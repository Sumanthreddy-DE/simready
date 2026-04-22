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
    assert graph.metadata["extractor"] == "custom-brepnet-phase2"
    assert "coedge_count" in graph.metadata


def test_extract_brep_graph_multi_body_works():
    validation = validate_step_file("tests/data/multi_body.step")
    assert validation.is_valid is True

    graph = extract_brep_graph(validation.shape)
    assert graph.metadata["solid_count"] >= 2
    assert len(graph.node_features) > 0


def test_extract_brep_graph_emits_topology_maps():
    validation = validate_step_file("tests/data/smoke_box.step")
    graph = extract_brep_graph(validation.shape)

    assert isinstance(graph.face_to_coedges, dict)
    assert isinstance(graph.edge_to_coedges, dict)
    assert isinstance(graph.coedge_to_face, dict)
    assert isinstance(graph.coedge_to_edge, dict)
    assert isinstance(graph.coedge_to_mate, dict)
    assert len(graph.coedge_features) >= 0
