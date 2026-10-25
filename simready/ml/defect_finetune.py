"""CPU-only defect-head fine-tuning with verified real clean negatives."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path

import torch
from torch import nn
from torch.optim import Adam
from torch.utils.data import WeightedRandomSampler
from torch_geometric.data import Data
from torch_geometric.loader import DataLoader

from simready.ml.model import DEFECT_CLASSES, BRepSAGE, ModelConfig


def load_brepsage_checkpoint(path: str | Path) -> BRepSAGE:
    """Load a BRepSAGE checkpoint, preserving its stored model configuration."""
    checkpoint_path = Path(path)
    if not checkpoint_path.is_file():
        raise FileNotFoundError(f"BRepSAGE checkpoint not found: {checkpoint_path}")
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    model = BRepSAGE(ModelConfig(**checkpoint["config"]))
    model.load_state_dict(checkpoint["state_dict"])
    return model


def freeze_non_defect_parameters(model: BRepSAGE) -> None:
    """Disable gradients everywhere except the graph-level defect head."""
    for name, parameter in model.named_parameters():
        parameter.requires_grad = name.startswith("defect_head.")


def configure_defect_optimizer(model: BRepSAGE, lr: float) -> Adam:
    """Configure Adam over defect-head parameters only."""
    return Adam(model.defect_head.parameters(), lr=lr)


def _graph_label(data: Data) -> int:
    try:
        label = data.graph_label
    except AttributeError as error:
        raise ValueError("every sample must have one integer graph_label") from error
    if not isinstance(label, torch.Tensor) or label.numel() != 1:
        raise ValueError("graph_label must have numel == 1")
    if label.dtype not in (torch.uint8, torch.int8, torch.int16, torch.int32, torch.int64):
        raise ValueError("graph_label must have integer dtype")
    return int(label.item())


def build_fit_weighting(
    real_fit: list[Data],
    synthetic_fit: list[Data],
    real_mass: float = 0.25,
) -> tuple[list[Data], list[float]]:
    """Combine synthetic and clean-real data with replacement-sampling weights."""
    if not real_fit:
        raise ValueError("real_fit must not be empty")
    if not synthetic_fit:
        raise ValueError("synthetic_fit must not be empty")
    if (
        isinstance(real_mass, bool)
        or not isinstance(real_mass, (int, float))
        or not math.isfinite(real_mass)
        or not 0.0 < real_mass <= 1.0
    ):
        raise ValueError("real_mass must be finite and in the interval (0, 1]")

    synthetic_labels = [_graph_label(data) for data in synthetic_fit]
    if any(label not in range(len(DEFECT_CLASSES)) for label in synthetic_labels):
        raise ValueError("synthetic_fit graph_label values must be valid defect classes")
    if set(synthetic_labels) != set(range(len(DEFECT_CLASSES))):
        raise ValueError("synthetic_fit must contain all four defect classes")
    if any(_graph_label(data) != 0 for data in real_fit):
        raise ValueError("every real_fit sample must have the clean graph_label 0")

    combined = list(synthetic_fit)
    for data in real_fit:
        tagged = data.clone()
        tagged.is_real_clean = True
        combined.append(tagged)
    real_weight = real_mass * len(synthetic_fit) / len(real_fit)
    return combined, [1.0] * len(synthetic_fit) + [real_weight] * len(real_fit)


def evaluate_defect(
    model: BRepSAGE,
    data: list[Data],
    batch_size: int = 16,
) -> dict[str, object]:
    """Evaluate graph-level defect predictions without changing model weights."""
    if not data:
        raise ValueError("data must not be empty")
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    for sample in data:
        target = _graph_label(sample)
        if not 0 <= target < len(DEFECT_CLASSES):
            raise ValueError(f"evaluation graph_label out of range [0, {len(DEFECT_CLASSES)}): {target}")

    model = model.to("cpu")
    model.eval()
    loader = DataLoader(data, batch_size=batch_size, shuffle=False)
    predictions = []
    class_correct = [0] * len(DEFECT_CLASSES)
    class_samples = [0] * len(DEFECT_CLASSES)

    with torch.no_grad():
        for batch in loader:
            output = model(batch.x, batch.edge_index, batch=batch.batch)
            probabilities = output["defect_probs"]
            predicted = probabilities.argmax(dim=-1)
            targets = batch.graph_label.view(-1)
            source_ids = getattr(batch, "source_id", None)
            if source_ids is None:
                source_ids = getattr(batch, "stem", [str(index) for index in range(len(targets))])
            for index, (target_tensor, prediction_tensor) in enumerate(zip(targets, predicted)):
                target = int(target_tensor)
                prediction = int(prediction_tensor)
                class_samples[target] += 1
                class_correct[target] += int(target == prediction)
                row_probabilities = probabilities[index]
                predictions.append(
                    {
                        "source_id": str(source_ids[index]),
                        "target": DEFECT_CLASSES[target],
                        "prediction": DEFECT_CLASSES[prediction],
                        "confidence": float(row_probabilities[prediction]),
                        "probabilities": {
                            name: float(row_probabilities[class_index])
                            for class_index, name in enumerate(DEFECT_CLASSES)
                        },
                    }
                )

    correct = sum(row["target"] == row["prediction"] for row in predictions)
    return {
        "samples": len(predictions),
        "accuracy": correct / len(predictions),
        "per_class_accuracy": {
            name: class_correct[index] / class_samples[index] if class_samples[index] else None
            for index, name in enumerate(DEFECT_CLASSES)
        },
        "per_class_samples": {
            name: class_samples[index] for index, name in enumerate(DEFECT_CLASSES)
        },
        "predictions": predictions,
    }


def checkpoint_sha256(path: str | Path) -> str:
    """Hash exact checkpoint bytes after requiring an explicit existing file."""
    checkpoint_path = Path(path)
    if not checkpoint_path.is_file():
        raise FileNotFoundError(f"BRepSAGE checkpoint not found: {checkpoint_path}")
    return hashlib.sha256(checkpoint_path.read_bytes()).hexdigest()


def compare_checkpoints(
    baseline_path: str | Path,
    candidate_path: str | Path,
    real_data: list[Data],
    synthetic_val: list[Data],
) -> dict[str, dict[str, object]]:
    """Compare two explicit checkpoints on synthetic val and real holdout only."""
    if not real_data:
        raise ValueError("real_data must not be empty")
    if not synthetic_val:
        raise ValueError("synthetic_val must not be empty")
    if any(getattr(data, "split", None) != "final_holdout" for data in real_data):
        raise ValueError("real_data must contain only final_holdout samples")

    result = {}
    for name, path in (("baseline", baseline_path), ("candidate", candidate_path)):
        model = load_brepsage_checkpoint(path)
        real_metrics = evaluate_defect(model, real_data)
        result[name] = {
            "path": str(path),
            "sha256": checkpoint_sha256(path),
            "synthetic_val": evaluate_defect(model, synthetic_val),
            "real_holdout": {"split": "final_holdout", **real_metrics},
        }
    return result


def _assert_frozen_tensors_unchanged(
    model: BRepSAGE,
    initial: dict[str, torch.Tensor],
) -> None:
    for name, tensor in initial.items():
        if not torch.equal(dict(model.named_parameters())[name], tensor):
            raise RuntimeError(f"non-defect parameter changed during fine-tuning: {name}")


def _epoch_steps(sample_count: int, batch_size: int) -> int:
    return math.ceil(sample_count / batch_size)


def _training_epoch_start(model: BRepSAGE, seed: int) -> int:
    cursor = getattr(model, "_defect_finetune_rng_cursor", None)
    if cursor is not None and cursor["seed"] == seed:
        return cursor["epoch"]
    return 0


def _save_training_epoch(
    model: BRepSAGE,
    seed: int,
    epoch: int,
    optimizer: Adam,
) -> None:
    model._defect_finetune_rng_cursor = {
        "seed": seed,
        "epoch": epoch,
        "optimizer_state": optimizer.state_dict(),
    }


def finetune_defect_head(
    model: BRepSAGE,
    real_fit: list[Data],
    synthetic_fit: list[Data],
    *,
    synthetic_val: list[Data],
    epochs: int,
    lr: float,
    batch_size: int,
    seed: int,
    real_mass: float = 0.25,
) -> list[dict[str, object]]:
    """Fine-tune only the defect head using cross-entropy loss on CPU."""
    if epochs <= 0:
        raise ValueError("epochs must be positive")
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")

    previous_deterministic = torch.are_deterministic_algorithms_enabled()
    previous_warn_only = torch.is_deterministic_algorithms_warn_only_enabled()
    previous_rng_state = torch.get_rng_state()
    torch.use_deterministic_algorithms(True)
    start_epoch = _training_epoch_start(model, seed)
    sampler_generator = torch.Generator()
    try:
        model = model.to("cpu")
        freeze_non_defect_parameters(model)
        optimizer = configure_defect_optimizer(model, lr=lr)
        cursor = getattr(model, "_defect_finetune_rng_cursor", None)
        if cursor is not None and cursor["seed"] == seed:
            optimizer.load_state_dict(cursor["optimizer_state"])
        frozen = {
            name: parameter.detach().clone()
            for name, parameter in model.named_parameters()
            if not name.startswith("defect_head.")
        }
        combined, weights = build_fit_weighting(real_fit, synthetic_fit, real_mass=real_mass)
        sample_count = len(synthetic_fit) + math.ceil(real_mass * len(synthetic_fit))
        sampler = WeightedRandomSampler(
            weights,
            num_samples=sample_count,
            replacement=True,
            generator=sampler_generator,
        )
        loader = DataLoader(
            combined,
            batch_size=batch_size,
            sampler=sampler,
            exclude_keys=["is_real_clean", "family_id", "split"],
        )
        criterion = nn.CrossEntropyLoss()
        history = []

        for epoch in range(start_epoch + 1, start_epoch + epochs + 1):
            sampler_generator.manual_seed(seed + epoch - 1)
            model.train()
            total_loss = 0.0
            total_samples = 0
            for step, batch in enumerate(loader):
                optimizer.zero_grad()
                torch.manual_seed(seed + (epoch - 1) * _epoch_steps(sample_count, batch_size) + step)
                output = model(batch.x, batch.edge_index, batch=batch.batch)
                loss = criterion(output["defect_logits"], batch.graph_label.view(-1))
                loss.backward()
                optimizer.step()
                _assert_frozen_tensors_unchanged(model, frozen)
                total_loss += float(loss.detach()) * batch.num_graphs
                total_samples += batch.num_graphs
            history.append(
                {
                    "epoch": epoch,
                    "fit_loss": total_loss / total_samples,
                    "synthetic_val": evaluate_defect(model, synthetic_val, batch_size=batch_size),
                }
            )
        _save_training_epoch(model, seed, start_epoch + epochs, optimizer)
        return history
    finally:
        torch.set_rng_state(previous_rng_state)
        torch.use_deterministic_algorithms(previous_deterministic, warn_only=previous_warn_only)
