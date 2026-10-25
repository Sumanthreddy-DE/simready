#!/usr/bin/env python3
"""Prepare graphs only from a strict, separately reviewed clean manifest."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from scripts.inspect_real_clean import (
    _validate_timeout,
    iter_step_files,
    run_spawn_worker,
    source_sha256,
)
from simready.ml.artifact_provenance import file_sha256
from simready.ml.graph_extractor import extract_brep_graph
from simready.ml.real_clean import build_real_labels, load_manifest
from simready.validator import validate_step_file


DEFAULT_PREPARE_TIMEOUT_SECONDS = 60.0


def _graph_payload(graph, sample) -> dict:
    payload = asdict(graph)
    payload["metadata"] = dict(payload["metadata"])
    payload["metadata"].update(
        {
            "source_id": sample.source_id,
            "family_id": sample.family_id,
            "split": sample.split,
            "source_sha256": sample.sha256,
        }
    )
    return payload


def _prepare_worker(step_path_str: str, sample, queue) -> None:
    """Spawn child for all OCC load/BRep/graph work."""
    try:
        validation = validate_step_file(step_path_str)
        if not validation.is_valid:
            queue.put({"kind": "error", "error": f"load+BRep validation failed: {validation.errors!r}"})
            return
        graph = extract_brep_graph(validation.shape)
        if not graph.node_features:
            queue.put({"kind": "error", "error": "graph extraction returned no node_features"})
            return
        labels = build_real_labels(sample, graph)
        queue.put({"kind": "ok", "graph": _graph_payload(graph, sample), "labels": labels})
    except BaseException as exc:
        queue.put({"kind": "error", "error": f"{type(exc).__name__}: {exc}"})


def prepare_one_in_subprocess(source: Path, sample, timeout_s: float) -> tuple[dict, dict]:
    outcome = run_spawn_worker(_prepare_worker, (str(source), sample), timeout_s)
    if outcome["kind"] == "timeout":
        raise TimeoutError(f"prepare_timeout (>{timeout_s:g}s); process={outcome['process']!r}")
    if outcome["kind"] != "result":
        raise RuntimeError(f"prepare process error: {outcome['error']}; process={outcome['process']!r}")
    payload = outcome["payload"]
    if not isinstance(payload, dict) or payload.get("kind") != "ok":
        raise ValueError(f"source {sample.source_id!r}: {payload!r}")
    return payload["graph"], payload["labels"]


def prepare(manifest_path: Path, input_dir: Path, output_dir: Path, timeout_s: float = DEFAULT_PREPARE_TIMEOUT_SECONDS) -> list[dict]:
    """Validate hashes in the parent and prepare OCC graphs in killable children."""
    timeout_s = _validate_timeout(timeout_s)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(f"output directory must be empty or absent: {output_dir}")
    if not input_dir.is_dir():
        raise ValueError(f"input directory does not exist: {input_dir}")

    samples = load_manifest(manifest_path)
    reviewed_manifest_sha256 = file_sha256(manifest_path)
    sources: dict[str, Path] = {}
    for path in iter_step_files(input_dir):
        source_key = path.stem.casefold()
        if source_key in sources:
            raise ValueError(f"input: source_id (file stem) must be unique case-insensitively: {path.stem!r}")
        sources[source_key] = path

    prepared: list[tuple[dict, dict, dict]] = []
    for sample in samples:
        source = sources.get(sample.source_id.casefold())
        if source is None:
            raise ValueError(f"source {sample.source_id!r}: exactly one STEP with this file stem is required")
        actual_sha256 = source_sha256(source)
        if actual_sha256 != sample.sha256:
            raise ValueError(f"source {sample.source_id!r}: sha256 mismatch: manifest={sample.sha256}, actual={actual_sha256}")
        graph_payload, labels = prepare_one_in_subprocess(source, sample, timeout_s)
        entry = {
            "status": "ok",
            "stem": sample.source_id,
            "source_id": sample.source_id,
            "family_id": sample.family_id,
            "split": sample.split,
            "face_count": labels["face_count"],
            "source_sha256": sample.sha256,
            "reviewed_manifest_sha256": reviewed_manifest_sha256,
            "graph_label": 0,
            "graph_label_name": "clean",
        }
        prepared.append((graph_payload, labels, entry))

    output_dir.mkdir(parents=True, exist_ok=True)
    for graph_payload, labels, entry in prepared:
        stem = entry["stem"]
        graph_path = output_dir / f"{stem}.graph.json"
        labels_path = output_dir / f"{stem}.labels.json"
        graph_path.write_text(json.dumps(graph_payload, indent=2), encoding="utf-8")
        labels_path.write_text(json.dumps(labels, indent=2), encoding="utf-8")
        entry["graph_sha256"] = file_sha256(graph_path)
        entry["labels_sha256"] = file_sha256(labels_path)
    entries = [entry for _graph, _labels, entry in prepared]
    (output_dir / "manifest.json").write_text(json.dumps(entries, indent=2), encoding="utf-8")
    return entries


def _positive_finite_timeout(value: str) -> float:
    try:
        return _validate_timeout(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=_positive_finite_timeout, default=DEFAULT_PREPARE_TIMEOUT_SECONDS)
    args = parser.parse_args(argv)
    try:
        entries = prepare(args.manifest, args.input, args.output, args.timeout)
    except Exception as exc:
        print(f"Preparation failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(f"Prepared {len(entries)} reviewed clean graphs in {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
