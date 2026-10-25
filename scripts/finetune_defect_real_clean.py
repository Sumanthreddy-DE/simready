#!/usr/bin/env python3
"""One-shot defect-head fine-tune; never materializes or evaluates real holdout."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import torch

from simready.ml.artifact_provenance import real_declared_artifacts, recorded_artifacts, real_source_provenance
from simready.ml.dataset import load_dataset, sample_source_id, source_part, split_train_val_by_source
from simready.ml.defect_finetune import (
    checkpoint_sha256,
    finetune_defect_head,
    load_brepsage_checkpoint,
)
from simready.ml.real_clean import load_real_clean_split

CONFIG = {
    "seed": 20260513,
    "epochs": 10,
    "lr": 1e-4,
    "batch_size": 16,
    "val_ratio": 0.2,
    "real_mass": 0.25,
}
DEFAULT_BASELINE = Path("weights/brepnet.pt")
DEFAULT_SYNTHETIC = Path("data/labels_combined_v2")
DEFAULT_REAL = Path("data/real_clean_v1/graphs")
DEFAULT_OUTPUT = Path("weights/experiments/real_clean_v1")
PROVENANCE_SOURCE_PATHS = (
    Path(__file__),
    Path(__file__).with_name("eval_defect_real_clean.py"),
    Path("simready/ml/dataset.py"),
    Path("simready/ml/defect_finetune.py"),
    Path("simready/ml/real_clean.py"),
    Path("simready/ml/model.py"),
)


def _source_record(data) -> dict[str, str]:
    return {"source_id": sample_source_id(data), "source_group": source_part(data.stem)}


def _git_output(arguments: list[str]) -> str | bytes:
    completed = subprocess.run(
        ["git", *arguments],
        check=True,
        capture_output=True,
        text=arguments[0] != "diff",
    )
    return completed.stdout


def code_provenance() -> dict[str, object]:
    """Identify the exact implementation, including evidence for uncommitted code."""
    revision = str(_git_output(["rev-parse", "HEAD"])).strip()
    status = str(_git_output(["status", "--porcelain"]))
    dirty = bool(status)
    source_files = {}
    for path in PROVENANCE_SOURCE_PATHS:
        status_line = str(_git_output(["status", "--porcelain", "--", str(path)]))
        status_code = status_line[:2] if status_line else ""
        git_status = "untracked" if status_code == "??" else "modified" if status_code else "clean"
        source_files[str(path)] = {
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "git_status": git_status,
        }
    evidence = {
        "commit_reproduces_code": not dirty,
        "source_files": source_files,
    }
    if dirty:
        diff = _git_output(["diff", "--binary", "HEAD", "--"])
        assert isinstance(diff, bytes)
        evidence.update({
            "note": "Working tree differs from code_revision; use source hashes and tracked diff hash as dirty-code evidence.",
            "tracked_diff_sha256": hashlib.sha256(diff).hexdigest(),
        })
    return {"code_revision": revision, "tree_dirty": dirty, "code_provenance": evidence}


def _checkpoint_payload(model) -> dict:
    config = model.config
    return {
        "state_dict": model.state_dict(),
        "config": {
            "in_dim": config.in_dim,
            "hidden_dim": config.hidden_dim,
            "num_layers": config.num_layers,
            "dropout": config.dropout,
            "num_defect_classes": config.num_defect_classes,
        },
    }


def train_experiment(baseline: Path, synthetic: Path, real: Path, output: Path) -> None:
    """Fit once using only real_fit and record every training-side decision."""
    if output.resolve() == baseline.resolve().parent:
        raise ValueError("output must not be the production baseline directory")
    if output.exists():
        raise FileExistsError(f"output path must be absent for a one-shot experiment: {output}")

    synthetic_data = load_dataset(synthetic)
    synthetic_fit, synthetic_val = split_train_val_by_source(
        synthetic_data, val_ratio=CONFIG["val_ratio"], seed=CONFIG["seed"]
    )
    # Hash all prepared artifacts without opening holdout graph/label content.
    synthetic_artifacts = recorded_artifacts(synthetic)
    real_artifacts = real_declared_artifacts(real)
    real_sources = real_source_provenance(real)
    real_fit = load_real_clean_split(real, "real_fit")
    real_fit_source_ids = [str(data.source_id) for data in real_fit]
    real_fit_families = sorted({str(data.family_id) for data in real_fit})
    baseline_model = load_brepsage_checkpoint(baseline)
    baseline_tensors = {name: tensor.detach().clone() for name, tensor in baseline_model.state_dict().items()}
    history = finetune_defect_head(
        baseline_model,
        real_fit,
        synthetic_fit,
        synthetic_val=synthetic_val,
        epochs=CONFIG["epochs"],
        lr=CONFIG["lr"],
        batch_size=CONFIG["batch_size"],
        seed=CONFIG["seed"],
        real_mass=CONFIG["real_mass"],
    )
    equality = {
        name: torch.equal(tensor, baseline_model.state_dict()[name])
        for name, tensor in baseline_tensors.items()
        if not name.startswith("defect_head.")
    }
    if not all(equality.values()):
        raise RuntimeError("non-defect baseline/candidate tensors differ")

    output.mkdir(parents=True)
    try:
        candidate_path = output / "candidate.pt"
        torch.save(_checkpoint_payload(baseline_model), candidate_path)
        candidate_sha256 = checkpoint_sha256(candidate_path)
        split_payload = {
            "seed": CONFIG["seed"],
            "val_ratio": CONFIG["val_ratio"],
            "fit": [_source_record(data) for data in synthetic_fit],
            "val": [_source_record(data) for data in synthetic_val],
        }
        config_payload = {
            "experiment": "real_clean_v1",
            "config": CONFIG,
            "baseline_path": str(baseline),
            "baseline_sha256": checkpoint_sha256(baseline),
            "candidate_sha256": candidate_sha256,
            "synthetic_path": str(synthetic),
            "real_path": str(real),
            "synthetic_artifacts": synthetic_artifacts,
            "real_artifacts": real_artifacts,
            "real_source_provenance": real_sources,
            **code_provenance(),
            "real_fit_source_ids": real_fit_source_ids,
            "real_fit_families": real_fit_families,
            "non_defect_baseline_candidate_equal": equality,
            "real_holdout_evaluated": False,
        }
        split_path = output / "synthetic_split.json"
        history_path = output / "history.json"
        split_path.write_text(json.dumps(split_payload, indent=2), encoding="utf-8")
        history_path.write_text(json.dumps(history, indent=2), encoding="utf-8")
        config_payload["synthetic_split_sha256"] = hashlib.sha256(split_path.read_bytes()).hexdigest()
        config_payload["history_sha256"] = hashlib.sha256(history_path.read_bytes()).hexdigest()
        (output / "config.json").write_text(json.dumps(config_payload, indent=2), encoding="utf-8")
    except Exception:
        # The output path remains visible as an incomplete, non-reusable attempt.
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--synthetic", type=Path, default=DEFAULT_SYNTHETIC)
    parser.add_argument("--real", type=Path, default=DEFAULT_REAL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    try:
        train_experiment(args.baseline, args.synthetic, args.real, args.output)
    except Exception as exc:
        print(f"Training failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(f"Saved one-shot candidate and provenance to {args.output}; real holdout was not materialized or evaluated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
