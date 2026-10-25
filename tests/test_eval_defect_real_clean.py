import json

import pytest
import torch

from scripts.eval_defect_real_clean import _recorded_synthetic_val, _validate_inspection, evaluate_experiment, main
from scripts.finetune_defect_real_clean import CONFIG as TRAINING_CONFIG
from simready.ml.artifact_provenance import artifact_hashes
from simready.ml.defect_finetune import checkpoint_sha256, load_brepsage_checkpoint
from simready.ml.model import BRepSAGE, ModelConfig


def graph(label, source_id, split):
    from torch_geometric.data import Data
    import torch

    return Data(
        x=torch.zeros((1, ModelConfig().in_dim)),
        edge_index=torch.empty((2, 0), dtype=torch.long),
        graph_label=torch.tensor([label]),
        source_id=source_id,
        split=split,
    )


def checkpoint(path):
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
        },
        path,
    )


def synthetic_val():
    return [graph(label, f"synthetic-{label}", "val") for label in range(4)]


def prediction_metrics(predictions):
    correct = sum(row == "clean" for row in predictions)
    return {
        "samples": len(predictions),
        "accuracy": correct / len(predictions),
        "per_class_accuracy": {"clean": correct / len(predictions)},
        "per_class_samples": {"clean": len(predictions)},
        "predictions": [
            {"source_id": f"row-{index}", "target": "clean", "prediction": row}
            for index, row in enumerate(predictions)
        ],
    }


@pytest.fixture
def evaluation(tmp_path, monkeypatch):
    baseline = tmp_path / "baseline.pt"
    candidate = tmp_path / "candidate.pt"
    checkpoint(baseline)
    checkpoint(candidate)
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    (real_dir / "manifest.json").write_text("[]", encoding="utf-8")
    (real_dir / "inspection.json").write_text(json.dumps({"records": [
        {"source_id": "skipped-a", "status": "timeout"},
        {"source_id": "excluded-b", "status": "ok", "inspection": {"self_intersection": "unknown"}},
        {"source_id": "excluded-c", "status": "ok", "inspection": {"self_intersection": "present"}},
    ]}), encoding="utf-8")
    (tmp_path / "manifest.json").write_text("[]", encoding="utf-8")
    split_path = tmp_path / "synthetic_split.json"
    split_path.write_text(json.dumps({
        "seed": 20260513,
        "val_ratio": 0.2,
        "fit": [{"source_id": "fit-a", "source_group": "fit-a"}],
        "val": [{"source_id": row.source_id, "source_group": f"group-{index}"} for index, row in enumerate(synthetic_val())],
    }), encoding="utf-8")
    (tmp_path / "history.json").write_text(json.dumps([{"epoch": 1}]), encoding="utf-8")
    config_path = split_path.parent / "config.json"
    config_path.write_text(json.dumps({
        "config": dict(TRAINING_CONFIG),
        "baseline_sha256": checkpoint_sha256(baseline),
        "candidate_sha256": checkpoint_sha256(candidate),
        "synthetic_artifacts": artifact_hashes(split_path.parent, []),
        "real_artifacts": artifact_hashes(real_dir, []),
        "real_source_provenance": {},
    }), encoding="utf-8")
    from scripts.eval_defect_real_clean import record_fixed_config_artifact_hashes
    record_fixed_config_artifact_hashes(config_path)
    import hashlib

    source = tmp_path / "recorded_training.py"
    source.write_text("trained implementation", encoding="utf-8")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["code_provenance"] = {
        "commit_reproduces_code": False,
        "source_files": {
            str(source): {
                "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "git_status": "modified",
            }
        },
    }
    config_path.write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.setattr("scripts.eval_defect_real_clean._source_git_status", lambda path: "modified")
    loaded = []
    monkeypatch.setattr("scripts.eval_defect_real_clean.load_dataset", lambda path: synthetic_val())
    monkeypatch.setattr(
        "scripts.eval_defect_real_clean.load_real_clean_split",
        lambda path, split: loaded.append(split) or [graph(0, f"real-{split}", split)],
    )
    monkeypatch.setattr(
        "scripts.eval_defect_real_clean.compare_checkpoints",
        lambda baseline_path, candidate_path, real_data, val: {
            "baseline": {"real_holdout": prediction_metrics(["clean", "open_shell"])},
            "candidate": {"real_holdout": prediction_metrics(["clean", "clean"])},
        },
    )
    return baseline, candidate, split_path, real_dir, tmp_path / "evaluation.json", loaded


def test_evaluation_uses_holdout_for_primary_fp_and_fit_only_for_diagnostic(evaluation):
    baseline, candidate, split, real, output, loaded = evaluation

    assert main([
        "--baseline", str(baseline),
        "--candidate", str(candidate),
        "--synthetic-split", str(split),
        "--synthetic", str(split.parent),
        "--real", str(real),
        "--inspection", str(real / "inspection.json"),
        "--output", str(output),
    ]) == 0

    result = json.loads(output.read_text(encoding="utf-8"))
    status = json.loads((output.parent / "evaluation.status.json").read_text(encoding="utf-8"))
    assert status["status"] == "complete"
    assert result["status"] == "complete"
    assert result["inspection_sha256"] == checkpoint_sha256(real / "inspection.json")
    assert loaded == ["real_fit", "final_holdout"]
    assert result["baseline"]["real_holdout"]["clean_false_positive_rate"] == 0.5
    assert result["candidate"]["real_holdout"]["clean_false_positive_rate"] == 0.0
    assert result["real_fit_diagnostic"]["held_out"] is False
    assert result["real_fit_diagnostic"]["primary_clean_false_positive_metric"] is False
    assert result["real_fit_diagnostic"]["source_ids"] == ["real-real_fit"]
    for name in ("baseline", "candidate"):
        assert result["real_fit_diagnostic"][name]["samples"] == 1
        assert "clean_false_positive_rate" not in result["real_fit_diagnostic"][name]
    assert {row["source_id"] for row in result["excluded_or_skipped"]} == {
        "skipped-a", "excluded-b", "excluded-c"
    }
    assert result["synthetic_validation_source_ids"] == [f"synthetic-{label}" for label in range(4)]


def test_evaluation_cli_requires_explicit_inspection_path():
    with pytest.raises(SystemExit) as error:
        main([])

    assert error.value.code == 2


def test_evaluation_refuses_to_replace_existing_result(evaluation):
    baseline, candidate, split, real, output, _loaded = evaluation
    output.write_text("once", encoding="utf-8")

    with pytest.raises(FileExistsError, match="once|output"):
        evaluate_experiment(baseline, candidate, split, real, output, real / "inspection.json", split.parent)

    assert output.read_text(encoding="utf-8") == "once"


def test_evaluation_requires_exact_recorded_synthetic_validation_ids(evaluation, monkeypatch):
    baseline, candidate, split, real, output, _loaded = evaluation
    monkeypatch.setattr("scripts.eval_defect_real_clean.load_dataset", lambda path: synthetic_val()[:3])

    with pytest.raises(ValueError, match="recorded synthetic"):
        evaluate_experiment(baseline, candidate, split, real, output, real / "inspection.json", split.parent)

    assert json.loads(output.read_text(encoding="utf-8"))["status"] == "failed"
    status = json.loads((output.parent / "evaluation.status.json").read_text(encoding="utf-8"))
    assert status["status"] == "failed"
    assert "recorded synthetic" in status["error"]


def test_evaluation_records_failure_and_refuses_retry(evaluation, monkeypatch):
    baseline, candidate, split, real, output, _loaded = evaluation

    def fail_mid_evaluation(*args):
        raise RuntimeError("injected mid-eval failure")

    monkeypatch.setattr("scripts.eval_defect_real_clean.compare_checkpoints", fail_mid_evaluation)
    with pytest.raises(RuntimeError, match="injected mid-eval"):
        evaluate_experiment(baseline, candidate, split, real, output, real / "inspection.json", split.parent)

    status_path = output.parent / "evaluation.status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    assert status["status"] == "failed"
    assert "injected mid-eval failure" in status["error"]
    with pytest.raises(FileExistsError, match="refus|once|exists"):
        evaluate_experiment(baseline, candidate, split, real, output, real / "inspection.json", split.parent)


def test_evaluation_rejects_checkpoint_mismatch_before_any_real_loader(evaluation, monkeypatch):
    baseline, candidate, split, real, output, _loaded = evaluation
    config_path = split.parent / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["candidate_sha256"] = "0" * 64
    config_path.write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.setattr(
        "scripts.eval_defect_real_clean.load_real_clean_split",
        lambda *args: (_ for _ in ()).throw(AssertionError("real loader must not run")),
    )

    with pytest.raises(ValueError, match="candidate.*hash|hash.*candidate"):
        evaluate_experiment(baseline, candidate, split, real, output, real / "inspection.json", split.parent)


def test_evaluation_rejects_modified_dataset_before_holdout(evaluation, monkeypatch):
    baseline, candidate, split, real, output, _loaded = evaluation
    (split.parent / "synthetic.graph.json").write_text("changed", encoding="utf-8")
    config_path = split.parent / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["synthetic_artifacts"]["synthetic.graph.json"] = "0" * 64
    config_path.write_text(json.dumps(config), encoding="utf-8")
    calls = []
    monkeypatch.setattr(
        "scripts.eval_defect_real_clean.load_real_clean_split",
        lambda path, split_name: calls.append(split_name) or [graph(0, f"real-{split_name}", split_name)],
    )

    with pytest.raises(ValueError, match="provenance mismatch"):
        evaluate_experiment(baseline, candidate, split, real, output, real / "inspection.json", split.parent)

    assert "final_holdout" not in calls


def test_evaluation_rejects_stale_inspection_before_holdout_predictions(evaluation, monkeypatch):
    baseline, candidate, split, real, output, _loaded = evaluation
    config_path = split.parent / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["real_source_provenance"] = {
        "real-real_fit": "a" * 64,
        "real-final_holdout": "b" * 64,
    }
    config_path.write_text(json.dumps(config), encoding="utf-8")
    inspection_path = real / "inspection.json"
    inspection = json.loads(inspection_path.read_text(encoding="utf-8"))
    inspection["records"].append({"source_id": "real-final_holdout", "source_sha256": "stale"})
    inspection_path.write_text(json.dumps(inspection), encoding="utf-8")
    monkeypatch.setattr(
        "scripts.eval_defect_real_clean.compare_checkpoints",
        lambda *args: (_ for _ in ()).throw(AssertionError("predictions must not run")),
    )

    with pytest.raises(ValueError, match="source_sha256|inspection"):
        evaluate_experiment(baseline, candidate, split, real, output, real / "inspection.json", split.parent)


def test_inspection_validates_every_evaluated_source_and_records_file_hash(tmp_path):
    import hashlib

    inspection = tmp_path / "inspection.json"
    inspection.write_text(json.dumps({"records": [
        {"source_id": "fit", "source_sha256": "a" * 64},
        {"source_id": "holdout", "source_sha256": "b" * 64},
    ]}), encoding="utf-8")

    records, digest = _validate_inspection(inspection, {"fit": "a" * 64, "holdout": "b" * 64})

    assert [row["source_id"] for row in records] == ["fit", "holdout"]
    assert digest == hashlib.sha256(inspection.read_bytes()).hexdigest()


def test_inspection_rejects_duplicate_source_ids(tmp_path):
    inspection = tmp_path / "inspection.json"
    inspection.write_text(json.dumps({"records": [
        {"source_id": "holdout", "source_sha256": "b" * 64},
        {"source_id": "holdout", "source_sha256": "b" * 64},
    ]}), encoding="utf-8")

    with pytest.raises(ValueError, match="unique"):
        _validate_inspection(inspection, {"holdout": "b" * 64})


@pytest.fixture
def evaluation_source_guard(evaluation, monkeypatch):
    import hashlib

    source = evaluation[2].parent / "recorded_training.py"
    source.write_text("trained implementation", encoding="utf-8")
    config_path = evaluation[2].parent / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["code_provenance"] = {
        "commit_reproduces_code": False,
        "source_files": {
            str(source): {
                "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "git_status": "modified",
            }
        },
    }
    config_path.write_text(json.dumps(config), encoding="utf-8")
    git_calls = []
    monkeypatch.setattr(
        "scripts.eval_defect_real_clean._source_git_status",
        lambda path: git_calls.append(path) or "modified",
    )
    return source, git_calls


@pytest.mark.parametrize("artifact_name", ["synthetic_split.json", "history.json"])
def test_evaluation_rejects_swapped_or_modified_fixed_artifact_before_any_data_load(
    evaluation, evaluation_source_guard, monkeypatch, artifact_name
):
    baseline, candidate, split, real, output, _loaded = evaluation
    artifact = split.parent / artifact_name
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload["swapped"] = True
    else:
        payload.append({"swapped": True})
    artifact.write_text(json.dumps(payload), encoding="utf-8")
    data_loads = []
    monkeypatch.setattr("scripts.eval_defect_real_clean.load_dataset", lambda path: data_loads.append("synthetic"))
    monkeypatch.setattr(
        "scripts.eval_defect_real_clean.load_real_clean_split",
        lambda path, split_name: data_loads.append(split_name),
    )
    monkeypatch.setattr(
        "scripts.eval_defect_real_clean.compare_checkpoints",
        lambda *args: (_ for _ in ()).throw(AssertionError("holdout predictions must not run")),
    )

    with pytest.raises(ValueError, match=f"{artifact_name}.*hash|hash.*{artifact_name}"):
        evaluate_experiment(baseline, candidate, split, real, output, real / "inspection.json", split.parent)

    assert data_loads == []


def test_evaluation_verifies_the_actual_alternate_split_path(evaluation, monkeypatch):
    baseline, candidate, split, real, output, _loaded = evaluation
    alternate_split = split.with_name("alternate_split.json")
    alternate_split.write_bytes(split.read_bytes())
    config_path = split.parent / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["synthetic_split_sha256"] = checkpoint_sha256(alternate_split)
    config_path.write_text(json.dumps(config), encoding="utf-8")
    split.write_text(json.dumps({"seed": 1, "val_ratio": 1.0, "val": []}), encoding="utf-8")

    evaluate_experiment(baseline, candidate, alternate_split, real, output, real / "inspection.json", split.parent)

    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["status"] == "complete"
    assert result["synthetic_validation_source_ids"] == [f"synthetic-{label}" for label in range(4)]


def test_evaluation_rejects_modified_training_source_and_status_before_any_data_load(
    evaluation, evaluation_source_guard, monkeypatch
):
    source, _git_calls = evaluation_source_guard
    baseline, candidate, split, real, output, _loaded = evaluation
    source.write_text("modified after training", encoding="utf-8")
    data_loads = []
    monkeypatch.setattr("scripts.eval_defect_real_clean.load_dataset", lambda path: data_loads.append("synthetic"))
    monkeypatch.setattr(
        "scripts.eval_defect_real_clean.load_real_clean_split",
        lambda path, split_name: data_loads.append(split_name),
    )

    with pytest.raises(ValueError, match="source.*hash|hash.*source"):
        evaluate_experiment(baseline, candidate, split, real, output, real / "inspection.json", split.parent)

    assert data_loads == []


def test_evaluation_rejects_changed_recorded_source_git_status(evaluation, evaluation_source_guard, monkeypatch):
    _source, _git_calls = evaluation_source_guard
    baseline, candidate, split, real, output, _loaded = evaluation
    monkeypatch.setattr("scripts.eval_defect_real_clean._source_git_status", lambda path: "clean")

    with pytest.raises(ValueError, match="source.*status|status.*source"):
        evaluate_experiment(baseline, candidate, split, real, output, real / "inspection.json", split.parent)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda config: config.__setitem__("config", {**config["config"], "lr": 0.01}), "training config"),
        (lambda config: config.__setitem__("code_provenance", {"commit_reproduces_code": True, "source_files": {}}), "source_files|code provenance"),
    ],
)
def test_evaluation_requires_exact_fixed_config_and_code_evidence(evaluation, monkeypatch, mutate, message):
    baseline, candidate, split, real, output, _loaded = evaluation
    config_path = split.parent / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    mutate(config)
    config_path.write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        evaluate_experiment(baseline, candidate, split, real, output, real / "inspection.json", split.parent)


def test_evaluation_verifies_sources_before_data_loading(evaluation, evaluation_source_guard, monkeypatch):
    source, git_calls = evaluation_source_guard
    baseline, candidate, split, real, output, _loaded = evaluation
    events = []
    monkeypatch.setattr("scripts.eval_defect_real_clean.load_dataset", lambda path: events.append("load") or synthetic_val())
    monkeypatch.setattr(
        "scripts.eval_defect_real_clean.load_real_clean_split",
        lambda path, split_name: events.append(split_name) or [graph(0, f"real-{split_name}", split_name)],
    )

    evaluate_experiment(baseline, candidate, split, real, output, real / "inspection.json", split.parent)

    assert git_calls == [str(source)]
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["provenance_verified"]["source_matches_training"] is True
    assert result["provenance_verified"]["synthetic_split_sha256"] is True
    assert result["provenance_verified"]["history_sha256"] is True
    assert events == ["real_fit", "final_holdout", "load"]


def test_recorded_synthetic_val_loads_actual_auto_label_stem_schema(tmp_path):
    dataset = tmp_path / "synthetic"
    dataset.mkdir()
    entries = [{"status": "ok", "stem": "part-a__clean", "face_count": 1}]
    (dataset / "manifest.json").write_text(json.dumps(entries), encoding="utf-8")
    (dataset / "part-a__clean.graph.json").write_text(json.dumps({
        "node_features": [{"face_index": 0, "surface_type": "plane"}],
        "adjacency": [],
    }), encoding="utf-8")
    (dataset / "part-a__clean.labels.json").write_text(json.dumps({
        "refinement": {}, "complexity_proxy": {}, "graph_label": 0,
    }), encoding="utf-8")
    split = tmp_path / "synthetic_split.json"
    split.write_text(json.dumps({"val": [{"source_id": "part-a__clean"}]}), encoding="utf-8")

    selected = _recorded_synthetic_val(dataset, split)

    assert [data.stem for data in selected] == ["part-a__clean"]
    assert selected[0].source_id == "part-a__clean"
