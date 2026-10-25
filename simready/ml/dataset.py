"""Dataset utilities: load auto-labeled graph/label JSONs as PyG Data objects."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import torch
from torch_geometric.data import Data

from simready.ml.model import build_edge_index, node_feature_vector


@dataclass
class SampleMetadata:
    stem: str
    graph_path: Path
    labels_path: Path
    face_count: int
    source_id: str | None = None
    family_id: str | None = None
    split: str | None = None


def sample_source_id(data: Data) -> str:
    """Canonical graph ID: reviewed source_id when present, otherwise auto-label stem."""
    source_id = getattr(data, "source_id", None)
    if source_id is None:
        source_id = getattr(data, "stem", None)
    if not isinstance(source_id, str) or not source_id:
        raise ValueError("sample requires a nonempty source_id or stem")
    return source_id


def discover_samples(dataset_dir: Path) -> list[SampleMetadata]:
    manifest_path = dataset_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"manifest.json not found in {dataset_dir}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    samples: list[SampleMetadata] = []
    for entry in manifest:
        if entry.get("status") != "ok":
            continue
        stem = entry.get("stem")
        if not stem:
            continue
        graph_path = dataset_dir / f"{stem}.graph.json"
        labels_path = dataset_dir / f"{stem}.labels.json"
        if not graph_path.is_file() or not labels_path.is_file():
            continue
        samples.append(
            SampleMetadata(
                stem=stem,
                graph_path=graph_path,
                labels_path=labels_path,
                face_count=int(entry.get("face_count", 0)),
                source_id=entry.get("source_id"),
                family_id=entry.get("family_id"),
                split=entry.get("split"),
            )
        )
    return samples


def load_sample(sample: SampleMetadata) -> Data:
    graph = json.loads(sample.graph_path.read_text(encoding="utf-8"))
    labels = json.loads(sample.labels_path.read_text(encoding="utf-8"))
    nodes = graph.get("node_features", [])
    if not nodes:
        raise ValueError(f"empty node_features in {sample.graph_path}")

    # Sort by face_index so labels and tensors align deterministically.
    nodes_sorted = sorted(nodes, key=lambda n: int(n.get("face_index", 0)))

    x = torch.tensor([node_feature_vector(node) for node in nodes_sorted], dtype=torch.float32)
    edge_index = build_edge_index(graph.get("adjacency", []))

    refinement_map = labels.get("refinement", {})
    complexity_map = labels.get("complexity_proxy", {})
    refinement = torch.tensor(
        [1.0 if refinement_map.get(str(int(n["face_index"])), False) else 0.0 for n in nodes_sorted],
        dtype=torch.float32,
    )
    complexity = torch.tensor(
        [float(complexity_map.get(str(int(n["face_index"])), 0.0)) for n in nodes_sorted],
        dtype=torch.float32,
    )

    data = Data(x=x, edge_index=edge_index)
    data.refinement_label = refinement
    data.complexity_label = complexity
    # Graph-level defect class (0 = clean). Shape [1] so PyG batching collates
    # one label per graph rather than broadcasting across nodes.
    data.graph_label = torch.tensor([int(labels.get("graph_label", 0))], dtype=torch.long)
    data.face_count = len(nodes_sorted)
    data.stem = sample.stem
    data.source_id = sample.source_id or sample.stem
    if sample.family_id is not None:
        data.family_id = sample.family_id
    if sample.split is not None:
        data.split = sample.split
    return data


def load_dataset(dataset_dir: Path) -> list[Data]:
    samples = discover_samples(dataset_dir)
    return [load_sample(sample) for sample in samples]


def split_train_val(data: list[Data], val_ratio: float = 0.2, seed: int = 20260513) -> tuple[list[Data], list[Data]]:
    if not data:
        return [], []
    generator = torch.Generator().manual_seed(seed)
    indices = torch.randperm(len(data), generator=generator).tolist()
    val_size = max(1, int(round(len(data) * val_ratio)))
    val_indices = set(indices[:val_size])
    train: list[Data] = []
    val: list[Data] = []
    for idx, entry in enumerate(data):
        (val if idx in val_indices else train).append(entry)
    return train, val


def source_part(stem: str) -> str:
    """Base part name for a (possibly degraded) sample stem.

    Degraded variants are named ``<source>__<defect>`` by
    generate_degraded_steps.py, so all variants of one base part share a source
    key. Splitting on this key prevents leakage (a degraded variant in train and
    its clean parent in val), which would inflate the held-out defect accuracy.
    """
    return stem.split("__", 1)[0]


def split_train_val_by_source(
    data: list[Data], val_ratio: float = 0.2, seed: int = 20260513
) -> tuple[list[Data], list[Data]]:
    """Group-aware split: every sample sharing a source part goes to one side."""
    if not data:
        return [], []
    sources = sorted({source_part(str(getattr(d, "stem", i))) for i, d in enumerate(data)})
    generator = torch.Generator().manual_seed(seed)
    order = torch.randperm(len(sources), generator=generator).tolist()
    val_count = max(1, int(round(len(sources) * val_ratio)))
    val_sources = {sources[order[i]] for i in range(val_count)}
    train: list[Data] = []
    val: list[Data] = []
    for i, entry in enumerate(data):
        key = source_part(str(getattr(entry, "stem", i)))
        (val if key in val_sources else train).append(entry)
    return train, val
