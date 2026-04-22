from simready.ml.graph_extractor import extract_brep_graph
from simready.parser import parse_geometry
from simready.splitter import split_bodies
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
    assert "adjacency_count" in graph.metadata


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


def test_extract_brep_graph_node_features_include_phase2_fields():
    validation = validate_step_file("tests/data/smoke_box.step")
    graph = extract_brep_graph(validation.shape)

    assert graph.node_features
    node = graph.node_features[0]
    assert set(node) >= {"face_index", "surface_type", "surface_type_one_hot", "area", "centroid", "normal", "mean_curvature", "uv_bounds"}
    assert len(node["surface_type_one_hot"]) == len(graph.metadata["surface_type_labels"])


def test_extract_brep_graph_edge_features_include_dihedral_metadata():
    validation = validate_step_file("tests/data/smoke_box.step")
    graph = extract_brep_graph(validation.shape)

    assert graph.edge_features
    edge = graph.edge_features[0]
    assert set(edge) >= {"edge_index", "length", "midpoint_curvature", "connected_faces", "convexity", "dihedral_angle", "dihedral_signal"}


def test_extract_brep_graph_multi_body_per_body_extraction():
    validation = validate_step_file("tests/data/multi_body.step")
    assert validation.is_valid is True

    split = split_bodies(validation.shape)
    assert split.body_count >= 2

    per_body_graphs = [extract_brep_graph(body) for body in split.bodies]
    assert len(per_body_graphs) == split.body_count
    assert all(graph.metadata["solid_count"] == 1 for graph in per_body_graphs)
    assert sum(graph.metadata["face_count"] for graph in per_body_graphs) == extract_brep_graph(validation.shape).metadata["face_count"]
