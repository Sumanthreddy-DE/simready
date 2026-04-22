from simready.ml.brepnet import EMBEDDING_DIM, NEUTRAL_FACE_SCORE, run_brepnet_inference
from simready.ml.graph_extractor import extract_brep_graph
from simready.validator import validate_step_file


def test_brepnet_fallback_returns_per_face_scores_and_embeddings():
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


def test_brepnet_fallback_handles_empty_graph():
    class EmptyGraph:
        node_features = []
        adjacency = []

    result = run_brepnet_inference(EmptyGraph())
    assert result.per_face_scores == {}
    assert result.aggregate_score == NEUTRAL_FACE_SCORE
