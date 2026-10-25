import copy
import math

import pytest
import torch
from torch_geometric.data import Data
from torch_geometric.loader import DataLoader

from simready.ml.defect_finetune import (
    build_fit_weighting,
    configure_defect_optimizer,
    evaluate_defect,
    finetune_defect_head,
    freeze_non_defect_parameters,
    load_brepsage_checkpoint,
)
from simready.ml.model import DEFECT_CLASSES, BRepSAGE, ModelConfig


def graph(label, source_id=None, feature=0.0):
    data = Data(
        x=torch.tensor([[feature] * ModelConfig().in_dim], dtype=torch.float32),
        edge_index=torch.empty((2, 0), dtype=torch.long),
        graph_label=torch.tensor([label], dtype=torch.long),
    )
    if source_id is not None:
        data.source_id = source_id
    return data


def synthetic_fit():
    return [graph(label, f"synthetic-{label}", feature=label + 1.0) for label in range(4)]


def real_fit():
    return [graph(0, "real-a", feature=0.1), graph(0, "real-b", feature=0.2)]


def small_model():
    torch.manual_seed(7)
    return BRepSAGE(ModelConfig(hidden_dim=4, num_layers=1, dropout=0.0))


def checkpoint(path, model=None):
    model = model or small_model()
    config = model.config
    torch.save(
        {
            "state_dict": model.state_dict(),
            "config": {
                "in_dim": config.in_dim,
                "hidden_dim": config.hidden_dim,
                "num_layers": config.num_layers,
                "dropout": config.dropout,
                "num_defect_classes": config.num_defect_classes,
            },
        },
        path,
    )


def test_load_brepsage_checkpoint_restores_config_and_weights(tmp_path):
    path = tmp_path / "brepnet.pt"
    expected = small_model()
    checkpoint(path, expected)

    actual = load_brepsage_checkpoint(path)

    assert isinstance(actual, BRepSAGE)
    assert actual.config == expected.config
    for name, tensor in expected.state_dict().items():
        assert torch.equal(actual.state_dict()[name], tensor)


def test_load_brepsage_checkpoint_missing_path_is_explicit(tmp_path):
    with pytest.raises(FileNotFoundError, match="missing.pt"):
        load_brepsage_checkpoint(tmp_path / "missing.pt")


def test_freeze_and_optimizer_include_only_defect_parameters():
    model = small_model()

    freeze_non_defect_parameters(model)
    optimizer = configure_defect_optimizer(model, lr=0.005)

    optimized = {parameter for group in optimizer.param_groups for parameter in group["params"]}
    assert optimized == set(model.defect_head.parameters())
    assert all(parameter.requires_grad for parameter in model.defect_head.parameters())
    assert all(not parameter.requires_grad for name, parameter in model.named_parameters() if not name.startswith("defect_head."))
    assert optimizer.param_groups[0]["lr"] == 0.005


def test_build_fit_weighting_orders_data_and_assigns_real_mass():
    synthetic = synthetic_fit()
    real = real_fit()

    combined, weights = build_fit_weighting(real, synthetic, real_mass=0.25)

    assert [data.source_id for data in combined] == [data.source_id for data in synthetic + real]
    assert weights == [1.0] * 4 + [0.5, 0.5]
    assert sum(weights[4:]) == pytest.approx(0.25 * len(synthetic))
    assert [data.is_real_clean for data in combined[4:]] == [True, True]
    assert all(not hasattr(data, "is_real_clean") for data in combined[:4])
    assert all(not hasattr(data, "is_real_clean") for data in real)


@pytest.mark.parametrize("mass", [0.0, -0.1, 1.1, math.nan, math.inf, True])
def test_build_fit_weighting_rejects_invalid_real_mass(mass):
    with pytest.raises(ValueError, match="real_mass"):
        build_fit_weighting(real_fit(), synthetic_fit(), real_mass=mass)


@pytest.mark.parametrize(
    ("real", "synthetic", "message"),
    [
        ([], synthetic_fit(), "real_fit"),
        (real_fit(), [], "synthetic_fit"),
        (real_fit(), synthetic_fit()[:-1], "all four"),
        ([graph(1), *real_fit()[1:]], synthetic_fit(), "clean"),
        (real_fit(), [graph(9), *synthetic_fit()[1:]], "graph_label"),
    ],
)
def test_build_fit_weighting_rejects_missing_or_mislabeled_data(real, synthetic, message):
    with pytest.raises(ValueError, match=message):
        build_fit_weighting(real, synthetic)


def test_training_is_deterministic_and_keeps_non_defect_tensors_identical():
    first = small_model()
    second = copy.deepcopy(first)

    history = finetune_defect_head(
        first,
        real_fit(),
        synthetic_fit(),
        synthetic_val=synthetic_fit(),
        epochs=2,
        lr=0.01,
        batch_size=3,
        seed=19,
    )
    repeated_history = finetune_defect_head(
        second,
        real_fit(),
        synthetic_fit(),
        synthetic_val=synthetic_fit(),
        epochs=2,
        lr=0.01,
        batch_size=3,
        seed=19,
    )

    assert history == repeated_history
    assert len(history) == 2
    assert [entry["epoch"] for entry in history] == [1, 2]
    assert all(set(entry) == {"epoch", "fit_loss", "synthetic_val"} for entry in history)
    for name, tensor in first.state_dict().items():
        assert torch.equal(tensor, second.state_dict()[name])


def test_training_leaves_frozen_unchanged_and_updates_only_defect_head():
    model = small_model()
    initial = copy.deepcopy(model.state_dict())

    history = finetune_defect_head(
        model,
        real_fit(),
        synthetic_fit(),
        synthetic_val=synthetic_fit(),
        epochs=1,
        lr=0.05,
        batch_size=2,
        seed=3,
    )

    for name, tensor in model.state_dict().items():
        if name.startswith("defect_head."):
            assert not torch.equal(tensor, initial[name])
        else:
            assert torch.equal(tensor, initial[name])
    assert history[0]["fit_loss"] > 0.0
    assert history[0]["synthetic_val"]["samples"] == 4


def test_training_detects_a_non_defect_tensor_change_after_optimizer_step(monkeypatch):
    model = small_model()
    original_step = torch.optim.Adam.step

    def corrupt_frozen_parameter(optimizer, *args, **kwargs):
        result = original_step(optimizer, *args, **kwargs)
        with torch.no_grad():
            model.convs[0].lin_l.weight.add_(1.0)
        return result

    monkeypatch.setattr(torch.optim.Adam, "step", corrupt_frozen_parameter)

    with pytest.raises(RuntimeError, match="non-defect"):
        finetune_defect_head(
            model,
            real_fit(),
            synthetic_fit(),
            synthetic_val=synthetic_fit(),
            epochs=1,
            lr=0.01,
            batch_size=2,
            seed=3,
        )


def test_training_evaluates_disjoint_synthetic_val_not_fit_data():
    model = small_model()
    fit = synthetic_fit()
    validation = [graph(0, "validation-only", feature=0.5)]

    history = finetune_defect_head(
        model,
        real_fit(),
        fit,
        synthetic_val=validation,
        epochs=1,
        lr=0.01,
        batch_size=2,
        seed=3,
    )

    assert history[0]["synthetic_val"]["samples"] == 1
    assert [row["source_id"] for row in history[0]["synthetic_val"]["predictions"]] == ["validation-only"]


@pytest.mark.parametrize(
    ("label", "message"),
    [
        (torch.tensor([1.0]), "integer"),
        (torch.tensor([1, 2]), "numel"),
        (torch.tensor([True]), "integer"),
    ],
)
def test_build_fit_weighting_rejects_non_scalar_or_non_integer_labels(label, message):
    real = real_fit()
    real[0].graph_label = label

    with pytest.raises(ValueError, match=message):
        build_fit_weighting(real, synthetic_fit())


@pytest.mark.parametrize("enabled", [False, True])
def test_training_restores_prior_deterministic_setting(enabled):
    previous = torch.are_deterministic_algorithms_enabled()
    torch.use_deterministic_algorithms(enabled)
    try:
        finetune_defect_head(
            small_model(),
            real_fit(),
            synthetic_fit(),
            synthetic_val=synthetic_fit(),
            epochs=1,
            lr=0.01,
            batch_size=2,
            seed=3,
        )
        assert torch.are_deterministic_algorithms_enabled() is enabled
    finally:
        torch.use_deterministic_algorithms(previous)


@pytest.mark.parametrize("enabled", [False, True])
def test_training_restores_deterministic_setting_after_exception(monkeypatch, enabled):
    previous = torch.are_deterministic_algorithms_enabled()
    torch.use_deterministic_algorithms(enabled)
    monkeypatch.setattr(torch.optim.Adam, "step", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("stop")))
    try:
        with pytest.raises(RuntimeError, match="stop"):
            finetune_defect_head(
                small_model(),
                real_fit(),
                synthetic_fit(),
                synthetic_val=synthetic_fit(),
                epochs=1,
                lr=0.01,
                batch_size=2,
                seed=3,
            )
        assert torch.are_deterministic_algorithms_enabled() is enabled
    finally:
        torch.use_deterministic_algorithms(previous)


def test_training_restores_warn_only_setting():
    previous = torch.are_deterministic_algorithms_enabled()
    previous_warn_only = torch.is_deterministic_algorithms_warn_only_enabled()
    torch.use_deterministic_algorithms(False, warn_only=True)
    try:
        finetune_defect_head(
            small_model(),
            real_fit(),
            synthetic_fit(),
            synthetic_val=synthetic_fit(),
            epochs=1,
            lr=0.01,
            batch_size=2,
            seed=3,
        )
        assert torch.are_deterministic_algorithms_enabled() is False
        assert torch.is_deterministic_algorithms_warn_only_enabled() is True
    finally:
        torch.use_deterministic_algorithms(previous, warn_only=previous_warn_only)


def test_training_restores_warn_only_setting_after_exception(monkeypatch):
    previous = torch.are_deterministic_algorithms_enabled()
    previous_warn_only = torch.is_deterministic_algorithms_warn_only_enabled()
    torch.use_deterministic_algorithms(False, warn_only=True)
    monkeypatch.setattr(torch.optim.Adam, "step", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("stop")))
    try:
        with pytest.raises(RuntimeError, match="stop"):
            finetune_defect_head(
                small_model(),
                real_fit(),
                synthetic_fit(),
                synthetic_val=synthetic_fit(),
                epochs=1,
                lr=0.01,
                batch_size=2,
                seed=3,
            )
        assert torch.are_deterministic_algorithms_enabled() is False
        assert torch.is_deterministic_algorithms_warn_only_enabled() is True
    finally:
        torch.use_deterministic_algorithms(previous, warn_only=previous_warn_only)


def test_consecutive_one_epoch_calls_match_one_two_epoch_call():
    continuous = small_model()
    continuous.dropout.p = 0.25
    split = copy.deepcopy(continuous)
    validation = synthetic_fit()

    continuous_history = finetune_defect_head(
        continuous,
        real_fit(),
        synthetic_fit(),
        synthetic_val=validation,
        epochs=2,
        lr=0.01,
        batch_size=3,
        seed=19,
    )
    first_history = finetune_defect_head(
        split,
        real_fit(),
        synthetic_fit(),
        synthetic_val=validation,
        epochs=1,
        lr=0.01,
        batch_size=3,
        seed=19,
    )
    second_history = finetune_defect_head(
        split,
        real_fit(),
        synthetic_fit(),
        synthetic_val=validation,
        epochs=1,
        lr=0.01,
        batch_size=3,
        seed=19,
    )

    for name, tensor in continuous.state_dict().items():
        assert torch.equal(tensor, split.state_dict()[name])
    assert first_history[0]["synthetic_val"] == continuous_history[0]["synthetic_val"]
    assert second_history[0]["synthetic_val"] == continuous_history[1]["synthetic_val"]


class FixedPredictionModel(torch.nn.Module):
    def forward(self, x, edge_index, batch=None):
        predictions = x[:, 0].long()
        probabilities = torch.zeros((x.size(0), len(DEFECT_CLASSES)))
        probabilities[torch.arange(x.size(0)), predictions] = 1.0
        return {"defect_probs": probabilities}


def test_evaluate_defect_exact_class_metrics_with_uneven_batches():
    data = [
        graph(0, "clean-correct-a", feature=0),
        graph(0, "clean-correct-b", feature=0),
        graph(1, "open-correct", feature=1),
        graph(1, "open-confused", feature=2),
        graph(3, "self-confused", feature=2),
    ]

    result = evaluate_defect(FixedPredictionModel(), data, batch_size=2)

    assert result["samples"] == 5
    assert result["accuracy"] == pytest.approx(3 / 5)
    assert result["per_class_samples"] == {
        "clean": 2,
        "open_shell": 2,
        "sliver_face": 0,
        "self_intersection": 1,
    }
    assert result["per_class_accuracy"] == {
        "clean": 1.0,
        "open_shell": 0.5,
        "sliver_face": None,
        "self_intersection": 0.0,
    }
    assert [row["prediction"] for row in result["predictions"]] == [
        "clean",
        "clean",
        "open_shell",
        "sliver_face",
        "sliver_face",
    ]


@pytest.mark.parametrize(
    ("label", "message"),
    [
        (torch.tensor([-1]), "range"),
        (torch.tensor([4]), "range"),
        (torch.tensor([1.0]), "integer"),
        (torch.tensor([1, 2]), "numel"),
    ],
)
def test_evaluate_defect_rejects_invalid_targets_before_model(label, message):
    class NoForwardModel(torch.nn.Module):
        def forward(self, *args, **kwargs):
            raise AssertionError("model must not run for invalid targets")

    data = graph(0)
    data.graph_label = label

    with pytest.raises(ValueError, match=message):
        evaluate_defect(NoForwardModel(), [data])


def test_evaluate_defect_reports_metrics_and_per_graph_predictions():
    model = small_model()
    data = synthetic_fit()
    loader = DataLoader(data, batch_size=3, shuffle=False)

    result = evaluate_defect(model, data, batch_size=3)
    expected_logits = []
    with torch.no_grad():
        model.eval()
        for batch in loader:
            expected_logits.extend(model(batch.x, batch.edge_index, batch.batch)["defect_logits"])

    assert result["samples"] == 4
    assert result["per_class_samples"] == {name: 1 for name in DEFECT_CLASSES}
    assert result["accuracy"] == pytest.approx(
        sum(row["target"] == row["prediction"] for row in result["predictions"]) / 4
    )
    assert set(result) == {"samples", "accuracy", "per_class_accuracy", "per_class_samples", "predictions"}
    assert set(result["per_class_accuracy"]) == set(DEFECT_CLASSES)
    for index, (row, logits) in enumerate(zip(result["predictions"], expected_logits)):
        probabilities = torch.softmax(logits, dim=-1)
        prediction = int(probabilities.argmax())
        assert row["source_id"] == f"synthetic-{index}"
        assert row["target"] == DEFECT_CLASSES[index]
        assert row["prediction"] == DEFECT_CLASSES[prediction]
        assert row["confidence"] == pytest.approx(float(probabilities[prediction]))
        assert row["probabilities"] == pytest.approx(
            {name: float(probabilities[i]) for i, name in enumerate(DEFECT_CLASSES)}
        )
