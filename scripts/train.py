#!/usr/bin/env python3
"""Train BRepSAGE on auto-labeled graph data.

Multi-task loss = BCEWithLogits(refinement) + MSE(complexity_proxy).
CPU-only by default — keep the model small enough that 5-10 epochs run in
under a minute on commodity hardware. A Colab-mountable notebook can wrap
the same scripts later if the dataset grows past ~5k graphs.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import torch
from torch.optim import Adam
from torch_geometric.loader import DataLoader

from simready.ml.dataset import load_dataset, split_train_val
from simready.ml.model import BRepSAGE, ModelConfig


def evaluate_split(model: BRepSAGE, loader: DataLoader, device: torch.device) -> dict[str, float]:
    model.eval()
    total_refinement_loss = 0.0
    total_complexity_loss = 0.0
    total_correct = 0
    total_faces = 0
    total_positives = 0
    total_predicted_positives = 0
    total_true_positives = 0
    bce = torch.nn.BCEWithLogitsLoss(reduction="sum")
    mse = torch.nn.MSELoss(reduction="sum")

    with torch.no_grad():
        for batch in loader:
            batch = batch.to(device)
            output = model(batch.x, batch.edge_index)
            total_refinement_loss += float(bce(output["refinement_logits"], batch.refinement_label))
            total_complexity_loss += float(mse(output["complexity_scores"], batch.complexity_label))
            preds = (output["refinement_probs"] > 0.5).float()
            total_correct += int((preds == batch.refinement_label).sum())
            total_faces += int(batch.refinement_label.numel())
            total_positives += int(batch.refinement_label.sum())
            total_predicted_positives += int(preds.sum())
            total_true_positives += int(((preds == 1) & (batch.refinement_label == 1)).sum())

    accuracy = total_correct / total_faces if total_faces else 0.0
    precision = total_true_positives / total_predicted_positives if total_predicted_positives else 0.0
    recall = total_true_positives / total_positives if total_positives else 0.0
    return {
        "refinement_loss": total_refinement_loss / max(1, total_faces),
        "complexity_loss": total_complexity_loss / max(1, total_faces),
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "positives": float(total_positives),
        "predicted_positives": float(total_predicted_positives),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("dataset_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--hidden-dim", type=int, default=32)
    parser.add_argument("--num-layers", type=int, default=2)
    parser.add_argument("--refinement-weight", type=float, default=1.0)
    parser.add_argument("--complexity-weight", type=float, default=1.0)
    parser.add_argument("--val-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=20260513)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(args.seed)

    dataset = load_dataset(args.dataset_dir)
    if not dataset:
        print(f"no labeled samples found in {args.dataset_dir}")
        return 1

    train_data, val_data = split_train_val(dataset, val_ratio=args.val_ratio, seed=args.seed)
    train_loader = DataLoader(train_data, batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(val_data, batch_size=args.batch_size)

    device = torch.device("cpu")
    config = ModelConfig(hidden_dim=args.hidden_dim, num_layers=args.num_layers)
    model = BRepSAGE(config).to(device)
    optimizer = Adam(model.parameters(), lr=args.lr)
    bce = torch.nn.BCEWithLogitsLoss()
    mse = torch.nn.MSELoss()

    history = []
    started = time.perf_counter()
    for epoch in range(1, args.epochs + 1):
        model.train()
        epoch_loss = 0.0
        for batch in train_loader:
            batch = batch.to(device)
            optimizer.zero_grad()
            output = model(batch.x, batch.edge_index)
            refinement_loss = bce(output["refinement_logits"], batch.refinement_label)
            complexity_loss = mse(output["complexity_scores"], batch.complexity_label)
            loss = args.refinement_weight * refinement_loss + args.complexity_weight * complexity_loss
            loss.backward()
            optimizer.step()
            epoch_loss += float(loss.detach()) * batch.num_graphs

        train_metrics = evaluate_split(model, train_loader, device)
        val_metrics = evaluate_split(model, val_loader, device)
        history.append({
            "epoch": epoch,
            "train_loss": epoch_loss / max(1, len(train_data)),
            "train": train_metrics,
            "val": val_metrics,
        })
        print(
            f"epoch {epoch:3d}  "
            f"train_loss={epoch_loss/max(1,len(train_data)):.4f}  "
            f"val_acc={val_metrics['accuracy']:.3f}  "
            f"val_precision={val_metrics['precision']:.3f}  "
            f"val_recall={val_metrics['recall']:.3f}  "
            f"val_complexity_mse={val_metrics['complexity_loss']:.4f}"
        )

    elapsed = time.perf_counter() - started

    checkpoint_path = args.output_dir / "brepnet.pt"
    metadata_path = args.output_dir / "brepnet_meta.json"
    torch.save(
        {
            "state_dict": model.state_dict(),
            "config": {
                "in_dim": config.in_dim,
                "hidden_dim": config.hidden_dim,
                "num_layers": config.num_layers,
                "dropout": config.dropout,
            },
        },
        checkpoint_path,
    )
    metadata_path.write_text(
        json.dumps(
            {
                "checkpoint": str(checkpoint_path),
                "epochs": args.epochs,
                "elapsed_seconds": elapsed,
                "train_samples": len(train_data),
                "val_samples": len(val_data),
                "history": history,
                "model_name": "BRepSAGE-multitask",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"saved checkpoint to {checkpoint_path}  (elapsed {elapsed:.1f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
