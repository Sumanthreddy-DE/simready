"""Per-face complexity scoring from B-Rep graph features.

Phase 2 status: graph-feature heuristic only. A real learned BRepNet (GNN)
will replace this in Phase 2A Task 4 once weights are trained on the
Fusion360 Gallery auto-label dataset (Task 6). The module name and field
shape are kept stable so that callers do not change when the heuristic is
swapped for a real model.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from simready.ml.graph_extractor import GraphData


EMBEDDING_DIM = 128
NEUTRAL_FACE_SCORE = 0.5
SIMPLE_SURFACE_TYPES = {"plane", "cylinder"}
MODEL_NAME = "graph-heuristic-complexity"
SCORE_SOURCE = "graph-feature-heuristic"


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


def _heuristic_face_score(node: dict[str, Any], graph: GraphData) -> float:
    """Map raw graph features to a [0, 1] complexity proxy.

    Not learned. Picked to be roughly monotone in features a real BRepNet
    would key on: small area, non-trivial surface type, high adjacency
    degree.
    """
    face_index = int(node.get("face_index", 0))
    area = float(node.get("area", 0.0) or 0.0)
    surface_type = str(node.get("surface_type", "other"))
    adjacency_degree = sum(1 for pair in graph.adjacency if face_index in pair)
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


def run_brepnet_inference(graph: GraphData, weights_path: str | None = None) -> BRepNetInferenceResult:
    """Score every face in the graph.

    `weights_path` is accepted for forward compatibility with a future
    learned model. It is currently ignored — the heuristic is the only
    backend.
    """
    nodes = list(getattr(graph, "node_features", []) or [])
    if not nodes:
        return BRepNetInferenceResult(
            available=True,
            weights_loaded=False,
            weights_path=None,
            model_name=MODEL_NAME,
            score_source=SCORE_SOURCE,
            per_face_scores={},
            per_face_embeddings={},
            aggregate_score=NEUTRAL_FACE_SCORE,
            notes=["No graph nodes present; nothing to score."],
        )

    scores: dict[int, float] = {}
    embeddings: dict[int, list[float]] = {}
    for node in nodes:
        face_index = int(node.get("face_index", 0))
        score = _heuristic_face_score(node, graph)
        scores[face_index] = score
        embeddings[face_index] = _build_embedding(node, score)

    aggregate = sum(scores.values()) / len(scores)
    return BRepNetInferenceResult(
        available=True,
        weights_loaded=False,
        weights_path=None,
        model_name=MODEL_NAME,
        score_source=SCORE_SOURCE,
        per_face_scores=scores,
        per_face_embeddings=embeddings,
        aggregate_score=aggregate,
        notes=[
            "Heuristic per-face complexity scoring from B-Rep graph features (area, surface type, adjacency degree).",
            "Not a learned model. Replace with trained BRepNet once Phase 2A Task 6 (auto-label) and Task 7 (fine-tune) ship.",
        ],
    )
