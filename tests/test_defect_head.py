"""Tests for the graph-level defect-classification head (non-circular GNN signal).

The defect head is trained on injected ground-truth tags from
`scripts/generate_degraded_steps.py` (part-level: open_shell / sliver_face /
self_intersection / clean), NOT on the rule-derived per-face label — so its
accuracy is a non-circular metric, unlike the refinement head.
"""

from __future__ import annotations

import json

import torch

from simready.ml.model import (
    DEFECT_CLASSES,
    NUM_DEFECT_CLASSES,
    BRepSAGE,
    ModelConfig,
    build_edge_index,
)


def test_defect_class_schema_clean_is_zero():
    assert DEFECT_CLASSES[0] == "clean"
    assert NUM_DEFECT_CLASSES == len(DEFECT_CLASSES)
    assert "open_shell" in DEFECT_CLASSES
    assert "self_intersection" in DEFECT_CLASSES
    assert "sliver_face" in DEFECT_CLASSES


def test_forward_emits_defect_logits_single_graph():
    model = BRepSAGE(ModelConfig(hidden_dim=8, num_layers=1))
    model.eval()
    x = torch.rand(5, ModelConfig().in_dim)
    edge_index = build_edge_index([(0, 1), (1, 2), (2, 3), (3, 4)])
    out = model(x, edge_index)
    # Per-node heads keep their shapes.
    assert out["refinement_logits"].shape == (5,)
    assert out["complexity_scores"].shape == (5,)
    # New graph-level head: one logit vector per graph. Single graph -> [1, C].
    assert out["defect_logits"].shape == (1, NUM_DEFECT_CLASSES)


def test_forward_defect_logits_batched():
    """With a PyG batch vector mapping nodes to 2 graphs, expect [2, C]."""
    model = BRepSAGE(ModelConfig(hidden_dim=8, num_layers=1))
    model.eval()
    x = torch.rand(6, ModelConfig().in_dim)
    edge_index = build_edge_index([(0, 1), (1, 2), (3, 4), (4, 5)])
    batch = torch.tensor([0, 0, 0, 1, 1, 1], dtype=torch.long)
    out = model(x, edge_index, batch=batch)
    assert out["defect_logits"].shape == (2, NUM_DEFECT_CLASSES)


def test_defect_class_from_tags(tmp_path):
    from scripts.auto_label import defect_class_from_tags

    assert defect_class_from_tags(None) == 0  # no tags -> clean
    assert defect_class_from_tags({"defect_tags": ["open_shell"]}) == DEFECT_CLASSES.index("open_shell")
    assert defect_class_from_tags({"defect_tags": ["self_intersection"]}) == DEFECT_CLASSES.index("self_intersection")
    assert defect_class_from_tags({"defect_tags": ["unknown_defect"]}) == 0  # unknown -> clean
    assert defect_class_from_tags({}) == 0


def test_dataset_loads_graph_label(tmp_path):
    """load_sample must surface graph_label as a long scalar (default 0)."""
    from simready.ml.dataset import SampleMetadata, load_sample

    graph = {
        "node_features": [
            {"face_index": 0, "surface_type": "plane", "area": 1.0, "normal": [0, 0, 1]},
            {"face_index": 1, "surface_type": "cylinder", "area": 2.0, "normal": [1, 0, 0]},
        ],
        "adjacency": [[0, 1]],
    }
    labels = {
        "refinement": {"0": True, "1": False},
        "complexity_proxy": {"0": 0.5, "1": 0.2},
        "graph_label": DEFECT_CLASSES.index("sliver_face"),
    }
    gpath = tmp_path / "part.graph.json"
    lpath = tmp_path / "part.labels.json"
    gpath.write_text(json.dumps(graph), encoding="utf-8")
    lpath.write_text(json.dumps(labels), encoding="utf-8")

    data = load_sample(SampleMetadata("part", gpath, lpath, face_count=2))
    assert int(data.graph_label) == DEFECT_CLASSES.index("sliver_face")
    assert data.graph_label.dtype == torch.long


def test_dataset_graph_label_defaults_to_clean(tmp_path):
    from simready.ml.dataset import SampleMetadata, load_sample

    graph = {
        "node_features": [{"face_index": 0, "surface_type": "plane", "area": 1.0, "normal": [0, 0, 1]}],
        "adjacency": [],
    }
    labels = {"refinement": {"0": False}, "complexity_proxy": {"0": 0.1}}  # no graph_label
    gpath = tmp_path / "part.graph.json"
    lpath = tmp_path / "part.labels.json"
    gpath.write_text(json.dumps(graph), encoding="utf-8")
    lpath.write_text(json.dumps(labels), encoding="utf-8")

    data = load_sample(SampleMetadata("part", gpath, lpath, face_count=1))
    assert int(data.graph_label) == 0


def test_inference_exposes_predicted_defect(tmp_path):
    """run_brepnet_inference must surface a graph-level defect prediction when a
    checkpoint with the defect head is loaded."""
    from simready.ml.brepnet import run_brepnet_inference
    from simready.ml.graph_extractor import extract_brep_graph
    from simready.validator import validate_step_file

    config = ModelConfig(hidden_dim=8, num_layers=1)
    model = BRepSAGE(config)
    ckpt = tmp_path / "brepnet.pt"
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
        ckpt,
    )
    validation = validate_step_file("tests/data/smoke_box.step")
    graph = extract_brep_graph(validation.shape)
    result = run_brepnet_inference(graph, weights_path=str(ckpt))

    assert result.weights_loaded is True
    assert result.predicted_defect in DEFECT_CLASSES
    assert 0.0 <= result.defect_confidence <= 1.0
    assert set(result.defect_probs) == set(DEFECT_CLASSES)
    assert abs(sum(result.defect_probs.values()) - 1.0) < 1e-4
