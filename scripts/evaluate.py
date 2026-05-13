#!/usr/bin/env python3
"""Evaluate a BRepSAGE checkpoint against a labeled dataset.

Reports per-face accuracy, precision, recall, F1 for the refinement head and
MSE / MAE for the complexity head. Writes a JSON summary plus per-sample
predictions for inspection.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
from torch_geometric.loader import DataLoader

from simready.ml.dataset import load_dataset
from simready.ml.model import BRepSAGE, ModelConfig


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("dataset_dir", type=Path)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--output", type=Path, default=Path("evaluation.json"))
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args()

    checkpoint = torch.load(str(args.checkpoint), map_location="cpu", weights_only=False)
    config = ModelConfig(**checkpoint.get("config", {}))
    model = BRepSAGE(config)
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()

    dataset = load_dataset(args.dataset_dir)
    if not dataset:
        print(f"no labeled samples found in {args.dataset_dir}")
        return 1

    loader = DataLoader(dataset, batch_size=args.batch_size)
    total_correct = 0
    total_faces = 0
    total_positives = 0
    total_predicted_positives = 0
    total_true_positives = 0
    total_complexity_sq = 0.0
    total_complexity_abs = 0.0
    per_sample: list[dict] = []

    with torch.no_grad():
        for batch in loader:
            output = model(batch.x, batch.edge_index)
            probs = output["refinement_probs"]
            preds = (probs > args.threshold).float()
            total_correct += int((preds == batch.refinement_label).sum())
            total_faces += int(batch.refinement_label.numel())
            total_positives += int(batch.refinement_label.sum())
            total_predicted_positives += int(preds.sum())
            total_true_positives += int(((preds == 1) & (batch.refinement_label == 1)).sum())
            diff = output["complexity_scores"] - batch.complexity_label
            total_complexity_sq += float((diff * diff).sum())
            total_complexity_abs += float(diff.abs().sum())

    accuracy = total_correct / total_faces if total_faces else 0.0
    precision = total_true_positives / total_predicted_positives if total_predicted_positives else 0.0
    recall = total_true_positives / total_positives if total_positives else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    mse = total_complexity_sq / max(1, total_faces)
    mae = total_complexity_abs / max(1, total_faces)

    summary = {
        "dataset_dir": str(args.dataset_dir),
        "checkpoint": str(args.checkpoint),
        "samples": len(dataset),
        "total_faces": total_faces,
        "refinement": {
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "positives": total_positives,
            "predicted_positives": total_predicted_positives,
            "true_positives": total_true_positives,
        },
        "complexity": {"mse": mse, "mae": mae},
    }
    args.output.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(
        f"samples={len(dataset)}  faces={total_faces}  "
        f"acc={accuracy:.3f}  precision={precision:.3f}  recall={recall:.3f}  f1={f1:.3f}  "
        f"complexity_mse={mse:.4f}  complexity_mae={mae:.4f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
