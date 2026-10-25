#!/usr/bin/env python3
"""Evaluate a recorded candidate once on its final real holdout."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from simready.ml.artifact_provenance import file_sha256, verify_artifact_hashes
from simready.ml.dataset import load_dataset, sample_source_id
from simready.ml.defect_finetune import (
    checkpoint_sha256,
    compare_checkpoints,
    evaluate_defect,
    load_brepsage_checkpoint,
)
from simready.ml.real_clean import clean_false_positive_rate, load_real_clean_split

DEFAULT_BASELINE = Path("weights/brepnet.pt")
DEFAULT_CANDIDATE = Path("weights/experiments/real_clean_v1/candidate.pt")
DEFAULT_SYNTHETIC = Path("data/labels_combined_v2")
DEFAULT_REAL = Path("data/real_clean_v1/graphs")
DEFAULT_OUTPUT = Path("weights/experiments/real_clean_v1/evaluation.json")


def _status_path(output: Path) -> Path:
    return output.with_name(f"{output.stem}.status.json")


def _write_status(output: Path, status: str, error: str | None = None) -> None:
    payload = {"status": status}
    if error is not None:
        payload["error"] = error
    _status_path(output).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _reserve(output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError:
        raise FileExistsError(f"evaluation output already exists; reruns are refused: {output}") from None
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump({"status": "running"}, stream)
    _write_status(output, "running")


def _recorded_synthetic_val(synthetic_path: Path, split_path: Path) -> list:
    split = json.loads(split_path.read_text(encoding="utf-8"))
    recorded_ids = [row["source_id"] for row in split["val"]]
    if not recorded_ids or len(recorded_ids) != len(set(recorded_ids)):
        raise ValueError("recorded synthetic validation IDs must be nonempty and unique")
    loaded = load_dataset(synthetic_path)
    loaded_ids = [sample_source_id(data) for data in loaded]
    if len(loaded_ids) != len(set(loaded_ids)):
        raise ValueError("recorded synthetic validation requires unique dataset IDs")
    by_id = dict(zip(loaded_ids, loaded))
    if not set(recorded_ids).issubset(by_id):
        raise ValueError("recorded synthetic validation IDs must all be present")
    return [by_id[source_id] for source_id in recorded_ids]


def _source_git_status(path: str) -> str:
    completed = subprocess.run(
        ["git", "status", "--porcelain", "--", path],
        check=True,
        capture_output=True,
        text=True,
    )
    status_code = completed.stdout[:2]
    return "untracked" if status_code == "??" else "modified" if status_code else "clean"


def _verify_code_provenance(config: dict) -> None:
    evidence = config.get("code_provenance")
    if not isinstance(evidence, dict):
        raise ValueError("code provenance source_files required")
    source_files = evidence.get("source_files")
    if not isinstance(source_files, dict) or not source_files:
        raise ValueError("code provenance source_files must be nonempty")
    for name, recorded in source_files.items():
        if not isinstance(recorded, dict):
            raise ValueError(f"invalid source provenance record: {name}")
        path = Path(name)
        try:
            actual_hash = file_sha256(path)
        except OSError as exc:
            raise ValueError(f"training source unavailable: {path}") from exc
        if actual_hash != recorded.get("sha256"):
            raise ValueError(f"training source hash mismatch: {path}")
        actual_status = _source_git_status(name)
        if actual_status != recorded.get("git_status"):
            raise ValueError(f"training source git status mismatch: {path}: {actual_status}")


def _verify_config(config_path: Path, synthetic_split: Path, baseline: Path, candidate: Path) -> dict:
    if not config_path.is_file():
        raise FileNotFoundError(f"training config required: {config_path}")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    from scripts.finetune_defect_real_clean import CONFIG as FIXED_TRAINING_CONFIG

    if config.get("config") != FIXED_TRAINING_CONFIG:
        raise ValueError("training config does not exactly match the fixed evaluation configuration")
    split_path = synthetic_split
    history_path = config_path.with_name("history.json")
    split = json.loads(split_path.read_text(encoding="utf-8"))
    for field, expected in (("seed", FIXED_TRAINING_CONFIG["seed"]), ("val_ratio", FIXED_TRAINING_CONFIG["val_ratio"])):
        if split.get(field) != expected:
            raise ValueError(f"synthetic split {field} mismatch: expected {expected}, actual {split.get(field)}")
    for name, path, key in (
        ("synthetic_split.json", split_path, "synthetic_split_sha256"),
        ("history.json", history_path, "history_sha256"),
    ):
        actual = file_sha256(path)
        if config.get(key) != actual:
            raise ValueError(f"{name} hash mismatch: expected {config.get(key)}, actual {actual}")
    # Source identity is deliberately checked before any dataset graph/label loading.
    _verify_code_provenance(config)
    for name, path in (("baseline", baseline), ("candidate", candidate)):
        expected = config.get(f"{name}_sha256")
        actual = checkpoint_sha256(path)
        if expected != actual:
            raise ValueError(f"{name} checkpoint hash mismatch: expected {expected}, actual {actual}")
    return config


def record_fixed_config_artifact_hashes(config_path: Path) -> None:
    """Test-fixture helper matching the training writer's post-artifact sealing order."""
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["synthetic_split_sha256"] = file_sha256(config_path.with_name("synthetic_split.json"))
    config["history_sha256"] = file_sha256(config_path.with_name("history.json"))
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")


def _validate_inspection(inspection_path: Path, source_provenance: dict[str, str]) -> tuple[list[dict], str]:
    records = json.loads(inspection_path.read_text(encoding="utf-8"))["records"]
    by_id = {}
    for record in records:
        source_id = record.get("source_id")
        if not isinstance(source_id, str) or not source_id or source_id in by_id:
            raise ValueError(f"inspection source_id must be nonempty and unique: {source_id!r}")
        by_id[source_id] = record
    for source_id, expected_sha256 in source_provenance.items():
        record = by_id.get(source_id)
        if record is None or record.get("source_sha256") != expected_sha256:
            raise ValueError(f"inspection source_sha256 missing or stale for {source_id}")
    return records, file_sha256(inspection_path)


def _excluded_or_skipped(records: list[dict], evaluated_ids: set[str]) -> list[dict]:
    return [
        {
            "source_id": record["source_id"],
            "status": record.get("status"),
            "inspection": record.get("inspection"),
            "errors": record.get("errors", []),
        }
        for record in records
        if record["source_id"] not in evaluated_ids
    ]


def _evaluate_reserved(
    baseline: Path,
    candidate: Path,
    synthetic_split: Path,
    real: Path,
    output: Path,
    inspection: Path,
    synthetic: Path,
) -> dict:
    config = _verify_config(synthetic_split.parent / "config.json", synthetic_split, baseline, candidate)
    # All declared real artifacts are verified as bytes before holdout graph loading.
    verify_artifact_hashes(real, config["real_artifacts"])
    verify_artifact_hashes(synthetic, config["synthetic_artifacts"])
    inspection_records, inspection_sha256 = _validate_inspection(inspection, config["real_source_provenance"])
    real_fit = load_real_clean_split(real, "real_fit")
    real_holdout = load_real_clean_split(real, "final_holdout")
    synthetic_val = _recorded_synthetic_val(synthetic, synthetic_split)
    result = compare_checkpoints(baseline, candidate, real_holdout, synthetic_val)
    real_fit_diagnostic = {
        "held_out": False,
        "primary_clean_false_positive_metric": False,
        "source_ids": [sample_source_id(data) for data in real_fit],
        "note": "Training split diagnostic only; not a holdout or clean false-positive-rate result.",
    }
    for name, checkpoint_path in (("baseline", baseline), ("candidate", candidate)):
        model = load_brepsage_checkpoint(checkpoint_path)
        predictions = [row["prediction"] for row in result[name]["real_holdout"]["predictions"]]
        result[name]["real_holdout"]["clean_false_positive_rate"] = clean_false_positive_rate(predictions)
        real_fit_diagnostic[name] = evaluate_defect(model, real_fit)
    evaluated_ids = set(config["real_source_provenance"])
    result.update({
        "status": "complete",
        "real_fit_diagnostic": real_fit_diagnostic,
        "synthetic_validation_source_ids": [sample_source_id(data) for data in synthetic_val],
        "inspection_sha256": inspection_sha256,
        "provenance_verified": {
            "source_matches_training": True,
            "synthetic_split_sha256": True,
            "history_sha256": True,
            "fixed_training_config": True,
        },
        "excluded_or_skipped": _excluded_or_skipped(inspection_records, evaluated_ids),
    })
    return result


def evaluate_experiment(
    baseline: Path,
    candidate: Path,
    synthetic_split: Path,
    real: Path,
    output: Path,
    inspection: Path,
    synthetic: Path | None = None,
) -> dict:
    """Reserve once, validate all provenance, then evaluate and publish atomically."""
    synthetic = DEFAULT_SYNTHETIC if synthetic is None else synthetic
    _reserve(output)
    try:
        result = _evaluate_reserved(baseline, candidate, synthetic_split, real, output, inspection, synthetic)
        temporary = output.with_name(f"{output.name}.tmp")
        temporary.write_text(json.dumps(result, indent=2), encoding="utf-8")
        os.replace(temporary, output)
        _write_status(output, "complete")
        return result
    except Exception as exc:
        try:
            failure = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}
            output.write_text(json.dumps(failure, indent=2), encoding="utf-8")
            _status_path(output).write_text(json.dumps(failure, indent=2), encoding="utf-8")
        except Exception:
            pass
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--synthetic-split", type=Path, default=DEFAULT_CANDIDATE.parent / "synthetic_split.json")
    parser.add_argument("--synthetic", type=Path, default=DEFAULT_SYNTHETIC)
    parser.add_argument("--real", type=Path, default=DEFAULT_REAL)
    parser.add_argument("--inspection", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    try:
        result = evaluate_experiment(
            args.baseline, args.candidate, args.synthetic_split, args.real,
            args.output, args.inspection, args.synthetic,
        )
    except Exception as exc:
        print(f"Evaluation failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(f"Saved final one-shot evaluation to {args.output}")
    print("Final holdout clean FP rates:")
    for name in ("baseline", "candidate"):
        print(f"  {name}: {result[name]['real_holdout']['clean_false_positive_rate']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
