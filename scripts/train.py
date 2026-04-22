#!/usr/bin/env python3
"""Colab-friendly BRepNet fine-tuning scaffold."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_manifest(dataset_dir: Path) -> list[dict]:
    manifest_path = dataset_dir / "manifest.json"
    if not manifest_path.is_file():
        return []
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="SimReady Phase 2 BRepNet training scaffold")
    parser.add_argument("dataset_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--epochs", type=int, default=5)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest(args.dataset_dir)
    usable = [entry for entry in manifest if entry.get("status") == "ok"]

    summary = {
        "dataset_dir": str(args.dataset_dir),
        "output_dir": str(args.output_dir),
        "epochs": args.epochs,
        "usable_samples": len(usable),
        "note": "Training loop scaffold only. Plug real BRepNet model + dataloader here when GPU environment is ready.",
        "colab_ready": True,
    }
    (args.output_dir / "training_plan.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
