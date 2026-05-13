"""PyG GraphSAGE multi-task per-face model for B-Rep analysis.

Two heads on a shared GraphSAGE encoder:

- `refinement_logits`  — per-face binary classification (rule-derived label).
- `complexity_scores`  — per-face scalar regression (graph-feature proxy in [0, 1]).

Designed for CPU training on the parametric SimReady dataset (~500 graphs).
Keep the model small so 5-10 epochs are seconds on CPU.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import torch
from torch import nn
from torch_geometric.nn import SAGEConv


SURFACE_TYPES = ["plane", "cylinder", "cone", "sphere", "torus", "bspline", "other"]
NODE_FEATURE_DIM = len(SURFACE_TYPES) + 5  # one-hot + log_area + normal_mag + mean_curvature + uv_u + uv_v
DEFAULT_HIDDEN_DIM = 32
DEFAULT_NUM_LAYERS = 2


@dataclass
class ModelConfig:
    in_dim: int = NODE_FEATURE_DIM
    hidden_dim: int = DEFAULT_HIDDEN_DIM
    num_layers: int = DEFAULT_NUM_LAYERS
    dropout: float = 0.1


class BRepSAGE(nn.Module):
    """Two-headed GraphSAGE over face-adjacency graphs."""

    def __init__(self, config: ModelConfig | None = None):
        super().__init__()
        cfg = config or ModelConfig()
        self.config = cfg

        self.convs = nn.ModuleList()
        last_dim = cfg.in_dim
        for _ in range(cfg.num_layers):
            self.convs.append(SAGEConv(last_dim, cfg.hidden_dim))
            last_dim = cfg.hidden_dim

        self.refinement_head = nn.Linear(cfg.hidden_dim, 1)
        self.complexity_head = nn.Linear(cfg.hidden_dim, 1)
        self.dropout = nn.Dropout(cfg.dropout)
        self.act = nn.ReLU()

    def encode(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        h = x
        for conv in self.convs:
            h = conv(h, edge_index)
            h = self.act(h)
            h = self.dropout(h)
        return h

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> dict[str, torch.Tensor]:
        embeddings = self.encode(x, edge_index)
        refinement_logits = self.refinement_head(embeddings).squeeze(-1)
        complexity_scores = torch.sigmoid(self.complexity_head(embeddings)).squeeze(-1)
        return {
            "embeddings": embeddings,
            "refinement_logits": refinement_logits,
            "refinement_probs": torch.sigmoid(refinement_logits),
            "complexity_scores": complexity_scores,
        }


def node_feature_vector(node: dict[str, Any]) -> list[float]:
    """Convert one graph_extractor node payload into the GNN input vector.

    Order matches NODE_FEATURE_DIM. Stays stable across training and inference.
    """
    surface_type = str(node.get("surface_type", "other"))
    one_hot = [1.0 if surface_type == name else 0.0 for name in SURFACE_TYPES]

    area = float(node.get("area", 0.0) or 0.0)
    log_area = float(torch.log1p(torch.tensor(max(area, 0.0))))

    normal = node.get("normal", (0.0, 0.0, 0.0))
    normal_mag = float(sum(abs(float(v)) for v in normal))

    curvature = float(node.get("mean_curvature", 0.0) or 0.0)

    uv = node.get("uv_bounds", (0.0, 0.0, 0.0, 0.0))
    try:
        uv_u = float(uv[1]) - float(uv[0])
        uv_v = float(uv[3]) - float(uv[2])
    except (IndexError, TypeError, ValueError):
        uv_u, uv_v = 0.0, 0.0

    return [*one_hot, log_area, normal_mag, curvature, uv_u, uv_v]


def build_edge_index(adjacency: list[tuple[int, int]] | list[list[int]]) -> torch.Tensor:
    """Materialize an undirected adjacency list into a PyG edge_index tensor."""
    if not adjacency:
        return torch.zeros((2, 0), dtype=torch.long)
    src: list[int] = []
    dst: list[int] = []
    for pair in adjacency:
        a, b = int(pair[0]), int(pair[1])
        src.append(a)
        dst.append(b)
        src.append(b)
        dst.append(a)
    return torch.tensor([src, dst], dtype=torch.long)
