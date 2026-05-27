"""Per-face complexity scoring from B-Rep graph features.

Two backends share the same result schema:

- **BRepSAGE (learned)**: PyG GraphSAGE checkpoint, loaded when a `.pt`
  file is available. Trained by `scripts/train.py` on auto-labeled parametric
  STEPs (refinement binary + complexity regression).
- **Graph-feature heuristic**: lightweight per-face score derived from raw
  graph features (area, surface type, adjacency degree). Used when no
  checkpoint is present, so the pipeline always returns scores.

`run_brepnet_inference` resolves the backend automatically and reports
honestly which path produced the result via `model_name`, `weights_loaded`,
and `score_source`.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from simready.ml.graph_extractor import GraphData


EMBEDDING_DIM = 128
NEUTRAL_FACE_SCORE = 0.5
SIMPLE_SURFACE_TYPES = {"plane", "cylinder"}
HEURISTIC_MODEL_NAME = "graph-heuristic-complexity"
HEURISTIC_SCORE_SOURCE = "graph-feature-heuristic"
LEARNED_MODEL_NAME = "BRepSAGE-multitask"
LEARNED_SCORE_SOURCE = "brepsage-checkpoint"
DEFAULT_WEIGHTS_ENV = "SIMREADY_BREPNET_WEIGHTS"
DEFAULT_WEIGHTS_PATHS = [
    "weights/brepnet.pt",
    "weights/brepnet.pth",
    "models/brepnet.pt",
    "models/brepnet.pth",
]

try:
    import torch
except ImportError:  # pragma: no cover
    torch = None


@dataclass
class BRepNetInferenceResult:
    available: bool
    weights_loaded: bool
    weights_path: str | None
    model_name: str
    score_source: str
    per_face_scores: dict[int, float] = field(default_factory=dict)
    per_face_embeddings: dict[int, list[float]] = field(default_factory=dict)
    aggregate_score: float = NEUTRAL_FACE_SCORE
    notes: list[str] = field(default_factory=list)
    # Graph-level defect prediction (learned head only; None for the heuristic
    # backend). Non-circular signal trained on injected defect ground truth.
    predicted_defect: str | None = None
    defect_confidence: float = 0.0
    defect_probs: dict[str, float] = field(default_factory=dict)


def _adjacency_degree_map(graph: GraphData) -> dict[int, int]:
    """Precompute per-face adjacency degree once. O(N) instead of O(N^2) when
    scoring every face."""
    degree_map: dict[int, int] = {}
    for a, b in graph.adjacency:
        degree_map[a] = degree_map.get(a, 0) + 1
        degree_map[b] = degree_map.get(b, 0) + 1
    return degree_map


def _heuristic_face_score(node: dict[str, Any], graph: GraphData, degree_map: dict[int, int] | None = None) -> float:
    """Map raw graph features to a [0, 1] complexity proxy."""
    face_index = int(node.get("face_index", 0))
    area = float(node.get("area", 0.0) or 0.0)
    surface_type = str(node.get("surface_type", "other"))
    adjacency_degree = (degree_map or _adjacency_degree_map(graph)).get(face_index, 0)
    small_area_boost = 0.18 if area <= 1e-6 else min(0.18, 1.0 / (1.0 + area))
    surface_boost = 0.08 if surface_type not in SIMPLE_SURFACE_TYPES else 0.0
    degree_boost = min(0.22, adjacency_degree * 0.03)
    normal = node.get("normal", (0.0, 0.0, 0.0))
    normal_energy = min(0.1, sum(abs(float(v)) for v in normal) * 0.02)
    return min(1.0, max(0.0, 0.32 + small_area_boost + surface_boost + degree_boost + normal_energy))


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


def _candidate_weight_paths(weights_path: str | None = None) -> list[Path]:
    candidates: list[Path] = []
    if weights_path:
        candidates.append(Path(weights_path))
    env_path = os.environ.get(DEFAULT_WEIGHTS_ENV)
    if env_path:
        candidates.append(Path(env_path))
    candidates.extend(Path(path) for path in DEFAULT_WEIGHTS_PATHS)
    seen: set[str] = set()
    unique: list[Path] = []
    for candidate in candidates:
        key = str(candidate)
        if key not in seen:
            unique.append(candidate)
            seen.add(key)
    return unique


def resolve_weights_path(weights_path: str | None = None) -> Path | None:
    for candidate in _candidate_weight_paths(weights_path):
        if candidate.is_file():
            return candidate
    return None


def _run_heuristic(graph: GraphData) -> BRepNetInferenceResult:
    nodes = list(getattr(graph, "node_features", []) or [])
    if not nodes:
        return BRepNetInferenceResult(
            available=True,
            weights_loaded=False,
            weights_path=None,
            model_name=HEURISTIC_MODEL_NAME,
            score_source=HEURISTIC_SCORE_SOURCE,
            per_face_scores={},
            per_face_embeddings={},
            aggregate_score=NEUTRAL_FACE_SCORE,
            notes=["No graph nodes present; nothing to score."],
        )

    degree_map = _adjacency_degree_map(graph)
    scores: dict[int, float] = {}
    embeddings: dict[int, list[float]] = {}
    for node in nodes:
        face_index = int(node.get("face_index", 0))
        score = _heuristic_face_score(node, graph, degree_map)
        scores[face_index] = score
        embeddings[face_index] = _build_embedding(node, score)

    aggregate = sum(scores.values()) / len(scores)
    return BRepNetInferenceResult(
        available=True,
        weights_loaded=False,
        weights_path=None,
        model_name=HEURISTIC_MODEL_NAME,
        score_source=HEURISTIC_SCORE_SOURCE,
        per_face_scores=scores,
        per_face_embeddings=embeddings,
        aggregate_score=aggregate,
        notes=[
            "Heuristic per-face complexity scoring from B-Rep graph features (area, surface type, adjacency degree).",
            "Not a learned model. Drop a trained BRepSAGE checkpoint into weights/brepnet.pt to switch backends.",
        ],
    )


def _run_brepsage(graph: GraphData, weights_file: Path) -> BRepNetInferenceResult | None:
    """Run a trained BRepSAGE checkpoint, falling back to None on failure."""
    if torch is None:
        return None
    try:
        from simready.ml.dataset import build_edge_index_from_adjacency
    except ImportError:
        build_edge_index_from_adjacency = None
    try:
        from simready.ml.model import (
            DEFECT_CLASSES,
            BRepSAGE,
            ModelConfig,
            build_edge_index,
            node_feature_vector,
        )
    except ImportError:  # pragma: no cover
        return None

    nodes = list(getattr(graph, "node_features", []) or [])
    if not nodes:
        return None

    try:
        checkpoint = torch.load(str(weights_file), map_location="cpu", weights_only=False)
    except Exception:
        return None

    try:
        config = ModelConfig(**checkpoint.get("config", {}))
        model = BRepSAGE(config)
        model.load_state_dict(checkpoint["state_dict"])
        model.eval()
    except Exception:
        return None

    nodes_sorted = sorted(nodes, key=lambda n: int(n.get("face_index", 0)))
    feature_rows = [node_feature_vector(node) for node in nodes_sorted]
    x = torch.tensor(feature_rows, dtype=torch.float32)
    edge_index = build_edge_index(graph.adjacency)

    try:
        with torch.no_grad():
            output = model(x, edge_index)
    except Exception:
        return None

    complexity_tensor = output["complexity_scores"].detach()
    refinement_probs = output["refinement_probs"].detach()
    embeddings_tensor = output["embeddings"].detach()

    # Graph-level defect prediction (single graph → first row). Older checkpoints
    # without a defect head won't reach here (load_state_dict would have failed).
    predicted_defect: str | None = None
    defect_confidence = 0.0
    defect_probs: dict[str, float] = {}
    defect_tensor = output.get("defect_probs")
    if defect_tensor is not None and defect_tensor.numel():
        row = defect_tensor.detach()[0]
        defect_probs = {DEFECT_CLASSES[i]: float(row[i]) for i in range(len(DEFECT_CLASSES))}
        best = int(row.argmax())
        predicted_defect = DEFECT_CLASSES[best]
        defect_confidence = float(row[best])

    scores: dict[int, float] = {}
    embeddings: dict[int, list[float]] = {}
    for row, node in enumerate(nodes_sorted):
        face_index = int(node.get("face_index", 0))
        # Fuse the two learned heads: refinement signal dominates when high,
        # complexity provides a continuous baseline.
        learned_score = min(
            1.0,
            max(0.0, 0.5 * float(refinement_probs[row]) + 0.5 * float(complexity_tensor[row])),
        )
        scores[face_index] = learned_score
        embedding_vec = embeddings_tensor[row].tolist()
        if len(embedding_vec) < EMBEDDING_DIM:
            embedding_vec = (embedding_vec + [0.0] * EMBEDDING_DIM)[:EMBEDDING_DIM]
        else:
            embedding_vec = embedding_vec[:EMBEDDING_DIM]
        embeddings[face_index] = [float(v) for v in embedding_vec]

    aggregate = sum(scores.values()) / len(scores) if scores else NEUTRAL_FACE_SCORE
    return BRepNetInferenceResult(
        available=True,
        weights_loaded=True,
        weights_path=str(weights_file),
        model_name=LEARNED_MODEL_NAME,
        score_source=LEARNED_SCORE_SOURCE,
        per_face_scores=scores,
        per_face_embeddings=embeddings,
        aggregate_score=aggregate,
        predicted_defect=predicted_defect,
        defect_confidence=defect_confidence,
        defect_probs=defect_probs,
        notes=[
            "Learned BRepSAGE checkpoint (multi-task: graph-level defect classification + "
            "per-face refinement + complexity regression).",
            "Trained by scripts/train.py on parametric + degraded STEPs; see weights/metrics.json.",
        ],
    )


def run_brepnet_inference(graph: GraphData, weights_path: str | None = None) -> BRepNetInferenceResult:
    """Score every face in the graph using the best available backend."""
    resolved = resolve_weights_path(weights_path)
    if resolved is not None:
        learned = _run_brepsage(graph, resolved)
        if learned is not None:
            return learned
    return _run_heuristic(graph)
