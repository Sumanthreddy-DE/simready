"""Per-stage OCC hang attribution for analyze_file on real CAD.

The real-CAD eval (docs/validation/real_eval.md §3) showed analyze_file
hanging on 4/12 industrial parts. Python thread timeouts cannot stop the
underlying OCC C++ call, so each (part, stage) probe here runs in its own
``multiprocessing.spawn`` child with a hard timeout + ``terminate()`` —
a hung stage kills only its own probe, never the batch.

Stages mirror ``simready.pipeline._analyze_file_inner`` order: load,
validate, heal, parse, the 13 checks of
``simready.checks.run_essential_checks_detailed`` individually, then
graph extraction and ML inference. Stages depending on a prerequisite
that already timed out are skipped and marked ``blocked_by_prereq``
(probing them would just rediscover the same hang, 90 s at a time).

Usage (sr env, PYTHONPATH set):
    python scripts/diagnose_occ_hang.py --input tests/data/real_eval \
        --parts 33125T73 --stage-timeout 90 \
        --output docs/validation/occ_hang_diagnosis
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import sys
import time
from pathlib import Path

# Checks taking (shape,) only; the rest take (shape, geometry_summary).
_SHAPE_ONLY_CHECKS = {
    "check_non_manifold_edges",
    "check_sharp_edges",
    "check_self_intersection",
}

CHECK_STAGES = [
    "check_degenerate_geometry",
    "check_non_manifold_edges",
    "check_open_boundaries",
    "check_short_edges",
    "check_thin_walls",
    "check_small_features",
    "check_small_fillets",
    "check_duplicate_body_heuristic",
    "check_thin_solid",
    "check_duplicate_face_heuristic",
    "check_orientation_nuance",
    "check_sharp_edges",
    "check_self_intersection",
]

STAGES = ["load", "validate", "heal", "parse", *CHECK_STAGES, "graph", "ml"]

# stage -> prerequisite chain that a child must rebuild before timing it.
_PREREQS = {
    "load": [],
    "validate": ["load"],
    "heal": ["load"],
    "parse": ["load", "heal"],
    "graph": ["load", "heal"],
    "ml": ["load", "heal"],
    **{name: ["load", "heal", "parse"] for name in CHECK_STAGES},
}


def _probe(step_path: str, stage: str, q) -> None:
    """Child process: rebuild prerequisites, then time exactly one stage."""
    from simready.healer import heal_shape
    from simready.parser import parse_geometry
    from simready.validator import validate_brep, validate_file_load

    t_load = time.perf_counter()
    load = validate_file_load(step_path)
    if not load.is_valid:
        q.put({"stage": stage, "error": "load_invalid"})
        return
    shape = load.shape
    if stage == "load":
        q.put({"stage": stage, "seconds": time.perf_counter() - t_load})
        return
    if stage == "validate":
        t = time.perf_counter()
        validate_brep(shape)
        q.put({"stage": stage, "seconds": time.perf_counter() - t})
        return

    t = time.perf_counter()
    healed = heal_shape(shape)
    shape = healed.healed_shape
    if stage == "heal":
        q.put({"stage": stage, "seconds": time.perf_counter() - t})
        return

    t = time.perf_counter()
    summary = parse_geometry(shape)
    if stage == "parse":
        q.put({"stage": stage, "seconds": time.perf_counter() - t})
        return

    if stage in CHECK_STAGES:
        import simready.checks as checks

        fn = getattr(checks, stage)
        args = (shape,) if stage in _SHAPE_ONLY_CHECKS else (shape, summary)
        t = time.perf_counter()
        fn(*args)
        q.put({"stage": stage, "seconds": time.perf_counter() - t})
        return

    if stage in ("graph", "ml"):
        from simready.ml.graph_extractor import extract_brep_graph

        t = time.perf_counter()
        graph = extract_brep_graph(shape)
        if stage == "graph":
            q.put({"stage": stage, "seconds": time.perf_counter() - t})
            return
        from simready.ml.brepnet import run_brepnet_inference

        t = time.perf_counter()
        run_brepnet_inference(graph)
        q.put({"stage": stage, "seconds": time.perf_counter() - t})
        return

    q.put({"stage": stage, "error": "unknown_stage"})


def probe_part(step_path: Path, stage_timeout: float) -> list[dict]:
    ctx = mp.get_context("spawn")
    rows: list[dict] = []
    timed_out: set[str] = set()
    for stage in STAGES:
        blocked = [p for p in _PREREQS[stage] if p in timed_out]
        if blocked:
            rows.append({"stage": stage, "blocked_by_prereq": blocked[0]})
            print(f"  {stage}: blocked by {blocked[0]}", flush=True)
            continue
        q = ctx.Queue()
        proc = ctx.Process(target=_probe, args=(str(step_path), stage, q))
        started = time.perf_counter()
        proc.start()
        proc.join(timeout=stage_timeout)
        if proc.is_alive():
            proc.terminate()
            proc.join(5)
            timed_out.add(stage)
            rows.append({
                "stage": stage,
                "timeout": True,
                "wall": round(time.perf_counter() - started, 2),
            })
        elif not q.empty():
            row = q.get()
            if "seconds" in row:
                row["seconds"] = round(row["seconds"], 3)
            rows.append(row)
        else:
            # Child died without a result (crash) — count as suspect too.
            rows.append({"stage": stage, "error": f"exit_{proc.exitcode}"})
        print(f"  {stage}: {rows[-1]}", flush=True)
    return rows


def _fmt_cell(row: dict) -> str:
    if row.get("timeout"):
        return "**TIMEOUT**"
    if "blocked_by_prereq" in row:
        return f"blocked ({row['blocked_by_prereq']})"
    if "error" in row:
        return f"err:{row['error']}"
    return f"{row['seconds']:.2f}"


def write_markdown(results: dict[str, list[dict]], out_md: Path, timeout: float) -> None:
    parts = list(results)
    lines = [
        "# OCC Hang Diagnosis — per-stage attribution",
        "",
        f"Per-(part, stage) spawn-subprocess probes, hard timeout {timeout:.0f} s.",
        "Cells: seconds, **TIMEOUT** (culprit), blocked (prereq hung), or err.",
        "",
        "| Stage | " + " | ".join(Path(p).stem.split("_")[0] for p in parts) + " |",
        "|---|" + "---|" * len(parts),
    ]
    for i, stage in enumerate(STAGES):
        cells = [_fmt_cell(results[p][i]) for p in parts]
        lines.append(f"| {stage} | " + " | ".join(cells) + " |")
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("tests/data/real_eval"))
    parser.add_argument("--parts", nargs="*", default=[],
                        help="Stem substrings to include (default: all STEPs)")
    parser.add_argument("--stage-timeout", type=float, default=90.0)
    parser.add_argument("--output", type=Path,
                        default=Path("docs/validation/occ_hang_diagnosis"))
    args = parser.parse_args()

    # Case-insensitive FS: *.STEP and *.step return the same files — dedupe.
    steps = sorted(
        {p.resolve() for p in (*args.input.glob("*.STEP"), *args.input.glob("*.step"))}
    )
    if args.parts:
        steps = [s for s in steps if any(p in s.stem for p in args.parts)]
    if not steps:
        print(f"No STEP files matched under {args.input}", file=sys.stderr)
        return 2

    results: dict[str, list[dict]] = {}
    for step in steps:
        print(f"[part] {step.name}", flush=True)
        results[str(step)] = probe_part(step, args.stage_timeout)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    out_json = args.output.with_suffix(".json")
    out_json.write_text(json.dumps(results, indent=2), encoding="utf-8")
    write_markdown(results, args.output.with_suffix(".md"), args.stage_timeout)
    print(f"Wrote {out_json} and {args.output.with_suffix('.md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
