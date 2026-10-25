import json
from pathlib import Path

import pytest
import torch

from scripts.finetune_defect_real_clean import CONFIG, code_provenance, main, train_experiment
from simready.ml.defect_finetune import load_brepsage_checkpoint
from simready.ml.model import DEFECT_CLASSES, BRepSAGE, ModelConfig


def graph(label, source_id, family_id=None, split=None):
    from torch_geometric.data import Data

    data = Data(
        x=torch.full((1, ModelConfig().in_dim), float(label + 1)),
        edge_index=torch.empty((2, 0), dtype=torch.long),
        graph_label=torch.tensor([label]),
        source_id=source_id,
        stem=source_id,
    )
    if family_id is not None:
        data.family_id = family_id
    if split is not None:
        data.split = split
    return data


def save_checkpoint(path):
    torch.manual_seed(7)
    model = BRepSAGE(ModelConfig(hidden_dim=4, num_layers=1, dropout=0.0))
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


def synthetic_samples():
    samples = []
    for source_index in range(6):
        for label in range(4):
            samples.append(graph(label, f"part-{source_index}__{DEFECT_CLASSES[label]}"))
    return samples


def real_samples(split):
    return [graph(0, f"real-{split}", f"family-{split}", split)]


@pytest.fixture
def experiment(tmp_path, monkeypatch):
    baseline = tmp_path / "weights" / "brepnet.pt"
    baseline.parent.mkdir()
    save_checkpoint(baseline)
    synthetic = tmp_path / "synthetic"
    real = tmp_path / "real"
    output = tmp_path / "output"
    synthetic.mkdir()
    (synthetic / "manifest.json").write_text("[]", encoding="utf-8")
    real.mkdir()
    (real / "manifest.json").write_text(json.dumps([
        {
            "stem": "real-real_fit", "source_id": "real-real_fit", "source_sha256": "a" * 64,
            "graph_sha256": "b" * 64, "labels_sha256": "c" * 64,
        },
    ]), encoding="utf-8")
    monkeypatch.setattr("scripts.finetune_defect_real_clean.load_dataset", lambda path: synthetic_samples())
    monkeypatch.setattr(
        "scripts.finetune_defect_real_clean.load_real_clean_split",
        lambda path, split: real_samples(split),
    )
    return baseline, synthetic, real, output


def test_fixed_training_config_cannot_be_tuned_from_cli():
    assert CONFIG == {
        "seed": 20260513,
        "epochs": 10,
        "lr": 1e-4,
        "batch_size": 16,
        "val_ratio": 0.2,
        "real_mass": 0.25,
    }
    with pytest.raises(SystemExit):
        main(["--epochs", "1"])


def test_training_writes_one_shot_candidate_and_exact_provenance(experiment, monkeypatch):
    baseline, synthetic, real, output = experiment
    holdout_calls = []
    monkeypatch.setattr(
        "scripts.finetune_defect_real_clean.load_real_clean_split",
        lambda path, split: holdout_calls.append(split) or real_samples(split),
    )
    assert main([
        "--baseline", str(baseline),
        "--synthetic", str(synthetic),
        "--real", str(real),
        "--output", str(output),
    ]) == 0

    assert sorted(path.name for path in output.iterdir()) == [
        "candidate.pt", "config.json", "history.json", "synthetic_split.json"
    ]
    config = json.loads((output / "config.json").read_text(encoding="utf-8"))
    split = json.loads((output / "synthetic_split.json").read_text(encoding="utf-8"))
    history = json.loads((output / "history.json").read_text(encoding="utf-8"))
    initial = load_brepsage_checkpoint(baseline)
    candidate = load_brepsage_checkpoint(output / "candidate.pt")
    evidence = {
        name: torch.equal(candidate.state_dict()[name], initial.state_dict()[name])
        for name in initial.state_dict()
        if not name.startswith("defect_head.")
    }
    assert all(evidence.values())
    assert config["config"] == CONFIG
    assert config["baseline_sha256"]
    import hashlib
    assert config["candidate_sha256"] == hashlib.sha256((output / "candidate.pt").read_bytes()).hexdigest()
    assert config["synthetic_split_sha256"] == hashlib.sha256((output / "synthetic_split.json").read_bytes()).hexdigest()
    assert config["history_sha256"] == hashlib.sha256((output / "history.json").read_bytes()).hexdigest()
    assert config["synthetic_artifacts"]["manifest.json"]
    assert config["real_artifacts"]["manifest.json"]
    assert config["real_artifacts"]["real-real_fit.graph.json"] == "b" * 64
    assert config["real_source_provenance"] == {"real-real_fit": "a" * 64}
    assert config["code_revision"]
    assert isinstance(config["tree_dirty"], bool)
    assert config["code_provenance"]["commit_reproduces_code"] is (not config["tree_dirty"])
    assert config["code_provenance"]["source_files"]
    assert all(len(row["sha256"]) == 64 for row in config["code_provenance"]["source_files"].values())
    if config["tree_dirty"]:
        assert len(config["code_provenance"]["tracked_diff_sha256"]) == 64
    assert config["real_fit_source_ids"] == ["real-real_fit"]
    assert config["real_fit_families"] == ["family-real_fit"]
    assert config["non_defect_baseline_candidate_equal"] == evidence
    assert set(split) == {"seed", "val_ratio", "fit", "val"}
    assert len(split["fit"]) + len(split["val"]) == 24
    assert {row["source_id"] for row in split["fit"]}.isdisjoint(row["source_id"] for row in split["val"])
    assert {row["source_group"] for row in split["fit"]}.isdisjoint(row["source_group"] for row in split["val"])
    assert len(history) == 10
    assert holdout_calls == ["real_fit"]
    assert not any("holdout" in path.name for path in output.iterdir())


def test_cli_loads_prepared_real_schema_and_skips_non_sample_synthetic_manifest_rows(tmp_path, monkeypatch):
    from tests.test_real_clean import _real_entries, _write_real_dataset

    baseline = tmp_path / "weights" / "brepnet.pt"
    baseline.parent.mkdir()
    save_checkpoint(baseline)
    synthetic = tmp_path / "synthetic"
    synthetic.mkdir()
    synthetic_entries = [{"input_file": "missing.step", "status": "skipped", "reason": "validation_failed"}]
    for sample in synthetic_samples():
        stem = sample.stem
        graph_payload = {
            "node_features": [{"face_index": 0, "surface_type": "plane", "area": 1.0, "normal": [0, 0, 1]}],
            "adjacency": [],
        }
        labels_payload = {
            "graph_label": int(sample.graph_label),
            "refinement": {},
            "complexity_proxy": {},
        }
        (synthetic / f"{stem}.graph.json").write_text(json.dumps(graph_payload), encoding="utf-8")
        (synthetic / f"{stem}.labels.json").write_text(json.dumps(labels_payload), encoding="utf-8")
        synthetic_entries.append({"status": "ok", "stem": stem, "face_count": 1})
    (synthetic / "manifest.json").write_text(json.dumps(synthetic_entries), encoding="utf-8")

    real = tmp_path / "real"
    real.mkdir()
    _write_real_dataset(real, _real_entries())
    output = tmp_path / "output"
    holdout_prefix = "family-b__variant"
    original_read_bytes = Path.read_bytes
    original_read_text = Path.read_text

    def guarded_read_bytes(path, *args, **kwargs):
        assert not path.name.startswith(holdout_prefix), f"holdout artifact read: {path}"
        return original_read_bytes(path, *args, **kwargs)

    def guarded_read_text(path, *args, **kwargs):
        assert not path.name.startswith(holdout_prefix), f"holdout artifact read: {path}"
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", guarded_read_bytes)
    monkeypatch.setattr(Path, "read_text", guarded_read_text)

    assert main([
        "--baseline", str(baseline),
        "--synthetic", str(synthetic),
        "--real", str(real),
        "--output", str(output),
    ]) == 0

    config = json.loads((output / "config.json").read_text(encoding="utf-8"))
    assert config["real_fit_source_ids"] == ["family-a__variant"]
    assert config["real_fit_families"] == ["family-a"]
    assert config["real_holdout_evaluated"] is False
    assert not any(name.startswith("missing.step") for name in config["synthetic_artifacts"])


def test_code_provenance_records_dirty_diff_and_hashes_untracked_sources(tmp_path, monkeypatch):
    import hashlib
    from types import SimpleNamespace

    source = tmp_path / "training.py"
    source.write_bytes(b"uncommitted implementation")
    monkeypatch.setattr("scripts.finetune_defect_real_clean.PROVENANCE_SOURCE_PATHS", (source,))
    commands = []

    def git_output(args):
        commands.append(args)
        return {
            ("rev-parse", "HEAD"): "abc123",
            ("status", "--porcelain"): " M simready/ml/dataset.py\n?? scripts/finetune_defect_real_clean.py",
            ("status", "--porcelain", "--", str(source)): f"?? {source.name}",
            ("diff", "--binary", "HEAD", "--"): b"tracked patch bytes",
        }[tuple(args)]

    monkeypatch.setattr("scripts.finetune_defect_real_clean._git_output", git_output)

    result = code_provenance()

    assert result["code_revision"] == "abc123"
    assert result["tree_dirty"] is True
    assert result["code_provenance"] == {
        "commit_reproduces_code": False,
        "note": "Working tree differs from code_revision; use source hashes and tracked diff hash as dirty-code evidence.",
        "tracked_diff_sha256": hashlib.sha256(b"tracked patch bytes").hexdigest(),
        "source_files": {
            str(source): {
                "sha256": hashlib.sha256(b"uncommitted implementation").hexdigest(),
                "git_status": "untracked",
            }
        },
    }


def test_code_provenance_marks_clean_commit_as_reproducing_implementation(tmp_path, monkeypatch):
    source = tmp_path / "training.py"
    source.write_bytes(b"committed implementation")
    monkeypatch.setattr("scripts.finetune_defect_real_clean.PROVENANCE_SOURCE_PATHS", (source,))
    monkeypatch.setattr(
        "scripts.finetune_defect_real_clean._git_output",
        lambda args: {"rev-parse": "abc123", "status": "", "diff": b""}.get(args[0], b""),
    )

    result = code_provenance()

    assert result["tree_dirty"] is False
    assert result["code_provenance"]["commit_reproduces_code"] is True
    assert "tracked_diff_sha256" not in result["code_provenance"]


def test_training_refuses_existing_output_without_overwriting(experiment):
    baseline, synthetic, real, output = experiment
    output.mkdir()
    marker = output / "candidate.pt"
    marker.write_text("keep", encoding="utf-8")

    with pytest.raises(FileExistsError, match="output"):
        train_experiment(baseline, synthetic, real, output)

    assert marker.read_text(encoding="utf-8") == "keep"


def test_training_never_overwrites_production_baseline(experiment):
    baseline, synthetic, real, _output = experiment

    with pytest.raises(ValueError, match="production"):
        train_experiment(baseline, synthetic, real, baseline.parent)
