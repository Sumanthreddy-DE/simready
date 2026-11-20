"""CLI: python -m simready.bench {smoke,run,regrade,replay,repair,compare,repair-summary,report}.

Imports are lazy per subcommand so ``report`` runs in plain Python
(no OCC, no openai) on the committed logs.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = REPO_ROOT / "data" / "bench_runs"

SMOKE_PROMPT = "A 40 x 30 x 5 mm plate with one 6 mm through hole in the centre."


def _smoke(args: argparse.Namespace) -> int:
    from simready.bench.attempt import classify_spec, parse_reply
    from simready.bench.prompting import BUILD_PART_TOOL, build_messages
    from simready.bench.providers import ModelClient, load_providers

    provider = load_providers()[args.model]
    client = ModelClient(provider, max_retries=2)
    try:
        ids = sorted(m.id for m in client.client.models.list())
        print(f"models.list: {len(ids)} ids; configured id present: {provider.model in ids}")
        if provider.model not in ids:
            print("  ids containing the alias stem:", [i for i in ids if args.model.split("-")[0] in i.lower()][:20])
    except Exception as exc:  # noqa: BLE001 — some providers don't serve models.list
        print(f"models.list unavailable: {type(exc).__name__}")
    reply = client.complete(build_messages(SMOKE_PROMPT), [BUILD_PART_TOOL], 0.7, seed=0)
    parsed = parse_reply(reply["tool_calls"], reply["content"])
    cls = classify_spec(parsed.spec)[0] if parsed.spec is not None else "F1_no_parse"
    print(json.dumps({
        "model_returned": reply["model_returned"],
        "finish_reason": reply["finish_reason"],
        "via": parsed.via,
        "n_tool_calls": parsed.n_tool_calls,
        "pre_build_class": cls,
        "usage": reply["usage"],
        "latency_s": reply["latency_s"],
    }, indent=2))
    # Vultr answers an unknown model id with its default model instead of an error.
    if reply["model_returned"] != provider.model:
        print(f"model_returned {reply['model_returned']!r} != configured {provider.model!r}")
        return 1
    return 0 if parsed.spec is not None else 1


def _run(args: argparse.Namespace) -> int:
    from simready.bench.concepts import CONCEPTS_V1
    from simready.bench.providers import ModelClient, load_providers
    from simready.bench.runner import run_benchmark

    provider = load_providers()[args.model]
    concepts = Path(args.concepts) if args.concepts else CONCEPTS_V1
    # Deterministic id (no timestamp): re-running the same command resumes the same log.
    run_id = args.run_id or (f"{args.model}-{args.arm}-{concepts.stem}-k{args.k}"
                             + (f"-smoke{args.limit}" if args.limit else ""))
    summary = run_benchmark(
        client=ModelClient(provider),
        model_alias=args.model,
        model_id=provider.model,
        base_url=provider.base_url,
        k=args.k,
        out_path=RUNS_DIR / f"{run_id}.jsonl",
        concepts_path=concepts,
        arm=args.arm,
        limit=args.limit,
        workers=args.workers,
        official=args.official,
        max_tokens=provider.max_tokens,
        supports_seed=provider.supports_seed,
        extra_body=provider.extra_body,
    )
    print(f"{summary.path}: wrote {summary.written}, infra errors {summary.infra_errors}, "
          f"stopped: {summary.stopped_reason or 'no'}")
    return 0 if summary.stopped_reason is None else 2


def _regrade(args: argparse.Namespace) -> int:
    from simready.bench import CHECKER_VERSION
    from simready.bench.replay import regrade

    run = Path(args.run)
    stem = run.name.removesuffix(".gz").removesuffix(".jsonl")
    out = Path(args.out) if args.out else run.with_name(f"{stem}.regrade-{CHECKER_VERSION}.jsonl")
    n = regrade(run, out, concepts_path=args.concepts)
    print(f"{out}: re-graded {n} attempts with checker {CHECKER_VERSION}")
    return 0


def _replay(args: argparse.Namespace) -> int:
    from simready.bench.replay import replay

    match, logged, rebuilt = replay(Path(args.run), args.attempt_id, concepts_path=args.concepts)
    print(json.dumps({"match": match, "logged": logged, "rebuilt": rebuilt}, indent=2))
    return 0 if match else 1


def _repair(args: argparse.Namespace) -> int:
    from simready.bench.providers import ModelClient, load_providers
    from simready.bench.repair import repair_run

    provider = load_providers()[args.model]
    summary = repair_run(Path(args.run), Path(args.out), ModelClient(provider), model_id=provider.model,
                         max_rounds=args.max_rounds)
    print(f"{summary.path}: repaired {summary.repaired}, infra errors {summary.infra_errors}, "
          f"stopped: {summary.stopped_reason or 'no'}")
    return 0 if summary.stopped_reason is None else 2


def _set_ids(path: str) -> set[str]:
    return {line.strip() for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()}


def _label(run) -> str:
    return f"{run.header.get('model_alias') or run.header.get('model')}/{run.header.get('arm', 'dsl-v1')}"


def _compare(args: argparse.Namespace) -> int:
    from simready.bench.report import _ci, _pct, load_run, paired_diff, pool_runs, subset_p1

    ids = _set_ids(args.concepts)
    a = pool_runs([load_run(p) for p in args.a])
    b = pool_runs([load_run(p) for p in args.b])
    d = paired_diff(a, b, ids)
    print("| A | B | n concepts | A pass@1 | B pass@1 | diff | 95% CI |")
    print("|---|---|---|---|---|---|---|")
    print(f"| {_label(a)} | {_label(b)} | {d['n_concepts']} | {_pct(subset_p1(a, ids)['p1'])} | "
          f"{_pct(subset_p1(b, ids)['p1'])} | {_pct(d['diff'])} | {_ci(d['diff_ci'])} |")
    return 0


def _repair_summary(args: argparse.Namespace) -> int:
    from simready.bench.report import _ci, _pct, load_run, pool_runs, repair_summary

    single = pool_runs([load_run(p) for p in args.single])
    r = repair_summary(single, list(args.repair), _set_ids(args.concepts))
    fixed = r["fixed_in_round"]
    print("| model/arm | n | single | after repair | diff | 95% CI | fixed in round 1 / 2 |")
    print("|---|---|---|---|---|---|---|")
    print(f"| {_label(single)} | {r['n_concepts']} | {_pct(r['p1_single'])} | {_pct(r['p1_after'])} | "
          f"{_pct(r['diff'])} | {_ci(r['diff_ci'])} | {fixed.get(1, 0)} / {fixed.get(2, 0)} |")
    return 0


def _report(args: argparse.Namespace) -> int:
    from simready.bench.report import load_run, render_markdown

    md = render_markdown([load_run(p) for p in args.runs])
    if args.out:
        Path(args.out).write_text(md, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(md)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m simready.bench")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("smoke", help="one live call: model id, tool calling, parse")
    s.add_argument("--model", required=True)
    r = sub.add_parser("run", help="run the benchmark for one model")
    r.add_argument("--model", required=True)
    r.add_argument("--k", type=int, default=5)
    r.add_argument("--limit", type=int)
    r.add_argument("--run-id")
    r.add_argument("--workers", type=int, default=4)
    r.add_argument("--official", action="store_true")
    r.add_argument("--arm", choices=("dsl-v1", "dsl-v2", "build123d"), default="dsl-v1")
    r.add_argument("--concepts", default=None, help="concept file (default concepts_v1.jsonl)")
    g = sub.add_parser("regrade", help="re-check logged specs with the current checker")
    g.add_argument("run")
    g.add_argument("--out")
    g.add_argument("--concepts", default=None, help="concept file (default: the header's prompt_file)")
    p = sub.add_parser("replay", help="rebuild one attempt and verify its fingerprint")
    p.add_argument("run")
    p.add_argument("attempt_id")
    p.add_argument("--concepts", default=None, help="concept file (default: the header's prompt_file)")
    rr = sub.add_parser("repair", help="repair pass on a run's failed in-vocab attempts (logged apart)")
    rr.add_argument("run")
    rr.add_argument("--out", required=True)
    rr.add_argument("--model", required=True)
    rr.add_argument("--max-rounds", type=int, default=2)
    cp = sub.add_parser("compare", help="paired pass@1 difference of two arms on a concept-id set")
    cp.add_argument("--a", nargs="+", required=True)
    cp.add_argument("--b", nargs="+", required=True)
    cp.add_argument("--concepts", required=True, help="file with one concept id per line")
    rs = sub.add_parser("repair-summary", help="single-shot vs after-repair pass@1 on a concept-id set")
    rs.add_argument("--single", nargs="+", required=True)
    rs.add_argument("--repair", nargs="+", required=True)
    rs.add_argument("--concepts", required=True, help="file with one concept id per line")
    rp = sub.add_parser("report", help="bench_v1.md tables from run logs (no OCC needed)")
    rp.add_argument("runs", nargs="+")
    rp.add_argument("--out")
    args = ap.parse_args(argv)
    handlers = {"smoke": _smoke, "run": _run, "regrade": _regrade, "replay": _replay, "report": _report,
                "repair": _repair,
                "compare": _compare, "repair-summary": _repair_summary}
    return handlers[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
