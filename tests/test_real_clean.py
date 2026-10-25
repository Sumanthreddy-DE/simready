import copy
import hashlib
import json
from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import pytest

from simready.ml.real_clean import (
    RealCleanSample,
    build_real_labels,
    clean_false_positive_rate,
    load_manifest,
    load_real_clean_samples,
    load_real_clean_split,
    split_real_samples,
)


INSPECTION_FIELDS = ("open_shell", "sliver_face", "self_intersection")


def part(source_id="part-a", family_id="family-a", split="real_fit", sha256="a" * 64):
    return {
        "source_id": source_id,
        "family_id": family_id,
        "split": split,
        "sha256": sha256,
        "inspection": {field: "absent" for field in INSPECTION_FIELDS},
    }


def manifest(*parts):
    return {"experiment": "real_clean_v1", "parts": list(parts)}


def write_manifest(tmp_path, value):
    path = tmp_path / "real_clean.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_build_real_labels_contains_only_reviewed_clean_graph_labels():
    sample = RealCleanSample(
        source_id="part-a",
        family_id="family-a",
        split="real_fit",
        sha256="a" * 64,
        inspection={field: "absent" for field in INSPECTION_FIELDS},
    )
    graph = SimpleNamespace(
        node_features=[
            {"face_index": 2, "surface_type": "plane"},
            {"face_index": 0, "surface_type": "plane"},
            {"face_index": 1, "surface_type": "cylinder"},
        ]
    )

    labels = build_real_labels(sample, graph)

    assert labels == {
        "face_count": 3,
        "indices": [0, 1, 2],
        "graph_label": 0,
        "graph_label_name": "clean",
        "label_source": "reviewed_real_clean_v1",
        "source_id": "part-a",
        "family_id": "family-a",
        "source_sha256": "a" * 64,
        "refinement": {},
        "complexity_proxy": {},
    }


def test_build_real_labels_rejects_duplicate_face_indices():
    sample = RealCleanSample("part-a", "family-a", "real_fit", "a" * 64, {})
    graph = SimpleNamespace(node_features=[{"face_index": 0}, {"face_index": 0}])

    with pytest.raises(ValueError, match="face_index"):
        build_real_labels(sample, graph)


def test_clean_false_positive_rate_counts_every_nonclean_class():
    predictions = ["clean", "open_shell", "sliver_face", "self_intersection", "clean"]

    assert clean_false_positive_rate(predictions) == pytest.approx(3 / 5)


@pytest.mark.parametrize("predictions", [[], (), ["CLEAN"], ["unknown"], [None], [0]])
def test_clean_false_positive_rate_rejects_empty_or_invalid_classes(predictions):
    with pytest.raises(ValueError):
        clean_false_positive_rate(predictions)


def test_load_manifest_accepts_verified_real_clean_samples(tmp_path):
    fit = part()
    holdout = part(
        source_id="part-b",
        family_id="family-b",
        split="final_holdout",
        sha256="b" * 64,
    )
    path = write_manifest(tmp_path, manifest(fit, holdout))

    samples = load_manifest(path)

    assert samples == [
        RealCleanSample(
            source_id="part-a",
            family_id="family-a",
            split="real_fit",
            sha256="a" * 64,
            inspection={field: "absent" for field in INSPECTION_FIELDS},
        ),
        RealCleanSample(
            source_id="part-b",
            family_id="family-b",
            split="final_holdout",
            sha256="b" * 64,
            inspection={field: "absent" for field in INSPECTION_FIELDS},
        ),
    ]
    assert all(sample.graph_label == 0 for sample in samples)


def test_real_clean_sample_is_immutable():
    sample = RealCleanSample("part-a", "family-a", "real_fit", "a" * 64, {})

    with pytest.raises(FrozenInstanceError):
        sample.graph_label = 1


def test_load_manifest_rejects_duplicate_source_id(tmp_path):
    first = part()
    second = part(source_id="part-b", family_id="family-b", sha256="b" * 64)
    second["source_id"] = first["source_id"]
    path = write_manifest(tmp_path, manifest(first, second))

    with pytest.raises(ValueError) as error:
        load_manifest(path)

    assert second["source_id"] in str(error.value)
    assert "source_id" in str(error.value)


def test_load_manifest_rejects_case_insensitive_duplicate_source_id(tmp_path):
    first = part(source_id="Part-A")
    second = part(source_id="part-a", family_id="family-b", sha256="b" * 64)
    path = write_manifest(tmp_path, manifest(first, second))

    with pytest.raises(ValueError, match="case-insensitive"):
        load_manifest(path)


def test_load_manifest_accepts_same_family_and_hash_for_distinct_sources(tmp_path):
    first = part()
    second = part(source_id="part-b")
    path = write_manifest(tmp_path, manifest(first, second))

    samples = load_manifest(path)

    assert [sample.source_id for sample in samples] == ["part-a", "part-b"]
    assert {sample.family_id for sample in samples} == {"family-a"}
    assert {sample.sha256 for sample in samples} == {"a" * 64}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("sha256", "A" * 64),
        ("sha256", "a" * 63),
        ("sha256", "g" * 64),
        ("sha256", ""),
        ("split", "train"),
        ("split", "REAL_FIT"),
        ("split", ""),
        ("family_id", ""),
        ("family_id", "   "),
        ("source_id", ""),
        ("source_id", "   "),
    ],
)
def test_load_manifest_rejects_invalid_fields_with_source_and_field(tmp_path, field, value):
    invalid = part()
    invalid[field] = value
    path = write_manifest(tmp_path, manifest(invalid))

    with pytest.raises(ValueError) as error:
        load_manifest(path)

    assert "source" in str(error.value)
    assert field in str(error.value)
    if field == "source_id":
        assert "non-empty string" in str(error.value)


@pytest.mark.parametrize("inspection_field", INSPECTION_FIELDS)
@pytest.mark.parametrize("value", ["present", "unknown", "skipped", "timeout", "Absent", "", None])
def test_load_manifest_rejects_unverified_inspection_values(tmp_path, inspection_field, value):
    invalid = part()
    invalid["inspection"][inspection_field] = value
    path = write_manifest(tmp_path, manifest(invalid))

    with pytest.raises(ValueError) as error:
        load_manifest(path)

    assert "part-a" in str(error.value)
    assert inspection_field in str(error.value)


@pytest.mark.parametrize("inspection_field", INSPECTION_FIELDS)
def test_load_manifest_rejects_missing_inspection_result(tmp_path, inspection_field):
    invalid = part()
    del invalid["inspection"][inspection_field]
    path = write_manifest(tmp_path, manifest(invalid))

    with pytest.raises(ValueError) as error:
        load_manifest(path)

    assert "part-a" in str(error.value)
    assert inspection_field in str(error.value)


def test_load_manifest_rejects_wrong_experiment(tmp_path):
    path = write_manifest(tmp_path, {"experiment": "other", "parts": [part()]})

    with pytest.raises(ValueError, match="experiment"):
        load_manifest(path)


def test_split_real_samples_rejects_family_in_both_splits():
    samples = [
        RealCleanSample("part-a", "shared", "real_fit", "a" * 64, {}),
        RealCleanSample("part-b", "shared", "final_holdout", "b" * 64, {}),
    ]

    with pytest.raises(ValueError) as error:
        split_real_samples(samples)

    assert "shared" in str(error.value)
    assert "family_id" in str(error.value)


@pytest.mark.parametrize(
    "split",
    ["real_fit", "final_holdout"],
)
def test_split_real_samples_requires_a_family_in_each_split(split):
    samples = [RealCleanSample("part-a", "family-a", split, "a" * 64, {})]

    with pytest.raises(ValueError) as error:
        split_real_samples(samples)

    assert "family" in str(error.value)
    assert "split" in str(error.value)


def _write_real_dataset(dataset_dir, entries):
    dataset_dir.mkdir(exist_ok=True)
    manifest_entries = []
    for entry in entries:
        source_id = entry["source_id"]
        graph = {
            "node_features": [{"face_index": 0, "surface_type": "plane", "area": 1.0, "normal": [0, 0, 1]}],
            "adjacency": [],
            "metadata": {key: entry[key] for key in ("source_id", "family_id", "split", "source_sha256")},
        }
        labels = {
            "face_count": 1,
            "indices": [0],
            "graph_label": 0,
            "graph_label_name": "clean",
            "label_source": "reviewed_real_clean_v1",
            "source_id": source_id,
            "family_id": entry["family_id"],
            "source_sha256": entry["source_sha256"],
            "refinement": {},
            "complexity_proxy": {},
        }
        (dataset_dir / f"{source_id}.graph.json").write_text(json.dumps(graph), encoding="utf-8")
        (dataset_dir / f"{source_id}.labels.json").write_text(json.dumps(labels), encoding="utf-8")
        manifest_entries.append({
            "status": "ok", "stem": source_id, "face_count": 1,
            "graph_sha256": hashlib.sha256((dataset_dir / f"{source_id}.graph.json").read_bytes()).hexdigest(),
            "labels_sha256": hashlib.sha256((dataset_dir / f"{source_id}.labels.json").read_bytes()).hexdigest(),
            **entry,
        })
    (dataset_dir / "manifest.json").write_text(json.dumps(manifest_entries), encoding="utf-8")
    return manifest_entries


def _real_entries():
    return [
        {"source_id": "family-a__variant", "family_id": "family-a", "split": "real_fit", "source_sha256": "a" * 64},
        {"source_id": "family-b__variant", "family_id": "family-b", "split": "final_holdout", "source_sha256": "b" * 64},
    ]


def test_load_real_clean_samples_uses_manifest_family_split_not_stems(tmp_path):
    _write_real_dataset(tmp_path, _real_entries())

    fit, holdout = load_real_clean_samples(tmp_path)

    assert [data.source_id for data in fit] == ["family-a__variant"]
    assert [data.source_id for data in holdout] == ["family-b__variant"]
    assert fit[0].family_id == "family-a"
    assert holdout[0].family_id == "family-b"


@pytest.mark.parametrize(
    ("file_kind", "field", "value"),
    [
        ("labels", "graph_label", None),
        ("labels", "face_count", None),
        ("labels", "face_count", 2),
        ("labels", "indices", None),
        ("labels", "indices", []),
        ("labels", "indices", [1]),
        ("labels", "refinement", None),
        ("labels", "refinement", {"0": False}),
        ("labels", "complexity_proxy", None),
        ("labels", "complexity_proxy", {"0": 0.0}),
        ("labels", "label_source", "generic_auto_label"),
        ("labels", "graph_label_name", "open_shell"),
        ("labels", "family_id", "other-family"),
        ("labels", "source_sha256", "0" * 64),
        ("graph", "family_id", "other-family"),
        ("graph", "split", "final_holdout"),
        ("graph", "source_id", "other-source"),
        ("manifest", "family_id", "other-family"),
        ("manifest", "split", "final_holdout"),
        ("manifest", "source_sha256", "0" * 64),
        ("manifest", "face_count", 2),
    ],
)
def test_load_real_clean_samples_rejects_unreviewed_or_inconsistent_metadata(tmp_path, file_kind, field, value):
    entries = _real_entries()
    _write_real_dataset(tmp_path, entries)
    if file_kind == "manifest":
        manifest_path = tmp_path / "manifest.json"
        manifest_entries = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest_entries[0][field] = value
        manifest_path.write_text(json.dumps(manifest_entries), encoding="utf-8")
    else:
        suffix = "labels" if file_kind == "labels" else "graph"
        path = tmp_path / f"family-a__variant.{suffix}.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        target = payload["metadata"] if file_kind == "graph" else payload
        if value is None:
            del target[field]
        else:
            target[field] = value
        path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError):
        load_real_clean_samples(tmp_path)


def test_real_loader_rejects_generic_unreviewed_manifest(tmp_path):
    _write_real_dataset(tmp_path, _real_entries())
    manifest_path = tmp_path / "manifest.json"
    entries = json.loads(manifest_path.read_text(encoding="utf-8"))
    for entry in entries:
        del entry["source_sha256"]
    manifest_path.write_text(json.dumps(entries), encoding="utf-8")

    with pytest.raises(ValueError, match="source_sha256"):
        load_real_clean_samples(tmp_path)


@pytest.mark.parametrize(
    ("split", "expected"),
    [("real_fit", ["family-a__variant"]), ("final_holdout", ["family-b__variant"])],
)
def test_load_real_clean_split_selects_only_requested_provenance_split(tmp_path, split, expected):
    _write_real_dataset(tmp_path, _real_entries())

    loaded = load_real_clean_split(tmp_path, split)

    assert [data.source_id for data in loaded] == expected
    assert all(data.split == split for data in loaded)


def test_load_real_clean_split_does_not_materialize_the_other_split(tmp_path, monkeypatch):
    _write_real_dataset(tmp_path, _real_entries())
    loaded = []
    from simready.ml import dataset

    original_load_sample = dataset.load_sample

    def record_load(metadata):
        loaded.append(metadata.source_id)
        return original_load_sample(metadata)

    monkeypatch.setattr(dataset, "load_sample", record_load)

    fit = load_real_clean_split(tmp_path, "real_fit")

    assert [data.source_id for data in fit] == ["family-a__variant"]
    assert loaded == ["family-a__variant"]


def test_load_real_clean_fit_never_reads_holdout_graph_or_labels(tmp_path, monkeypatch):
    from pathlib import Path

    _write_real_dataset(tmp_path, _real_entries())
    original_read_bytes = Path.read_bytes
    original_read_text = Path.read_text
    reads = []

    def guarded_read_bytes(path, *args, **kwargs):
        reads.append(path.name)
        assert not path.name.startswith("family-b__variant"), f"holdout artifact read: {path}"
        return original_read_bytes(path, *args, **kwargs)

    def guarded_read_text(path, *args, **kwargs):
        reads.append(path.name)
        assert not path.name.startswith("family-b__variant"), f"holdout artifact read: {path}"
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", guarded_read_bytes)
    monkeypatch.setattr(Path, "read_text", guarded_read_text)

    fit = load_real_clean_split(tmp_path, "real_fit")

    assert [data.source_id for data in fit] == ["family-a__variant"]
    assert set(reads) == {
        "manifest.json", "family-a__variant.graph.json", "family-a__variant.labels.json"
    }


def test_training_provenance_never_reads_holdout_graph_or_label_bytes(tmp_path, monkeypatch):
    from pathlib import Path
    from simready.ml.artifact_provenance import real_declared_artifacts

    _write_real_dataset(tmp_path, _real_entries())
    expected_holdout_hash = hashlib.sha256((tmp_path / "family-b__variant.graph.json").read_bytes()).hexdigest()
    original_read_bytes = Path.read_bytes

    def guarded_read(path, *args, **kwargs):
        assert not path.name.startswith("family-b__variant"), f"holdout artifact read: {path}"
        return original_read_bytes(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", guarded_read)

    artifacts = real_declared_artifacts(tmp_path)

    assert artifacts["family-b__variant.graph.json"] == expected_holdout_hash


def test_split_real_samples_preserves_manifest_order_and_does_not_mutate_input():
    samples = [
        RealCleanSample("part-a", "family-a", "real_fit", "a" * 64, {"open_shell": "absent"}),
        RealCleanSample("part-b", "family-b", "final_holdout", "b" * 64, {}),
        RealCleanSample("part-c", "family-a", "real_fit", "c" * 64, {}),
        RealCleanSample("part-d", "family-c", "real_fit", "d" * 64, {}),
        RealCleanSample("part-e", "family-b", "final_holdout", "e" * 64, {}),
    ]
    original = copy.deepcopy(samples)

    fit, holdout = split_real_samples(samples)

    assert fit == [samples[0], samples[2], samples[3]]
    assert holdout == [samples[1], samples[4]]
    assert samples == original
