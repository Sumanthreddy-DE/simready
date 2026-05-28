#!/usr/bin/env python3
"""Out-of-distribution eval: run the trained BRepSAGE model + rule pipeline on
real, UNLABELED CAD STEP files (e.g. McMaster-Carr / GrabCAD downloads).

The model was trained only on synthetic parametric solids + auto-degraded
variants. Real production parts (imported fillets, NURBS surfaces, dense small
features, high face counts) are out-of-distribution. There are no ground-truth
labels here, so this is a *generalization probe*, not an accuracy measurement:

- Does the graph-level defect head over-fire on real clean-ish parts, or
  correctly call most of them "clean"?  (false-positive behaviour)
- Does the learned ML aggregate track the rule-layer mean, or diverge?
- Does the pipeline survive real topology (large parts, open shells) without
  crashing?

Writes a Markdown table to --output and prints a compact summary.

Usage (sr env):
    $env:PYTHONPATH = "<repo_root>"
    C:\\mm\\sr\\python.exe scripts/eval_real_cad.py \
        --input tests/data/real_eval --output docs/validation/real_eval.md
"""
from __future__ import annotations

import argparse
import multiprocessing as mp
import sys
from pathlib import Path

from simready.ml.brepnet import resolve_weights_path, run_brepnet_inference
from simready.ml.graph_extractor import extract_brep_graph
from simready.occ_utils import TopAbs_FACE, count_shapes
from simready.pipeline import analyze_file
from simready.validator import validate_step_file

# Default face-count ceiling. Counting faces is a cheap topology walk; building
# the graph (area/curvature/UV per face) + the full rule pipeline is O(faces)
# and unguarded — a multi-thousand-face import can hang for tens of minutes.
# Parts above this are skipped, not extracted/analyzed.
DEFAULT_MAX_FACES = 800

# Hard per-part wall-clock for the expensive pass (extract + ML + rule pipeline).
# The pipeline calls into OCC C++; per the project's OCC lesson, a Python thread
# timeout does NOT actually kill a stuck C++ call (e.g. self-intersection /
# BOPAlgo on pathological NURBS). So the expensive pass runs in a SPAWN child
# process and the parent calls .terminate() on overrun — that is the only
# reliable way to bound runtime here. The 51-min hang on a 58-face cast flange
# (43505K359) motivated this — small face count is not a safety guarantee.
DEFAULT_ANALYZE_TIMEOUT_S = 60.0


def iter_steps(input_dir: Path):
    seen: set[str] = set()
    for pattern in ("*.step", "*.stp", "*.STEP", "*.STP"):
        for p in input_dir.glob(pattern):
            key = str(p.resolve()).lower()  # Windows is case-insensitive; dedupe
            if key not in seen:
                seen.add(key)
                yield p


def precheck_one(step_path: Path) -> tuple[dict, object | None]:
    """Cheap pass: validate + count faces only. NO graph extraction.

    Counting faces is a fast topology walk (TopExp_Explorer over TopAbs_FACE),
    so this cannot hang the way per-face geometry extraction can. Returns the
    partial row plus the validation result (so the expensive pass can reuse the
    already-loaded shape instead of re-reading the file)."""
    row: dict = {"file": step_path.name}
    validation = validate_step_file(str(step_path))
    row["is_valid"] = bool(getattr(validation, "is_valid", False))
    if not row["is_valid"]:
        row["error"] = "validation_failed"
        return row, None
    row["faces"] = count_shapes(validation.shape, TopAbs_FACE)
    return row, validation


def _analyze_worker_main(step_path_str: str, queue) -> None:
    """Spawn-child entry point: do the full expensive pipeline for ONE part and
    put a JSON-serializable result on ``queue``. The parent will .terminate()
    this process on timeout — that is the only reliable kill switch for an OCC
    C++ hang (Python thread timeouts cannot interrupt the C++ call).

    Must be a module-level function so it pickles cleanly under spawn."""
    try:
        validation = validate_step_file(step_path_str)
        if not getattr(validation, "is_valid", False):
            queue.put(("err", "validation_failed_in_child"))
            return
        graph = extract_brep_graph(validation.shape)
        ml = run_brepnet_inference(graph)
        report = analyze_file(step_path_str)
        score = report.get("score", {}) or {}
        findings = report.get("findings", []) or []
        severities: dict = {}
        for f in findings:
            sev = f.get("severity", "Info")
            severities[sev] = severities.get(sev, 0) + 1
        payload = {
            "weights_loaded": bool(ml.weights_loaded),
            "predicted_defect": ml.predicted_defect,
            "defect_confidence": round(float(ml.defect_confidence), 3),
            "ml_aggregate": round(float(ml.aggregate_score), 3),
            "overall": score.get("overall"),
            "label": score.get("label"),
            "complexity": report.get("complexity"),
            "rule_mean": round(float(report.get("rule_face_mean", 0.0) or 0.0), 3),
            "findings": len(findings),
            "severities": severities,
            "elapsed_s": round(float(report.get("elapsed_seconds", 0.0) or 0.0), 2),
        }
        queue.put(("ok", payload))
    except Exception as exc:
        queue.put(("err", f"{type(exc).__name__}: {exc}"))


def analyze_one(row: dict, step_path: Path, max_faces: int, timeout_s: float) -> dict:
    """Expensive pass: extract + ML + rule pipeline, in a spawn child.

    Parts above ``max_faces`` are skipped without spawning. For analyzed parts,
    the worker runs in a child process and the parent terminates it after
    ``timeout_s`` seconds — bounding wall-clock even when OCC hangs in C++."""
    faces = row.get("faces")
    if isinstance(faces, int) and faces > max_faces:
        row["skipped"] = f"too_large ({faces} faces)"
        return row

    ctx = mp.get_context("spawn")
    queue = ctx.Queue()
    proc = ctx.Process(target=_analyze_worker_main, args=(str(step_path), queue))
    proc.start()
    proc.join(timeout_s)
    if proc.is_alive():
        proc.terminate()
        proc.join(5)
        if proc.is_alive():
            try:
                proc.kill()
            except Exception:
                pass
        row["error"] = f"analyze_timeout (>{int(timeout_s)}s)"
        return row

    try:
        status, payload = queue.get(timeout=2)
    except Exception:
        row["error"] = f"no_result_from_worker (exit={proc.exitcode})"
        return row
    if status == "err":
        row["error"] = payload
        return row

    row.update(payload)
    return row


def fmt_sev(sev: dict) -> str:
    order = ["Critical", "Major", "Minor", "Info"]
    parts = [f"{k[0]}{sev[k]}" for k in order if sev.get(k)]
    return " ".join(parts) if parts else "-"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("tests/data/real_eval"))
    parser.add_argument("--output", type=Path, default=Path("docs/validation/real_eval.md"))
    parser.add_argument(
        "--max-faces", type=int, default=DEFAULT_MAX_FACES,
        help="Skip (do not extract/analyze) parts with more faces than this. "
             f"Default {DEFAULT_MAX_FACES}. Guards against multi-minute hangs on "
             "giant imports.")
    parser.add_argument(
        "--analyze-timeout", type=float, default=DEFAULT_ANALYZE_TIMEOUT_S,
        help="Hard per-part wall-clock for the expensive pass, in seconds. "
             f"Default {DEFAULT_ANALYZE_TIMEOUT_S:g}. Enforced via subprocess "
             "termination — bounds runtime even when OCC hangs in C++.")
    args = parser.parse_args(argv)

    if not args.input.is_dir():
        print(f"Input dir {args.input} missing.", file=sys.stderr)
        return 1

    weights = resolve_weights_path()
    if weights is None:
        print("WARNING: no checkpoint resolved — defect head will be absent "
              "(heuristic fallback). Train first.", file=sys.stderr, flush=True)

    steps = sorted(iter_steps(args.input))
    if not steps:
        print(f"No STEP files in {args.input}.", file=sys.stderr)
        return 1

    # Pass 1 — cheap precheck (validate + count faces). Cannot hang: no graph
    # extraction here. Carries the loaded validation forward to avoid re-reading.
    prechecked: list[tuple[dict, object | None, Path]] = []
    for i, step in enumerate(steps, 1):
        print(f"[precheck {i}/{len(steps)}] {step.name} ...", flush=True)
        try:
            row, validation = precheck_one(step)
        except Exception as exc:  # a malformed file must not abort the batch
            row, validation = {"file": step.name, "error": f"{type(exc).__name__}: {exc}"}, None
        prechecked.append((row, validation, step))
        print(f"    -> faces={row.get('faces', 'ERR')}", flush=True)

    # Process smallest-first so results land fast and the heavy parts come last
    # (where the --max-faces guard skips them outright). Errors sort first (-1).
    prechecked.sort(key=lambda it: it[0].get("faces") if isinstance(it[0].get("faces"), int) else -1)

    # Pass 2 — expensive extract + ML + rule pipeline, in a spawn child with
    # hard --analyze-timeout. The precheck's validation is intentionally NOT
    # carried into the child (TopoDS_Shape isn't picklable, and re-validating
    # in the child costs ms — far cheaper than the hang protection it enables).
    rows: list[dict] = []
    n = len(prechecked)
    for i, (row, _validation, step) in enumerate(prechecked, 1):
        if "error" in row:
            rows.append(row)
            continue
        print(f"[analyze {i}/{n}] {step.name} ({row.get('faces')} faces) ...", flush=True)
        try:
            rows.append(analyze_one(row, step, args.max_faces, args.analyze_timeout))
        except Exception as exc:  # never abort the batch on one bad file
            row["error"] = f"{type(exc).__name__}: {exc}"
            rows.append(row)
        print(f"    -> {rows[-1]}", flush=True)

    ok = [r for r in rows if "error" not in r and "skipped" not in r]
    skipped = [r for r in rows if "skipped" in r]
    errored = [r for r in rows if "error" in r]
    flagged = [r for r in ok if r.get("predicted_defect") and r["predicted_defect"] != "clean"]

    lines: list[str] = []
    lines.append("# Real-CAD Out-of-Distribution Eval\n")
    lines.append(f"**Checkpoint:** `{weights}`  ")
    lines.append(f"**Input:** `{args.input}` ({len(ok)}/{len(rows)} analyzed, "
                 f"{len(skipped)} skipped, {len(errored)} errored)  ")
    lines.append(f"**Max faces:** `{args.max_faces}` (parts above this are skipped, not extracted/analyzed)  ")
    lines.append("**Nature:** UNLABELED real McMaster-Carr-style parts — generalization probe, not accuracy.\n")
    lines.append("| File | Faces | Tier | Overall | Label | Rule mean | ML agg | Defect pred (conf) | Findings (sev) | s |")
    lines.append("|---|--:|---|--:|---|--:|--:|---|---|--:|")
    for r in rows:
        if "error" in r:
            lines.append(f"| {r['file']} | {r.get('faces','—')} | — | — | ERROR | — | — | {r['error']} | — | — |")
            continue
        if "skipped" in r:
            lines.append(f"| {r['file']} | {r.get('faces','?')} | — | — | SKIPPED | — | — | {r['skipped']} | — | — |")
            continue
        complexity = r.get("complexity") or {}
        tier = complexity.get("tier", "?") if isinstance(complexity, dict) else str(complexity)
        overall = r.get("overall")
        overall_str = f"{overall:.2f}" if isinstance(overall, (int, float)) else "?"
        lines.append(
            f"| {r['file']} | {r.get('faces','?')} | {tier} | "
            f"{overall_str} | {r.get('label','?')} | {r.get('rule_mean','?')} | "
            f"{r.get('ml_aggregate','?')} | {r.get('predicted_defect','?')} "
            f"({r.get('defect_confidence','?')}) | {fmt_sev(r.get('severities',{}))} | {r.get('elapsed_s','?')} |"
        )
    lines.append("")
    lines.append("## Summary\n")
    lines.append(f"- Analyzed {len(ok)}/{len(rows)} parts; {len(skipped)} skipped (>{args.max_faces} faces); "
                 f"{len(errored)} errored.")
    lines.append(f"- Defect head flagged a synthetic-defect class on {len(flagged)}/{len(ok)} "
                 f"analyzed parts (these are presumed defect-free; flags = false positives / OOD behaviour).")
    if ok:
        faces = [r["faces"] for r in ok if isinstance(r.get("faces"), int)]
        if faces:
            lines.append(f"- Analyzed face-count range: {min(faces)}–{max(faces)} "
                         f"({sum(1 for f in faces if f > 200)} analyzed parts >200 faces).")
    if skipped:
        skipped_desc = ", ".join(f"{r['file']} ({r.get('faces','?')} faces)" for r in skipped)
        lines.append(f"- Skipped (too large): {skipped_desc}.")
    lines.append("\n*(Interpretation written separately — these are raw outputs.)*\n")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote {args.output}  ({len(ok)} analyzed, {len(skipped)} skipped, "
          f"{len(errored)} errored, {len(flagged)} flagged)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
