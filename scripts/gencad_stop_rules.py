"""Offline prefix-only stop rules and the unchanged notebook cell-5 scoring logic.

Rule functions use only the standard library. Run this file with the CadQuery
environment to score; references never enter the rule functions.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

SKETCH = re.compile(r"^# Generating a workplane for sketch \d+[^\n]*(?:\n|$)", re.M)
SOLID = re.compile(r"^solid\s*=(?!=).*(?:\n|$)", re.M)


def complete(code: str) -> bool:
    """Whether Python can parse the entire prefix as complete statements."""
    try:
        ast.parse(code)
        return True
    except (SyntaxError, ValueError):
        return False


def r1(code: str) -> str:
    """Preserve complete input; otherwise retain the last complete solid line."""
    if complete(code):
        return code
    for match in reversed(list(SOLID.finditer(code))):
        prefix = code[:match.end()]
        if complete(prefix):
            return prefix
    return ""


def r2(code: str) -> str:
    """Stop before the first textually repeated index-normalized sketch block."""
    starts = [m.start() for m in SKETCH.finditer(code)] + [len(code)]
    seen = set()
    for start, end in zip(starts, starts[1:]):
        block = code[start:end]
        normalized = re.sub(r"\b(sketch|loop|solid)(\d+)\b", r"\1N", block)
        normalized = re.sub(r"(?<=wp_sketch)\d+\b", "N", normalized)
        normalized = re.sub(r"(?<=for sketch )\d+\b", "N", normalized)
        if normalized in seen:
            return r1(code[:start])
        seen.add(normalized)
    return r1(code)


def r3(code: str, k: int) -> str:
    """Keep at most k completed sketch blocks (eval-set sensitivity only)."""
    if k < 1:
        raise ValueError("k must be positive")
    starts = [m.start() for m in SKETCH.finditer(code)]
    prefix = code[:starts[k]] if len(starts) > k else code
    trimmed = r1(prefix)
    # A syntactically complete but unfinished sketch is not a complete block.
    ends = [m.end() for m in SOLID.finditer(trimmed) if complete(trimmed[:m.end()])]
    return trimmed[:ends[-1]] if ends else ""


def positive_control(rows: list[dict], baseline: dict[int, dict]) -> tuple[int, float]:
    """Fail closed unless all 100 flags and IoUs reproduce the saved scores."""
    if len(rows) != 100 or {r["idx"] for r in rows} != set(baseline):
        raise ValueError("positive control requires all 100 baseline rows")
    flags = sum(r["valid"] != baseline[r["idx"]]["valid"] for r in rows)
    delta = max(abs(r["iou"] - baseline[r["idx"]]["iou"]) for r in rows)
    if flags or delta > 1e-3:
        raise ValueError(f"positive control failed: flag mismatches={flags}, max IoU difference={delta:.9g}")
    return flags, delta


# Notebook cell 5: only paths/transport are adapted; the scoring logic is unchanged.
SCORER = r'''
import sys, json
sys.path.insert(0, sys.argv[1])
from metrics.best_iou import _load_solid_from_code, _normalized_mesh, iou_best
import cadquery as cq
gt, pr, step_out = open(sys.argv[2]).read(), open(sys.argv[3]).read(), sys.argv[4]
r = {"valid": False, "iou": 0.0, "err": None}
try:
    s_pr = _load_solid_from_code(pr, "pred")
    r["valid"] = True
except Exception as e:
    r["err"] = str(e)[:300]
if r["valid"]:
    try:
        cq.exporters.export(s_pr, step_out)
        s_gt = _load_solid_from_code(gt, "gt")
        r["iou"] = float(iou_best(_normalized_mesh(s_gt), _normalized_mesh(s_pr)))
    except Exception as e:
        r["err"] = "iou: " + str(e)[:300]
print(json.dumps(r))
'''


def score_one(metric_repo: Path, gt: str, prediction: str, directory: Path) -> dict:
    """One fresh process and 120-second timeout per notebook sample."""
    gt_path, pr_path = directory / "gt.py", directory / "pr.py"
    gt_path.write_text(gt, encoding="utf-8")
    pr_path.write_text(prediction, encoding="utf-8")
    try:
        proc = subprocess.run(
            [sys.executable, "-c", SCORER, str(metric_repo), str(gt_path),
             str(pr_path), str(directory / "part.step")],
            capture_output=True, text=True, timeout=120,
        )
        return (json.loads(proc.stdout.strip().splitlines()[-1]) if proc.stdout.strip()
                else {"valid": False, "iou": 0.0, "err": "crash: " + proc.stderr[-300:]})
    except subprocess.TimeoutExpired:
        return {"valid": False, "iou": 0.0, "err": "timeout 120s"}


def main() -> None:
    from gencad_common import CACHE, RESULTS, load_generations, load_reference, load_scores

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rule", required=True, choices=["R0", "R1", "R2", "R3"])
    parser.add_argument("--k", type=int)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    if (args.rule == "R3" and (args.k is None or not 1 <= args.k <= 8)
            or args.rule != "R3" and args.k is not None):
        parser.error("R3 requires --k in 1..8; other rules do not accept --k")
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    output = RESULTS / "stop_rules"
    baseline, generations = load_scores(), load_generations()
    assert sum(r["valid"] for r in baseline.values()) == 88
    assert all(r1(generations[i]["code"]) == generations[i]["code"]
               for i, row in baseline.items() if row["valid"]), "R1 changed a valid program"
    print("Negative control: R1 preserves all 88 valid programs byte-identically", flush=True)
    print("R2 changes", sum(r2(r["code"]) != r["code"] for r in generations.values()),
          "of 100 programs", flush=True)
    if args.rule != "R0":
        flags, delta = positive_control(json.loads((output / "scores_R0.json").read_text()), baseline)
        print(f"Positive control passed: flags={flags}, max IoU difference={delta:.9g}", flush=True)
    references = load_reference()
    transform = {"R0": lambda s: s, "R1": r1, "R2": r2, "R3": lambda s: r3(s, args.k)}[args.rule]
    rows = []
    with tempfile.TemporaryDirectory(dir=CACHE) as tmp:
        for i in sorted(generations)[:args.limit]:
            result = score_one(CACHE / "mecagent-technical-test", references[i]["code"],
                               transform(generations[i]["code"]), Path(tmp))
            rows.append({**result, "idx": i})
            print(f'{args.rule} {len(rows)} idx={i} valid={result["valid"]} iou={result["iou"]:.6f}', flush=True)
    output.mkdir(parents=True, exist_ok=True)
    tag = args.rule + (f"_k{args.k}" if args.k else "")
    if args.limit is not None:
        tag += f"_limit{args.limit}"
    (output / f"scores_{tag}.json").write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
    valid = [r for r in rows if r["valid"]]
    mean = statistics.mean(r["iou"] for r in valid) if valid else 0.0
    print(f"{tag}: n={len(rows)} / VSR={len(valid)/len(rows):.3f} / IoU valid-only={mean:.6f} / "
          f'IoU invalid=0={statistics.mean(r["iou"] for r in rows):.6f}', flush=True)
    if args.rule == "R0" and args.limit is None:
        flags, delta = positive_control(rows, baseline)
        print(f"Positive control passed: flags={flags}, max IoU difference={delta:.9g}")


if __name__ == "__main__":
    main()
