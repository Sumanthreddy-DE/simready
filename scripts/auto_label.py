#!/usr/bin/env python3
"""Auto-label STEP datasets with SimReady rule + graph outputs.

Each STEP produces three JSON files (and a manifest entry):

- `<stem>.graph.json`   — full graph extractor payload (nodes, edges, coedges, adjacency).
- `<stem>.labels.json`  — multi-task per-face labels:
                          - `refinement` (binary, from rule_per_face > threshold)
                          - `complexity_proxy` (continuous, derived from graph features only)
- `<stem>.report.json`  — full pipeline report (for traceability and debugging).

Labels are intentionally derived from independent sources: `refinement` reflects
the symbolic rule layer, `complexity_proxy` reflects raw graph topology. Training
on both encourages embeddings that capture more than either head alone.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from simready.ml.graph_extractor import extract_brep_graph
from simready.pipeline import analyze_file
from simready.validator import validate_step_file


SIMPLE_SURFACE_TYPES = {"plane", "cylinder"}
REFINEMENT_THRESHOLD = 0.5


def iter_step_files(input_dir: Path):
    for suffix in ("*.step", "*.stp", "*.STEP", "*.STP"):
        yield from input_dir.rglob(suffix)


def compute_complexity_proxy(graph) -> dict[int, float]:
    """Per-face complexity score derived purely from graph features.

    Higher when surface is non-simple, area is small, or adjacency degree is high.
    Range: [0, 1]. Independent of rule findings — that's deliberate so the model
    has a non-circular continuous regression target.
    """
    scores: dict[int, float] = {}
    if not graph.node_features:
        return scores

    areas = [float(n.get("area", 0.0) or 0.0) for n in graph.node_features]
    max_area = max(areas) if areas else 1.0
    if max_area <= 0.0:
        max_area = 1.0

    for node in graph.node_features:
        face_index = int(node.get("face_index", 0))
        area = float(node.get("area", 0.0) or 0.0)
        surface_type = str(node.get("surface_type", "other"))
        adjacency_degree = sum(1 for pair in graph.adjacency if face_index in pair)

        log_area_term = 0.0 if area <= 0.0 else 1.0 - min(1.0, math.log1p(area) / math.log1p(max_area))
        type_term = 0.0 if surface_type in SIMPLE_SURFACE_TYPES else 0.4
        degree_term = min(0.5, adjacency_degree * 0.05)
        score = min(1.0, 0.1 + 0.4 * log_area_term + type_term + degree_term)
        scores[face_index] = score
    return scores


def build_labels(report: dict, graph) -> dict[str, object]:
    rule_scores = {int(k): float(v) for k, v in (report.get("per_face_scores") or {}).items()}
    face_count = len(graph.node_features)
    indices = sorted({int(node.get("face_index", 0)) for node in graph.node_features})

    refinement = {str(idx): bool(rule_scores.get(idx, 0.0) > REFINEMENT_THRESHOLD) for idx in indices}
    complexity = compute_complexity_proxy(graph)

    return {
        "face_count": face_count,
        "indices": indices,
        "refinement": refinement,
        "complexity_proxy": {str(idx): float(complexity.get(idx, 0.0)) for idx in indices},
        "rule_per_face": {str(idx): float(rule_scores.get(idx, 0.0)) for idx in indices},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Auto-label STEP files for BRepNet fine-tuning")
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, object]] = []

    step_files = sorted(set(iter_step_files(args.input_dir)))
    if args.limit > 0:
        step_files = step_files[: args.limit]

    for step_file in step_files:
        stem = step_file.stem
        try:
            report = analyze_file(str(step_file))
            validation = validate_step_file(str(step_file))
            if not validation.is_valid:
                manifest.append({"input_file": str(step_file), "status": "skipped", "reason": "validation_failed"})
                continue

            graph = extract_brep_graph(validation.shape)
            if not graph.node_features:
                manifest.append({"input_file": str(step_file), "status": "skipped", "reason": "empty_graph"})
                continue

            graph_payload = {
                "node_features": graph.node_features,
                "edge_features": graph.edge_features,
                "coedge_features": graph.coedge_features,
                "adjacency": graph.adjacency,
                "metadata": graph.metadata,
            }
            labels = build_labels(report, graph)

            (args.output_dir / f"{stem}.graph.json").write_text(json.dumps(graph_payload, indent=2), encoding="utf-8")
            (args.output_dir / f"{stem}.labels.json").write_text(json.dumps(labels, indent=2), encoding="utf-8")
            (args.output_dir / f"{stem}.report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

            manifest.append({
                "input_file": str(step_file),
                "status": "ok",
                "stem": stem,
                "face_count": labels["face_count"],
                "positive_refinement": sum(1 for v in labels["refinement"].values() if v),
            })
            if args.verbose:
                print(f"[ok] {stem}: faces={labels['face_count']} pos_refinement={sum(1 for v in labels['refinement'].values() if v)}")
        except Exception as exc:
            manifest.append({"input_file": str(step_file), "status": "error", "reason": str(exc)})
            if args.verbose:
                print(f"[error] {step_file}: {exc}", file=sys.stderr)

    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    ok = sum(1 for entry in manifest if entry.get("status") == "ok")
    print(f"auto-labeled {ok}/{len(manifest)} STEPs into {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
