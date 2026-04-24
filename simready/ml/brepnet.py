"""BRepNet inference scaffolding with graceful CPU fallback."""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from simready.ml.graph_extractor import GraphData

try:
    import torch
except ImportError:  # pragma: no cover
    torch = None


DEFAULT_WEIGHTS_ENV = "SIMREADY_BREPNET_WEIGHTS"
DEFAULT_WEIGHTS_PATHS = [
    "weights/brepnet.pt",
    "weights/brepnet.pth",
    "models/brepnet.pt",
    "models/brepnet.pth",
]
EMBEDDING_DIM = 128
NEUTRAL_FACE_SCORE = 0.5
SIMPLE_SURFACE_TYPES = {"plane", "cylinder"}


@dataclass
class BRepNetInferenceResult:
    available: bool
    weights_loaded: bool
    weights_path: str | None
    model_name: str
    score_source: str
    per_face_scores: dict[int, float] = field(default_factory=dict)
    per_face_embeddings: dict[int, list[float]] = field(default_factory=dict)
    aggregate_score: float = 0.5
    notes: list[str] = field(default_factory=list)


class HeuristicBRepNetModel:
    """Lightweight fallback that mimics per-face complexity scoring."""

    model_name = "heuristic-brepnet-fallback"

    def infer(self, graph: GraphData) -> BRepNetInferenceResult:
        scores: dict[int, float] = {}
        embeddings: dict[int, list[float]] = {}
        degree_map = _adjacency_degree_map(graph)

        for node in graph.node_features:
            face_index = int(node.get("face_index", 0))
            area = float(node.get("area", 0.0) or 0.0)
            normal = node.get("normal", (0.0, 0.0, 0.0))
            surface_type = str(node.get("surface_type", "other"))
            adjacency_degree = degree_map.get(face_index, 0)
            small_area_boost = 0.18 if area <= 1e-6 else min(0.18, 1.0 / (1.0 + area))
            surface_boost = 0.08 if surface_type not in SIMPLE_SURFACE_TYPES else 0.0
            degree_boost = min(0.22, adjacency_degree * 0.03)
            normal_energy = min(0.1, sum(abs(float(v)) for v in normal) * 0.02)
            score = min(1.0, max(0.0, 0.32 + small_area_boost + surface_boost + degree_boost + normal_energy))
            scores[face_index] = score
            embeddings[face_index] = _build_embedding(node, score)

        aggregate = sum(scores.values()) / len(scores) if scores else NEUTRAL_FACE_SCORE
        return BRepNetInferenceResult(
            available=False,
            weights_loaded=False,
            weights_path=None,
            model_name=self.model_name,
            score_source="heuristic-fallback",
            per_face_scores=scores,
            per_face_embeddings=embeddings,
            aggregate_score=aggregate,
            notes=[
                "BRepNet weights not found. Using heuristic fallback scores.",
                "Production deployment should use downloaded or fine-tuned weights.",
            ],
        )


class TorchBRepNetAdapter:
    """Small adapter that loads a torch checkpoint when available."""

    model_name = "brepnet-checkpoint-adapter"

    def __init__(self, checkpoint: Any, weights_path: str):
        self.checkpoint = checkpoint
        self.weights_path = weights_path

    def infer(self, graph: GraphData) -> BRepNetInferenceResult:
        checkpoint_meta = self.checkpoint if isinstance(self.checkpoint, dict) else {}
        configured_dim = int(checkpoint_meta.get("embedding_dim", EMBEDDING_DIM) or EMBEDDING_DIM)
        bias = float(checkpoint_meta.get("complexity_bias", 0.0) or 0.0)
        scale = float(checkpoint_meta.get("complexity_scale", 1.0) or 1.0)
        degree_map = _adjacency_degree_map(graph)

        scores: dict[int, float] = {}
        embeddings: dict[int, list[float]] = {}
        for node in graph.node_features:
            face_index = int(node.get("face_index", 0))
            base_score = _heuristic_face_score(node, graph, degree_map)
            score = min(1.0, max(0.0, (base_score * scale) + bias))
            scores[face_index] = score
            embeddings[face_index] = _build_embedding(node, score, configured_dim)

        aggregate = sum(scores.values()) / len(scores) if scores else NEUTRAL_FACE_SCORE
        return BRepNetInferenceResult(
            available=True,
            weights_loaded=True,
            weights_path=self.weights_path,
            model_name=self.model_name,
            score_source="checkpoint-adapter",
            per_face_scores=scores,
            per_face_embeddings=embeddings,
            aggregate_score=aggregate,
            notes=[
                "Loaded BRepNet-compatible checkpoint metadata.",
                "Current adapter uses checkpoint scaling over graph-derived heuristic features until full model wiring lands.",
            ],
        )


def _build_embedding(node: dict[str, Any], score: float, dims: int = EMBEDDING_DIM) -> list[float]:
    base = [
        float(score),
        float(node.get("area", 0.0) or 0.0),
        float(sum(abs(v) for v in node.get("normal", (0.0, 0.0, 0.0)))),
        float(len(node.get("surface_type_one_hot", []))),
    ]
    embedding: list[float] = []
    while len(embedding) < dims:
        for index, value in enumerate(base):
            embedding.append(float(math.tanh(value + (index * 0.1))))
            if len(embedding) == dims:
                break
    return embedding


def _adjacency_degree_map(graph: GraphData) -> dict[int, int]:
    degree_map: dict[int, int] = {}
    for a, b in graph.adjacency:
        degree_map[a] = degree_map.get(a, 0) + 1
        degree_map[b] = degree_map.get(b, 0) + 1
    return degree_map


def _heuristic_face_score(node: dict[str, Any], graph: GraphData, degree_map: dict[int, int] | None = None) -> float:
    face_index = int(node.get("face_index", 0))
    area = float(node.get("area", 0.0) or 0.0)
    surface_type = str(node.get("surface_type", "other"))
    adjacency_degree = (degree_map or _adjacency_degree_map(graph)).get(face_index, 0)
    small_area_boost = 0.18 if area <= 1e-6 else min(0.18, 1.0 / (1.0 + area))
    surface_boost = 0.08 if surface_type not in SIMPLE_SURFACE_TYPES else 0.0
    degree_boost = min(0.22, adjacency_degree * 0.03)
    return min(1.0, max(0.0, 0.32 + small_area_boost + surface_boost + degree_boost))


def _candidate_weight_paths(weights_path: str | None = None) -> list[Path]:
    candidates: list[Path] = []
    if weights_path:
        candidates.append(Path(weights_path))
    env_path = os.environ.get(DEFAULT_WEIGHTS_ENV)
    if env_path:
        candidates.append(Path(env_path))
    candidates.extend(Path(path) for path in DEFAULT_WEIGHTS_PATHS)

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        resolved = str(candidate)
        if resolved not in seen:
            unique.append(candidate)
            seen.add(resolved)
    return unique


def resolve_weights_path(weights_path: str | None = None) -> Path | None:
    for candidate in _candidate_weight_paths(weights_path):
        if candidate.is_file():
            return candidate
    return None


def load_brepnet_model(weights_path: str | None = None) -> HeuristicBRepNetModel | TorchBRepNetAdapter:
    resolved = resolve_weights_path(weights_path)
    if resolved is None or torch is None:
        return HeuristicBRepNetModel()

    try:
        checkpoint = torch.load(str(resolved), map_location="cpu")
    except Exception:
        try:
            checkpoint = json.loads(resolved.read_text(encoding="utf-8"))
        except Exception:
            return HeuristicBRepNetModel()

    return TorchBRepNetAdapter(checkpoint=checkpoint, weights_path=str(resolved))


def run_brepnet_inference(graph: GraphData, weights_path: str | None = None) -> BRepNetInferenceResult:
    model = load_brepnet_model(weights_path=weights_path)
    result = model.infer(graph)
    if not result.per_face_scores:
        result.per_face_scores = {int(node.get("face_index", 0)): NEUTRAL_FACE_SCORE for node in graph.node_features}
    if not result.per_face_embeddings:
        result.per_face_embeddings = {
            int(node.get("face_index", 0)): _build_embedding(node, result.per_face_scores[int(node.get("face_index", 0))])
            for node in graph.node_features
        }
    if result.per_face_scores:
        result.aggregate_score = sum(result.per_face_scores.values()) / len(result.per_face_scores)
    return result
