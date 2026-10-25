import copy
import hashlib
import json
from pathlib import Path

import pytest

from scripts.prepare_real_clean import main


def reviewed_manifest(source: Path, split="real_fit"):
    return {
        "experiment": "real_clean_v1",
        "parts": [
            {
                "source_id": source.stem,
                "family_id": "reviewed-family",
                "split": split,
                "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "inspection": {
                    "open_shell": "absent",
                    "sliver_face": "absent",
                    "self_intersection": "absent",
                },
            }
        ],
    }


def write_manifest(path: Path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_prepare_writes_real_graphs_labels_and_dataset_metadata(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    source = input_dir / "Reviewed Part.STEP"
    source.write_bytes(Path("tests/data/smoke_box.step").read_bytes())
    manifest = write_manifest(tmp_path / "reviewed.json", reviewed_manifest(source))
    output = tmp_path / "dataset"

    assert main(["--manifest", str(manifest), "--input", str(input_dir), "--output", str(output)]) == 0

    graph = json.loads((output / "Reviewed Part.graph.json").read_text(encoding="utf-8"))
    labels = json.loads((output / "Reviewed Part.labels.json").read_text(encoding="utf-8"))
    manifest_entries = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert graph["metadata"]["source_id"] == "Reviewed Part"
    assert graph["metadata"]["family_id"] == "reviewed-family"
    assert graph["metadata"]["split"] == "real_fit"
    assert labels["graph_label"] == 0
    assert labels["graph_label_name"] == "clean"
    assert labels["label_source"] == "reviewed_real_clean_v1"
    assert labels["refinement"] == {}
    assert labels["complexity_proxy"] == {}
    assert manifest_entries == [
        {
            "status": "ok",
            "stem": "Reviewed Part",
            "source_id": "Reviewed Part",
            "family_id": "reviewed-family",
            "split": "real_fit",
            "face_count": 6,
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "reviewed_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
            "graph_sha256": hashlib.sha256((output / "Reviewed Part.graph.json").read_bytes()).hexdigest(),
            "labels_sha256": hashlib.sha256((output / "Reviewed Part.labels.json").read_bytes()).hexdigest(),
            "graph_label": 0,
            "graph_label_name": "clean",
        }
    ]

    from simready.ml.dataset import discover_samples, load_sample

    samples = discover_samples(output)
    assert len(samples) == 1
    data = load_sample(samples[0])
    assert data.source_id == "Reviewed Part"
    assert data.family_id == "reviewed-family"
    assert data.split == "real_fit"
    assert data.face_count == 6
    assert int(data.graph_label) == 0
    assert data.refinement_label.tolist() == [0.0] * 6
    assert data.complexity_label.tolist() == [0.0] * 6


def test_prepare_to_real_loader_roundtrip_preserves_hashes_and_family_splits(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    fit_source = input_dir / "fit__part.step"
    holdout_source = input_dir / "holdout__part.step"
    fit_source.write_bytes(Path("tests/data/smoke_box.step").read_bytes())
    holdout_source.write_bytes(Path("tests/data/smoke_box.step").read_bytes())
    value = reviewed_manifest(fit_source)
    holdout = reviewed_manifest(holdout_source, split="final_holdout")["parts"][0]
    holdout["family_id"] = "holdout-family"
    value["parts"].append(holdout)
    manifest = write_manifest(tmp_path / "reviewed.json", value)
    output = tmp_path / "dataset"

    assert main(["--manifest", str(manifest), "--input", str(input_dir), "--output", str(output)]) == 0

    from simready.ml.real_clean import load_real_clean_samples

    fit, loaded_holdout = load_real_clean_samples(output)
    assert [data.source_id for data in fit] == ["fit__part"]
    assert [data.source_id for data in loaded_holdout] == ["holdout__part"]
    manifest_entries = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert [entry["source_sha256"] for entry in manifest_entries] == [
        hashlib.sha256(fit_source.read_bytes()).hexdigest(),
        hashlib.sha256(holdout_source.read_bytes()).hexdigest(),
    ]


def test_prepare_rejects_hash_mismatch_without_creating_output(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    source = input_dir / "part.step"
    source.write_bytes(Path("tests/data/smoke_box.step").read_bytes())
    value = reviewed_manifest(source)
    value["parts"][0]["sha256"] = "0" * 64
    manifest = write_manifest(tmp_path / "reviewed.json", value)
    output = tmp_path / "dataset"

    assert main(["--manifest", str(manifest), "--input", str(input_dir), "--output", str(output)]) == 1
    assert not output.exists()


def test_prepare_rejects_missing_and_duplicate_source_ids(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    source = input_dir / "part.step"
    source.write_bytes(Path("tests/data/smoke_box.step").read_bytes())
    value = reviewed_manifest(source)
    manifest = write_manifest(tmp_path / "reviewed.json", value)

    assert main(["--manifest", str(manifest), "--input", str(tmp_path), "--output", str(tmp_path / "missing")]) == 1

    value["parts"][0]["source_id"] = "other"
    manifest = write_manifest(tmp_path / "reviewed.json", value)
    assert main(["--manifest", str(manifest), "--input", str(input_dir), "--output", str(tmp_path / "wrong-stem")]) == 1

    value = reviewed_manifest(source)
    duplicate = copy.deepcopy(value["parts"][0])
    duplicate["source_id"] = duplicate["source_id"].upper()
    duplicate["family_id"] = "other-family"
    value["parts"].append(duplicate)
    manifest = write_manifest(tmp_path / "reviewed.json", value)
    assert main(["--manifest", str(manifest), "--input", str(input_dir), "--output", str(tmp_path / "duplicate")]) == 1


def test_prepare_matches_windows_case_variants_of_one_source_stem(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    source = input_dir / "part.step"
    source.write_bytes(Path("tests/data/smoke_box.step").read_bytes())
    (input_dir / "PART.STEP").write_bytes(source.read_bytes())
    assert len(list(input_dir.iterdir())) == 1
    manifest = write_manifest(tmp_path / "reviewed.json", reviewed_manifest(source))

    assert main(["--manifest", str(manifest), "--input", str(input_dir), "--output", str(tmp_path / "dataset")]) == 0


def test_prepare_timeout_is_explicit_and_does_not_create_output(tmp_path, monkeypatch):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    source = input_dir / "part.step"
    source.write_bytes(Path("tests/data/smoke_box.step").read_bytes())
    manifest = write_manifest(tmp_path / "reviewed.json", reviewed_manifest(source))
    output = tmp_path / "dataset"

    def timeout_worker(*_args, **_kwargs):
        raise TimeoutError("prepare_timeout (>0.001s)")

    monkeypatch.setattr("scripts.prepare_real_clean.prepare_one_in_subprocess", timeout_worker)

    assert main(["--manifest", str(manifest), "--input", str(input_dir), "--output", str(output), "--timeout", "0.001"]) == 1
    assert not output.exists()


def test_prepare_refuses_nonempty_output_before_reading_sources(tmp_path):
    output = tmp_path / "dataset"
    output.mkdir()
    (output / "keep.txt").write_text("do not overwrite", encoding="utf-8")

    assert main(["--manifest", str(tmp_path / "absent.json"), "--input", str(tmp_path), "--output", str(output)]) == 1
    assert (output / "keep.txt").read_text(encoding="utf-8") == "do not overwrite"
