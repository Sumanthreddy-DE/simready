import hashlib

import pytest
import torch
from torch_geometric.data import Data

from simready.ml.defect_finetune import compare_checkpoints
from simready.ml.model import DEFECT_CLASSES, BRepSAGE, ModelConfig


class ForcedDefectModel(torch.nn.Module):
    def __init__(self, prediction):
        super().__init__()
        self.prediction = prediction

    def forward(self, x, edge_index, batch=None):
        graph_count = 1 if batch is None else int(batch.max()) + 1
        probabilities = torch.zeros((graph_count, len(DEFECT_CLASSES)))
        probabilities[:, self.prediction] = 1.0
        return {"defect_probs": probabilities}


def graph(label, source_id, split=None):
    data = Data(
        x=torch.zeros((1, ModelConfig().in_dim), dtype=torch.float32),
        edge_index=torch.empty((2, 0), dtype=torch.long),
        graph_label=torch.tensor([label], dtype=torch.long),
        source_id=source_id,
    )
    if split is not None:
        data.split = split
    return data


def checkpoint(path, prediction):
    model = BRepSAGE(ModelConfig(hidden_dim=4, num_layers=1))
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
            "forced_prediction": prediction,
        },
        path,
    )


@pytest.fixture
def forced_checkpoints(monkeypatch):
    def load_forced(path):
        payload = torch.load(path, map_location="cpu", weights_only=True)
        return ForcedDefectModel(payload["forced_prediction"])

    monkeypatch.setattr("simready.ml.defect_finetune.load_brepsage_checkpoint", load_forced)


def holdout():
    return [graph(0, "real-holdout-a", "final_holdout"), graph(0, "real-holdout-b", "final_holdout")]


def synthetic_val():
    return [graph(label, f"synthetic-{label}") for label in range(4)]


def test_compare_checkpoints_hashes_paths_and_evaluates_each_model_independently(tmp_path, forced_checkpoints):
    baseline_path = tmp_path / "baseline.pt"
    candidate_path = tmp_path / "candidate.pt"
    checkpoint(baseline_path, 0)
    checkpoint(candidate_path, 1)

    result = compare_checkpoints(baseline_path, candidate_path, holdout(), synthetic_val())

    assert result["baseline"]["path"] == str(baseline_path)
    assert result["candidate"]["path"] == str(candidate_path)
    for name, path in (("baseline", baseline_path), ("candidate", candidate_path)):
        assert result[name]["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
        assert result[name]["synthetic_val"]["samples"] == 4
        assert result[name]["real_holdout"]["split"] == "final_holdout"
        assert result[name]["real_holdout"]["samples"] == 2
    assert [row["prediction"] for row in result["baseline"]["real_holdout"]["predictions"]] == ["clean", "clean"]
    assert [row["prediction"] for row in result["candidate"]["real_holdout"]["predictions"]] == ["open_shell"] * 2
    assert [row["source_id"] for row in result["candidate"]["real_holdout"]["predictions"]] == [
        "real-holdout-a",
        "real-holdout-b",
    ]
    assert result["baseline"]["synthetic_val"]["accuracy"] == 0.25
    assert result["candidate"]["synthetic_val"]["accuracy"] == 0.25


def test_compare_checkpoints_requires_explicit_checkpoint_paths(tmp_path, forced_checkpoints):
    for name in ("baseline", "candidate"):
        case_dir = tmp_path / name
        case_dir.mkdir()
        baseline_path = case_dir / "baseline.pt"
        candidate_path = case_dir / "candidate.pt"
        checkpoint(baseline_path if name == "candidate" else candidate_path, 0)
        with pytest.raises(FileNotFoundError, match=f"{name}.pt"):
            compare_checkpoints(baseline_path, candidate_path, holdout(), synthetic_val())


@pytest.mark.parametrize("empty_side", ["real", "synthetic"])
def test_compare_checkpoints_rejects_empty_evaluation_data(tmp_path, forced_checkpoints, empty_side):
    baseline = tmp_path / "baseline.pt"
    candidate = tmp_path / "candidate.pt"
    checkpoint(baseline, 0)
    checkpoint(candidate, 0)
    real = [] if empty_side == "real" else holdout()
    synthetic = [] if empty_side == "synthetic" else synthetic_val()

    with pytest.raises(ValueError, match="must not be empty"):
        compare_checkpoints(baseline, candidate, real, synthetic)


def test_compare_checkpoints_rejects_real_fit_to_prevent_holdout_ambiguity(tmp_path, forced_checkpoints):
    baseline = tmp_path / "baseline.pt"
    candidate = tmp_path / "candidate.pt"
    checkpoint(baseline, 0)
    checkpoint(candidate, 0)

    with pytest.raises(ValueError, match="final_holdout"):
        compare_checkpoints(baseline, candidate, [graph(0, "fit", "real_fit")], synthetic_val())
