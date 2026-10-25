"""Load verified real clean negatives for the real_clean_v1 experiment."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from simready.ml.model import DEFECT_CLASSES


EXPERIMENT = "real_clean_v1"
SPLITS = ("real_fit", "final_holdout")
INSPECTION_FIELDS = ("open_shell", "sliver_face", "self_intersection")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class RealCleanSample:
    source_id: str
    family_id: str
    split: str
    sha256: str
    inspection: dict[str, str]
    graph_label: int = 0


def _error(source_id: object, field: str, message: str) -> ValueError:
    return ValueError(f"source {source_id!r}: {field}: {message}")


def _required_text(entry: dict, field: str, source_id: object) -> str:
    value = entry.get(field)
    if not isinstance(value, str) or not value.strip():
        raise _error(source_id, field, "must be a non-empty string")
    return value


def _load_part(entry: object) -> RealCleanSample:
    if not isinstance(entry, dict):
        raise _error("<unknown>", "part", "must be an object")

    source_id = _required_text(entry, "source_id", entry.get("source_id", "<missing>"))
    family_id = _required_text(entry, "family_id", source_id)
    split = _required_text(entry, "split", source_id)
    if split not in SPLITS:
        raise _error(source_id, "split", f"must be one of {SPLITS}")

    sha256 = _required_text(entry, "sha256", source_id)
    if _SHA256.fullmatch(sha256) is None:
        raise _error(source_id, "sha256", "must be exactly 64 lowercase hexadecimal characters")

    inspection = entry.get("inspection")
    if not isinstance(inspection, dict):
        raise _error(source_id, "inspection", "must be an object")
    for field in INSPECTION_FIELDS:
        if field not in inspection:
            raise _error(source_id, f"inspection.{field}", "missing verified result")
        if inspection[field] != "absent":
            raise _error(
                source_id,
                f"inspection.{field}",
                f"must be exactly 'absent', got {inspection[field]!r}",
            )

    return RealCleanSample(
        source_id=source_id,
        family_id=family_id,
        split=split,
        sha256=sha256,
        inspection=dict(inspection),
    )


def load_manifest(path: Path) -> list[RealCleanSample]:
    """Load training-eligible clean samples; reject all unverified evidence."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("manifest: must be an object")
    if data.get("experiment") != EXPERIMENT:
        raise ValueError(f"experiment: must be exactly {EXPERIMENT!r}")

    parts = data.get("parts")
    if not isinstance(parts, list):
        raise ValueError("parts: must be a list")

    samples = [_load_part(entry) for entry in parts]
    seen_source_ids: set[str] = set()
    for sample in samples:
        source_key = sample.source_id.casefold()
        if source_key in seen_source_ids:
            raise _error(sample.source_id, "source_id", f"duplicate case-insensitive value {sample.source_id!r}")
        seen_source_ids.add(source_key)
    return samples


def split_real_samples(samples: list[RealCleanSample]) -> tuple[list[RealCleanSample], list[RealCleanSample]]:
    """Return ordered fit and holdout samples, enforcing disjoint families."""
    fit_families = {sample.family_id for sample in samples if sample.split == "real_fit"}
    holdout_families = {sample.family_id for sample in samples if sample.split == "final_holdout"}
    overlap = sorted(fit_families & holdout_families)
    if overlap:
        raise ValueError(f"family_id: families appear in both splits: {', '.join(overlap)}")
    if not fit_families or not holdout_families:
        raise ValueError("family split: requires at least one real_fit and one final_holdout family")

    fit = [sample for sample in samples if sample.split == "real_fit"]
    holdout = [sample for sample in samples if sample.split == "final_holdout"]
    return fit, holdout


def build_real_labels(sample: RealCleanSample, graph) -> dict[str, object]:
    """Build graph-only labels from an already reviewed clean sample."""
    indices = [int(node["face_index"]) for node in graph.node_features]
    if len(indices) != len(set(indices)):
        raise ValueError(f"source {sample.source_id!r}: duplicate graph face_index")
    return {
        "face_count": len(graph.node_features),
        "indices": sorted(indices),
        "graph_label": sample.graph_label,
        "graph_label_name": DEFECT_CLASSES[sample.graph_label],
        "label_source": "reviewed_real_clean_v1",
        "source_id": sample.source_id,
        "family_id": sample.family_id,
        "source_sha256": sample.sha256,
        "refinement": {},
        "complexity_proxy": {},
    }


def _validated_real_sample(dataset_dir: Path, entry: object) -> tuple[object, str]:
    from simready.ml.dataset import SampleMetadata

    if not isinstance(entry, dict) or entry.get("status") != "ok":
        raise ValueError("real_clean manifest: every entry must have status 'ok'")
    source_id = _required_text(entry, "source_id", entry.get("source_id", "<missing>"))
    if entry.get("stem") != source_id:
        raise _error(source_id, "stem", "must match source_id")
    family_id = _required_text(entry, "family_id", source_id)
    split = _required_text(entry, "split", source_id)
    if split not in SPLITS:
        raise _error(source_id, "split", f"must be one of {SPLITS}")
    sha256 = _required_text(entry, "source_sha256", source_id)
    if _SHA256.fullmatch(sha256) is None:
        raise _error(source_id, "source_sha256", "must be a lowercase SHA-256")

    graph_path = dataset_dir / f"{source_id}.graph.json"
    labels_path = dataset_dir / f"{source_id}.labels.json"
    metadata = SampleMetadata(
        stem=source_id,
        graph_path=graph_path,
        labels_path=labels_path,
        face_count=int(entry.get("face_count", 0)),
        source_id=source_id,
        family_id=family_id,
        split=split,
    )
    return metadata, sha256


def _validate_requested_artifacts(entry: dict, metadata, sha256: str) -> None:
    source_id = metadata.source_id
    graph = json.loads(metadata.graph_path.read_text(encoding="utf-8"))
    labels = json.loads(metadata.labels_path.read_text(encoding="utf-8"))
    if not isinstance(graph, dict) or not isinstance(labels, dict) or not isinstance(graph.get("metadata"), dict):
        raise _error(source_id, "dataset", "graph, graph metadata and labels must be objects")
    if labels.get("label_source") != "reviewed_real_clean_v1":
        raise _error(source_id, "label_source", "must be 'reviewed_real_clean_v1'")
    if labels.get("graph_label") != 0 or labels.get("graph_label_name") != "clean":
        raise _error(source_id, "graph_label", "reviewed real samples must be explicit clean class 0")
    expected = {"source_id": source_id, "family_id": metadata.family_id, "source_sha256": sha256}
    for field, value in expected.items():
        if labels.get(field) != value or graph["metadata"].get(field) != value:
            raise _error(source_id, field, "manifest, labels and graph metadata must agree")
    if graph["metadata"].get("split") != metadata.split:
        raise _error(source_id, "split", "manifest and graph metadata must agree")
    nodes = graph.get("node_features")
    if not isinstance(nodes, list) or not nodes:
        raise _error(source_id, "node_features", "must be a nonempty list")
    face_count = len(nodes)
    if type(entry.get("face_count")) is not int or entry["face_count"] != face_count:
        raise _error(source_id, "face_count", "manifest must equal graph node count")
    if type(labels.get("face_count")) is not int or labels["face_count"] != face_count:
        raise _error(source_id, "face_count", "labels must equal graph node count")
    indices = [node.get("face_index") for node in nodes]
    if any(type(index) is not int for index in indices):
        raise _error(source_id, "face_index", "every graph node must have an integer face_index")
    if labels.get("indices") != sorted(indices) or len(indices) != len(set(indices)):
        raise _error(source_id, "indices", "must be the sorted unique graph face indices")
    for field in ("refinement", "complexity_proxy"):
        if type(labels.get(field)) is not dict or labels[field] != {}:
            raise _error(source_id, field, "real graph-only labels must be an explicitly empty object")


def _load_real_clean_data(
    dataset_dir: Path, requested_split: str | None = None
) -> tuple[list[object], list[object]]:
    """Validate all provenance but materialize only the requested split, if given."""
    from simready.ml.dataset import load_sample

    entries = json.loads((dataset_dir / "manifest.json").read_text(encoding="utf-8"))
    if not isinstance(entries, list) or not entries:
        raise ValueError("real_clean manifest: must be a nonempty list")
    seen: set[str] = set()
    fit: list[object] = []
    holdout: list[object] = []
    split_families = {name: set() for name in SPLITS}
    for entry in entries:
        metadata, _sha256 = _validated_real_sample(dataset_dir, entry)
        key = metadata.source_id.casefold()
        if key in seen:
            raise _error(metadata.source_id, "source_id", "duplicate case-insensitive value")
        seen.add(key)
        split_families[metadata.split].add(metadata.family_id)
        if requested_split is None or metadata.split == requested_split:
            _validate_requested_artifacts(entry, metadata, _sha256)
            data = load_sample(metadata)
            (fit if metadata.split == "real_fit" else holdout).append(data)
    fit_families = split_families["real_fit"]
    holdout_families = split_families["final_holdout"]
    if not fit_families or not holdout_families or fit_families & holdout_families:
        raise ValueError("family split: real_fit and final_holdout require nonempty disjoint families")
    if not fit and not holdout:
        raise ValueError("requested real split must not be empty")
    return fit, holdout


def load_real_clean_samples(dataset_dir: Path) -> tuple[list[object], list[object]]:
    """Load reviewed real graphs and enforce disjoint, nonempty family splits."""
    return _load_real_clean_data(dataset_dir)


def load_real_clean_split(dataset_dir: Path, split: str) -> list[object]:
    """Load exactly one reviewed split; never materialize the other split's graphs."""
    if split not in SPLITS:
        raise ValueError(f"split must be one of {SPLITS}")
    fit, holdout = _load_real_clean_data(dataset_dir, split)
    return fit if split == "real_fit" else holdout


def clean_false_positive_rate(predictions: Iterable[str]) -> float:
    """Return the fraction of reviewed-clean parts assigned a nonclean class."""
    labels = list(predictions)
    if not labels:
        raise ValueError("predictions: must not be empty")
    invalid = [label for label in labels if label not in DEFECT_CLASSES]
    if invalid:
        raise ValueError(f"predictions: invalid defect classes: {invalid!r}")
    return sum(label != "clean" for label in labels) / len(labels)
