from simready.ml.graph_extractor import extract_brep_graph
from simready.parser import parse_geometry
from simready.validator import validate_step_file


def test_extract_brep_graph_smoke_box():
    validation = validate_step_file("tests/data/smoke_box.step")
    assert validation.is_valid is True

    graph = extract_brep_graph(validation.shape)
    geometry = parse_geometry(validation.shape)

    assert graph.metadata["face_count"] == geometry.face_count
    assert len(graph.node_features) == geometry.face_count
    assert isinstance(graph.edge_features, list)
    assert isinstance(graph.adjacency, list)


def test_extract_brep_graph_multi_body_works():
    validation = validate_step_file("tests/data/multi_body.step")
    assert validation.is_valid is True

    graph = extract_brep_graph(validation.shape)
    assert graph.metadata["solid_count"] >= 2
    assert len(graph.node_features) > 0
