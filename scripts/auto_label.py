#!/usr/bin/env python3
"""Auto-label STEP datasets with SimReady rule and graph outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from simready.ml.graph_extractor import extract_brep_graph
from simready.pipeline import analyze_file
from simready.validator import validate_step_file


def iter_step_files(input_dir: Path):
    for suffix in ("*.step", "*.stp", "*.STEP", "*.STP"):
        yield from input_dir.rglob(suffix)


def main() -> int:
    parser = argparse.ArgumentParser(description="Auto-label STEP files for BRepNet fine-tuning")
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, object]] = []

    step_files = sorted(set(iter_step_files(args.input_dir)))
    if args.limit > 0:
        step_files = step_files[: args.limit]

    for step_file in step_files:
        try:
            report = analyze_file(str(step_file))
            validation = validate_step_file(str(step_file))
            if not validation.is_valid:
                manifest.append({"input_file": str(step_file), "status": "skipped", "reason": "validation_failed"})
                continue

            graph = extract_brep_graph(validation.shape)
            graph_payload = {
                "node_features": graph.node_features,
                "edge_features": graph.edge_features,
                "coedge_features": graph.coedge_features,
                "adjacency": graph.adjacency,
                "metadata": graph.metadata,
            }
            labels = {
                "rule_per_face": report.get("per_face_scores", {}),
                "combined_per_face": report.get("combined_per_face_scores", {}),
                "needs_refinement": {
                    str(face_index): float(score) > 0.5
                    for face_index, score in report.get("combined_per_face_scores", {}).items()
                },
                "score": report.get("score", {}),
                "status": report.get("status"),
            }

            stem = step_file.stem
            graph_path = args.output_dir / f"{stem}.graph.json"
            labels_path = args.output_dir / f"{stem}.labels.json"
            report_path = args.output_dir / f"{stem}.report.json"
            graph_path.write_text(json.dumps(graph_payload, indent=2), encoding="utf-8")
            labels_path.write_text(json.dumps(labels, indent=2), encoding="utf-8")
            report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            manifest.append({"input_file": str(step_file), "status": "ok", "graph": str(graph_path), "labels": str(labels_path)})
        except Exception as exc:
            manifest.append({"input_file": str(step_file), "status": "error", "reason": str(exc)})

    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
