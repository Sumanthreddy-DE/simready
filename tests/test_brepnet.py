import simready.ml.brepnet as brepnet_module
from simready.ml.brepnet import EMBEDDING_DIM, NEUTRAL_FACE_SCORE, run_brepnet_inference
from simready.ml.graph_extractor import extract_brep_graph
from simready.validator import validate_step_file


def _force_heuristic(monkeypatch):
    """Pin run_brepnet_inference to the heuristic backend regardless of
    whether `weights/brepnet.pt` exists on disk."""
    monkeypatch.setattr(brepnet_module, "DEFAULT_WEIGHTS_PATHS", [])
    monkeypatch.delenv("SIMREADY_BREPNET_WEIGHTS", raising=False)


def test_brepnet_fallback_returns_per_face_scores_and_embeddings(monkeypatch):
    _force_heuristic(monkeypatch)
    validation = validate_step_file("tests/data/smoke_box.step")
    assert validation.is_valid is True

    graph = extract_brep_graph(validation.shape)
    result = run_brepnet_inference(graph)

    assert result.weights_loaded is False
    assert result.model_name
    assert result.per_face_scores
    assert len(result.per_face_scores) == len(graph.node_features)
    assert set(result.per_face_scores) == {node["face_index"] for node in graph.node_features}
    assert result.per_face_embeddings
    assert len(next(iter(result.per_face_embeddings.values()))) == EMBEDDING_DIM
    assert 0.0 <= result.aggregate_score <= 1.0


def test_brepnet_fallback_handles_empty_graph(monkeypatch):
    _force_heuristic(monkeypatch)

    class EmptyGraph:
        node_features = []
        adjacency = []

    result = run_brepnet_inference(EmptyGraph())
    assert result.per_face_scores == {}
    assert result.aggregate_score == NEUTRAL_FACE_SCORE


def test_brepsage_backend_engages_when_checkpoint_exists(tmp_path):
    """When a usable BRepSAGE checkpoint is present, run_brepnet_inference
    must load it instead of falling back to the heuristic."""
    import torch
    from simready.ml.model import BRepSAGE, ModelConfig

    config = ModelConfig(hidden_dim=8, num_layers=1)
    model = BRepSAGE(config)
    checkpoint_path = tmp_path / "brepnet.pt"
    torch.save(
        {
            "state_dict": model.state_dict(),
            "config": {"in_dim": config.in_dim, "hidden_dim": config.hidden_dim, "num_layers": config.num_layers, "dropout": config.dropout},
        },
        checkpoint_path,
    )

    validation = validate_step_file("tests/data/smoke_box.step")
    graph = extract_brep_graph(validation.shape)
    result = run_brepnet_inference(graph, weights_path=str(checkpoint_path))

    assert result.weights_loaded is True
    assert result.weights_path == str(checkpoint_path)
    assert "brepsage" in result.model_name.lower() or "BRepSAGE" in result.model_name
    assert len(result.per_face_scores) == len(graph.node_features)
    assert all(0.0 <= score <= 1.0 for score in result.per_face_scores.values())
