"""bench_v1.md tables from run logs. Stdlib (+ pydantic via concepts) only:
no OCC, no network — the README's quick reproduce path.

pass@1 = mean success over a prompt's attempts; pass@k = share of prompts
with at least one pass (n = k, so exact). Headline numbers are over in-vocab
concepts only. 95% CIs bootstrap over CONCEPTS (a concept's 3 x k attempts
are not independent). Mechanical-reasoning gap = pass@1(explicit) -
pass@1(engineer), paired per concept.
"""

from __future__ import annotations

import random
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from simready.bench import runlog
from simready.bench.concepts import PHRASINGS

N_BOOT = 2000
BOOT_SEED = 20261004
FAILURE_CLASSES = [
    "F1_no_parse", "F2_schema", "F3_reference", "F4_build_error", "F5_invalid_solid",
    "F6_dimension_miss", "F7_feature_miss", "F8_timeout", "F9_out_of_vocab",
]


@dataclass
class ModelRun:
    header: dict
    attempts: list[dict]  # scored attempts only
    excluded: int  # infra_error + checker_error
    excluded_attempts: list[dict] | None = None


def load_run(path: str | Path) -> ModelRun:
    all_attempts = runlog.attempts(path)
    scored = [a for a in all_attempts if a.get("failure_class") not in runlog.EXCLUDED_CLASSES]
    excluded = [a for a in all_attempts if a.get("failure_class") in runlog.EXCLUDED_CLASSES]
    return ModelRun(runlog.read_header(path), scored, len(excluded), excluded)


def _prompts(run: ModelRun, in_vocab: bool = True) -> dict[tuple[str, str], list[bool]]:
    table: dict[tuple[str, str], list[bool]] = defaultdict(list)
    for a in run.attempts:
        if a["in_vocab"] == in_vocab:
            table[(a["concept_id"], a["phrasing"])].append(bool(a["passed"]))
    return table


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else float("nan")


def _bootstrap(values_by_concept: dict[str, list[float]]) -> tuple[float, float]:
    keys = sorted(values_by_concept)
    if not keys:
        return (float("nan"), float("nan"))
    rng = random.Random(BOOT_SEED)
    stats = []
    for _ in range(N_BOOT):
        sample = [v for k in (rng.choice(keys) for _ in keys) for v in values_by_concept[k]]
        stats.append(_mean(sample))
    stats.sort()
    return stats[int(0.025 * N_BOOT)], stats[int(0.975 * N_BOOT) - 1]


def headline(run: ModelRun) -> dict:
    prompts = _prompts(run)
    p1_by: dict[str, list[float]] = defaultdict(list)
    pk_by: dict[str, list[float]] = defaultdict(list)
    for (cid, _), results in prompts.items():
        p1_by[cid].append(_mean([float(r) for r in results]))
        pk_by[cid].append(1.0 if any(results) else 0.0)
    return {
        "p1": _mean([v for vs in p1_by.values() for v in vs]),
        "p1_ci": _bootstrap(p1_by),
        "pk": _mean([v for vs in pk_by.values() for v in vs]),
        "pk_ci": _bootstrap(pk_by),
        "n_concepts": len(p1_by),
        "n_prompts": len(prompts),
    }


def by_phrasing(run: ModelRun) -> dict:
    prompts = _prompts(run)
    p1: dict[str, dict[str, float]] = defaultdict(dict)
    for (cid, ph), results in prompts.items():
        p1[ph][cid] = _mean([float(r) for r in results])
    paired = {cid: [p1["explicit"][cid] - p1["engineer"][cid]]
              for cid in p1.get("explicit", {}) if cid in p1.get("engineer", {})}
    return {
        "p1": {ph: _mean(list(p1[ph].values())) for ph in PHRASINGS if p1.get(ph)},
        "gap": _mean([d[0] for d in paired.values()]),
        "gap_ci": _bootstrap(paired),
    }


def failure_distribution(run: ModelRun) -> dict[str, Counter]:
    dist: dict[str, Counter] = {ph: Counter() for ph in PHRASINGS}
    for a in run.attempts:
        if a["in_vocab"] and a.get("failure_class"):
            dist[a["phrasing"]][a["failure_class"]] += 1
    return dist


def out_of_vocab(run: ModelRun) -> Counter:
    out: Counter = Counter()
    for a in run.attempts:
        if a["in_vocab"]:
            continue
        cls = a.get("failure_class")
        if cls == "F9_out_of_vocab":
            out["used_missing_op (F9)"] += 1
        elif cls == "F1_no_parse":
            out["declined / no spec (F1)"] += 1
        elif a.get("passed"):
            out["faked: built and passed checks"] += 1
        else:
            out["faked: built or tried, failed"] += 1
    return out


def cost(run: ModelRun) -> dict:
    usage = [a["usage"] for a in run.attempts if a.get("usage")]
    lat = [a["latency_s"] for a in run.attempts if a.get("latency_s") is not None]
    return {
        "calls": len(run.attempts) + run.excluded,
        "prompt_tokens": sum(u.get("prompt_tokens") or 0 for u in usage),
        "completion_tokens": sum(u.get("completion_tokens") or 0 for u in usage),
        "median_latency_s": statistics.median(lat) if lat else float("nan"),
    }


def incomplete_prompts(run: ModelRun) -> int:
    """Prompts with fewer than k scored attempts (pass@k is then not exact)."""
    k = run.header["k"]
    counts: Counter = Counter((a["concept_id"], a["phrasing"]) for a in run.attempts)
    keys = set(counts) | {(a["concept_id"], a["phrasing"]) for a in (run.excluded_attempts or [])}
    return sum(1 for key in keys if counts[key] < k)


def _pct(x: float) -> str:
    return "n/a" if x != x else f"{100 * x:.1f}%"


def _ci(ci: tuple[float, float]) -> str:
    return f"[{_pct(ci[0])}, {_pct(ci[1])}]"


def render_markdown(runs: list[ModelRun]) -> str:
    lines: list[str] = []
    add = lines.append
    add("## 1. Setup\n")
    add("| model | id | base URL | k | temp | prompt sha256 | checker | official | started | incomplete prompts |")
    add("|---|---|---|---|---|---|---|---|---|---|")
    for r in runs:
        h = r.header
        add(f"| {h.get('model_alias')} | `{h.get('model')}` | {h.get('base_url')} | {h.get('k')} | "
            f"{h.get('temperature')} | `{h.get('prompt_sha256', '')[:12]}` | {h.get('checker_version')} | "
            f"{h.get('official')} | {h.get('started')} | {incomplete_prompts(r)} |")
    add("\nNumbers here are **not comparable** to `docs/validation/geometry_gen_eval.md` "
        "(different models, prompts and metric).\n")
    add("## 2. Headline (in-vocab prompts, 95% CI bootstrapped over concepts)\n")
    add("| model | pass@1 | 95% CI | pass@k | 95% CI | concepts | prompts |")
    add("|---|---|---|---|---|---|---|")
    for r in runs:
        h = headline(r)
        add(f"| {r.header.get('model_alias')} | {_pct(h['p1'])} | {_ci(h['p1_ci'])} | {_pct(h['pk'])} | "
            f"{_ci(h['pk_ci'])} | {h['n_concepts']} | {h['n_prompts']} |")
    add("\n## 3. By phrasing (pass@1) and mechanical-reasoning gap\n")
    add("| model | explicit | engineer | intent | gap (explicit - engineer) | paired 95% CI |")
    add("|---|---|---|---|---|---|")
    for r in runs:
        b = by_phrasing(r)
        p = b["p1"]
        add(f"| {r.header.get('model_alias')} | {_pct(p.get('explicit', float('nan')))} | "
            f"{_pct(p.get('engineer', float('nan')))} | {_pct(p.get('intent', float('nan')))} | "
            f"{_pct(b['gap'])} | {_ci(b['gap_ci'])} |")
    add("\n## 4. Failure classes (in-vocab, failed attempts)\n")
    add("| model | phrasing | " + " | ".join(FAILURE_CLASSES) + " |")
    add("|---|---|" + "---|" * len(FAILURE_CLASSES))
    for r in runs:
        for ph, counter in failure_distribution(r).items():
            add(f"| {r.header.get('model_alias')} | {ph} | " + " | ".join(str(counter[c]) for c in FAILURE_CLASSES) + " |")
    add("\n## 5. Out-of-vocab concepts (reported separately, never in the headline)\n")
    add("| model | outcome | attempts |")
    add("|---|---|---|")
    for r in runs:
        for outcome, n in sorted(out_of_vocab(r).items()):
            add(f"| {r.header.get('model_alias')} | {outcome} | {n} |")
    add("\n## 6. Cost\n")
    add("| model | calls | prompt tokens | completion tokens | median latency (s) | excluded (infra/checker) |")
    add("|---|---|---|---|---|---|")
    for r in runs:
        c = cost(r)
        add(f"| {r.header.get('model_alias')} | {c['calls']} | {c['prompt_tokens']} | {c['completion_tokens']} | "
            f"{c['median_latency_s']:.2f} | {r.excluded} |")
    add("\n## 8. Known limits (generated counts)\n")
    for r in runs:
        nc = sum((a.get("check_report") or {}).get("n_not_checked", 0) for a in r.attempts)
        add(f"- {r.header.get('model_alias')}: {nc} `not_checked` results across scored attempts.")
    add("")
    return "\n".join(lines)
