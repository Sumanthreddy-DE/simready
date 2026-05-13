"""B-Rep graph extraction for Phase 2 ML integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import acos, sqrt
from typing import Any

try:
    from OCC.Core.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
except ImportError:  # pragma: no cover
    BRepAdaptor_Curve = None
    BRepAdaptor_Surface = None

try:
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.GProp import GProp_GProps
except ImportError:  # pragma: no cover
    brepgprop = None
    GProp_GProps = None


try:
    from OCC.Core.GeomLProp import GeomLProp_SLProps
except ImportError:  # pragma: no cover
    GeomLProp_SLProps = None

try:
    from OCC.Core.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_FORWARD, TopAbs_REVERSED, TopAbs_WIRE
except ImportError:  # pragma: no cover
    TopAbs_EDGE = TopAbs_FACE = TopAbs_FORWARD = TopAbs_REVERSED = TopAbs_WIRE = None

try:
    from OCC.Core.TopExp import TopExp_Explorer
except ImportError:  # pragma: no cover
    TopExp_Explorer = None

try:
    from OCC.Core.TopoDS import topods
except ImportError:  # pragma: no cover
    topods = None

try:
    from OCC.Extend.TopologyUtils import TopologyExplorer, WireExplorer
except ImportError:  # pragma: no cover
    TopologyExplorer = None
    WireExplorer = None

try:
    from OCC.Core.GeomAbs import GeomAbs_BSplineSurface, GeomAbs_Cone, GeomAbs_Cylinder, GeomAbs_Plane, GeomAbs_Sphere, GeomAbs_Torus
except ImportError:  # pragma: no cover
    GeomAbs_BSplineSurface = GeomAbs_Cone = GeomAbs_Cylinder = GeomAbs_Plane = GeomAbs_Sphere = GeomAbs_Torus = None

try:
    from OCC.Core.TopTools import TopTools_IndexedMapOfShape
except ImportError:  # pragma: no cover
    TopTools_IndexedMapOfShape = None

from simready.occ_utils import build_edge_face_map, count_topology, edge_length, uv_bounds


SURFACE_TYPE_MAP = {
    GeomAbs_Plane: "plane",
    GeomAbs_Cylinder: "cylinder",
    GeomAbs_Cone: "cone",
    GeomAbs_Sphere: "sphere",
    GeomAbs_Torus: "torus",
    GeomAbs_BSplineSurface: "bspline",
}

SURFACE_TYPE_ONE_HOT = ["plane", "cylinder", "cone", "sphere", "torus", "bspline", "other"]


@dataclass
class GraphData:
    node_features: list[dict[str, Any]] = field(default_factory=list)
    edge_features: list[dict[str, Any]] = field(default_factory=list)
    coedge_features: list[dict[str, Any]] = field(default_factory=list)
    adjacency: list[tuple[int, int]] = field(default_factory=list)
    face_to_coedges: dict[int, list[int]] = field(default_factory=dict)
    edge_to_coedges: dict[int, list[int]] = field(default_factory=dict)
    coedge_to_face: dict[int, int] = field(default_factory=dict)
    coedge_to_edge: dict[int, int] = field(default_factory=dict)
    coedge_to_mate: dict[int, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class FaceEntry:
    index: int
    face: Any
    hash_code: int


@dataclass
class EdgeEntry:
    index: int
    edge: Any
    hash_code: int


def _shape_hash(shape: Any) -> int | None:
    try:
        return int(shape.HashCode(2147483647))
    except Exception:
        return None


def _iter_faces(shape: Any) -> list[FaceEntry]:
    if TopExp_Explorer is None or TopAbs_FACE is None:
        return []
    try:
        explorer = TopExp_Explorer(shape, TopAbs_FACE)
    except Exception:
        return []

    faces: list[FaceEntry] = []
    index = 0
    while explorer.More():
        face = topods.Face(explorer.Current()) if topods is not None else explorer.Current()
        faces.append(FaceEntry(index=index, face=face, hash_code=_shape_hash(face) or index))
        index += 1
        explorer.Next()
    return faces


def _iter_edges(shape: Any) -> list[EdgeEntry]:
    explorer = _safe_topology_explorer(shape)
    if explorer is not None:
        edges: list[EdgeEntry] = []
        for index, edge in enumerate(explorer.edges()):
            edges.append(EdgeEntry(index=index, edge=edge, hash_code=_shape_hash(edge) or index))
        return edges

    if TopExp_Explorer is None or TopAbs_EDGE is None:
        return []
    try:
        exp = TopExp_Explorer(shape, TopAbs_EDGE)
    except Exception:
        return []

    edges = []
    seen: set[int] = set()
    index = 0
    while exp.More():
        edge = topods.Edge(exp.Current()) if topods is not None else exp.Current()
        h = _shape_hash(edge) or index
        if h not in seen:
            seen.add(h)
            edges.append(EdgeEntry(index=index, edge=edge, hash_code=h))
            index += 1
        exp.Next()
    return edges


def _surface_type_name(face: Any) -> str:
    if BRepAdaptor_Surface is None:
        return "unknown"
    try:
        surface = BRepAdaptor_Surface(face, True)
        return SURFACE_TYPE_MAP.get(surface.GetType(), "other")
    except Exception:
        return "unknown"


def _surface_type_vector(name: str) -> list[float]:
    canonical = name if name in SURFACE_TYPE_ONE_HOT else "other"
    return [1.0 if key == canonical else 0.0 for key in SURFACE_TYPE_ONE_HOT]


def _face_area(face: Any) -> float:
    if brepgprop is None or GProp_GProps is None:
        return 0.0
    props = GProp_GProps()
    try:
        brepgprop.SurfaceProperties(face, props)
        return float(props.Mass())
    except Exception:
        return 0.0


def _face_centroid(face: Any) -> tuple[float, float, float]:
    if brepgprop is None or GProp_GProps is None:
        return (0.0, 0.0, 0.0)
    props = GProp_GProps()
    try:
        brepgprop.SurfaceProperties(face, props)
        center = props.CentreOfMass()
        return (float(center.X()), float(center.Y()), float(center.Z()))
    except Exception:
        return (0.0, 0.0, 0.0)




def _face_normal(face: Any) -> tuple[float, float, float]:
    if BRepAdaptor_Surface is None or GeomLProp_SLProps is None:
        return (0.0, 0.0, 0.0)
    try:
        surface = BRepAdaptor_Surface(face, True)
        umin, umax, vmin, vmax = uv_bounds(face)
        u = (umin + umax) / 2.0
        v = (vmin + vmax) / 2.0
        props = GeomLProp_SLProps(surface.Surface().Surface(), u, v, 1, 1e-6)
        if not props.IsNormalDefined():
            return (0.0, 0.0, 0.0)
        normal = props.Normal()
        return (float(normal.X()), float(normal.Y()), float(normal.Z()))
    except Exception:
        return (0.0, 0.0, 0.0)


def _vector_dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _vector_norm(a: tuple[float, float, float]) -> float:
    return sqrt(_vector_dot(a, a))


def _edge_midpoint_curvature(edge: Any) -> float:
    if BRepAdaptor_Curve is None:
        return 0.0
    try:
        curve = BRepAdaptor_Curve(edge)
        first = curve.FirstParameter()
        last = curve.LastParameter()
        mid = (first + last) / 2.0
        return float(abs(curve.Curvature(mid)))
    except Exception:
        return 0.0


def _coedge_orientation_value(oriented_edge: Any) -> int:
    try:
        orientation = oriented_edge.Orientation()
        if orientation == TopAbs_FORWARD:
            return 1
        if orientation == TopAbs_REVERSED:
            return -1
    except Exception:
        pass
    return 0


def _convexity_from_normals(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[str, float | None, float | None]:
    norm_a = _vector_norm(a)
    norm_b = _vector_norm(b)
    if norm_a == 0.0 or norm_b == 0.0:
        return ("unknown", None, None)
    cos_theta = max(-1.0, min(1.0, _vector_dot(a, b) / (norm_a * norm_b)))
    angle_radians = acos(cos_theta)
    angle_degrees = angle_radians * 180.0 / 3.141592653589793
    if cos_theta > 0.98:
        return ("smooth", angle_degrees, cos_theta)
    if cos_theta >= 0.0:
        return ("convex", angle_degrees, cos_theta)
    return ("concave", angle_degrees, cos_theta)


def _safe_topology_explorer(shape: Any):
    """Return a TopologyExplorer with ignore_orientation=True for unique edges."""
    if TopologyExplorer is None:
        return None
    try:
        return TopologyExplorer(shape, ignore_orientation=True)
    except TypeError:
        try:
            return TopologyExplorer(shape)
        except Exception:
            return None
    except Exception:
        return None


def _build_shape_index_map(entries: list[FaceEntry] | list[EdgeEntry]) -> Any | None:
    """Build a TopTools_IndexedMapOfShape for O(1) lookups by IsSame semantics."""
    if TopTools_IndexedMapOfShape is None:
        return None
    shape_map = TopTools_IndexedMapOfShape()
    for entry in entries:
        shape_map.Add(entry.face if hasattr(entry, "face") else entry.edge)
    return shape_map


def _shape_map_find_index(shape: Any, shape_map: Any, entries: list) -> int | None:
    """O(1) lookup: find the entry index for a shape using the prebuilt map."""
    if shape_map is None:
        return _linear_find_index(shape, entries)
    try:
        idx = shape_map.FindIndex(shape)
        if idx > 0:
            return idx - 1  # OCC maps are 1-based, entries are 0-based
    except Exception:
        pass
    return None


def _linear_find_index(shape: Any, entries: list) -> int | None:
    """Fallback linear scan using IsSame()."""
    for entry in entries:
        try:
            s = entry.face if hasattr(entry, "face") else entry.edge
            if s.IsSame(shape):
                return entry.index
        except Exception:
            pass
    return None


def _attached_faces_by_edge_via_topology_explorer(
    edges: list[EdgeEntry], faces: list[FaceEntry], shape: Any, face_map: Any | None
) -> dict[int, list[int]]:
    """Fallback: use TopologyExplorer.faces_from_edge() when build_edge_face_map is unavailable."""
    explorer = _safe_topology_explorer(shape)
    if explorer is None:
        return {}

    attached: dict[int, list[int]] = {}
    for edge_entry in edges:
        face_indices: list[int] = []
        try:
            for face in explorer.faces_from_edge(edge_entry.edge):
                face_index = _shape_map_find_index(face, face_map, faces)
                if face_index is not None and face_index not in face_indices:
                    face_indices.append(face_index)
        except Exception:
            pass
        attached[edge_entry.hash_code] = face_indices
    return attached


def _attached_faces_by_edge(
    edges: list[EdgeEntry], faces: list[FaceEntry], shape: Any, face_map: Any | None = None
) -> dict[int, list[int]]:
    edge_face_map = build_edge_face_map(shape)
    if edge_face_map is None:
        return _attached_faces_by_edge_via_topology_explorer(edges, faces, shape, face_map)

    try:
        from OCC.Core.TopTools import TopTools_ListIteratorOfListOfShape
    except ImportError:  # pragma: no cover
        return _attached_faces_by_edge_via_topology_explorer(edges, faces, shape, face_map)

    attached: dict[int, list[int]] = {}

    for edge_entry in edges:
        face_indices: list[int] = []
        try:
            idx = edge_face_map.FindIndex(edge_entry.edge)
            if idx == 0:
                attached[edge_entry.hash_code] = []
                continue
            face_list = edge_face_map.FindFromIndex(idx)
            it = TopTools_ListIteratorOfListOfShape(face_list)
            while it.More():
                face = it.Value()
                face_index = _shape_map_find_index(face, face_map, faces)
                if face_index is not None and face_index not in face_indices:
                    face_indices.append(face_index)
                it.Next()
        except Exception:
            pass
        attached[edge_entry.hash_code] = face_indices
    return attached


def extract_brep_graph(shape: Any) -> GraphData:
    faces = _iter_faces(shape)
    edges = _iter_edges(shape)

    # Precompute O(1) shape index maps
    face_map = _build_shape_index_map(faces)
    edge_map = _build_shape_index_map(edges)

    raw_counts = count_topology(shape)
    graph = GraphData(metadata=raw_counts)
    graph.metadata["oriented_edge_count"] = raw_counts["edge_count"]
    graph.metadata["edge_count"] = len(edges)
    graph.metadata["surface_type_labels"] = SURFACE_TYPE_ONE_HOT

    face_normals: dict[int, tuple[float, float, float]] = {}
    face_error_count = 0
    for entry in faces:
        try:
            surface_type = _surface_type_name(entry.face)
            area = _face_area(entry.face)
            centroid = _face_centroid(entry.face)
            uv = uv_bounds(entry.face)
            normal = _face_normal(entry.face)
        except Exception:
            face_error_count += 1
            surface_type = "unknown"
            area = 0.0
            centroid = (0.0, 0.0, 0.0)
            uv = (0.0, 0.0, 0.0, 0.0)
            normal = (0.0, 0.0, 0.0)
        face_normals[entry.index] = normal
        graph.node_features.append(
            {
                "face_index": entry.index,
                "surface_type": surface_type,
                "surface_type_one_hot": _surface_type_vector(surface_type),
                "area": area,
                "centroid": centroid,
                "normal": normal,
                "mean_curvature": 0.0,
                "uv_bounds": uv,
            }
        )

    attached_faces_by_edge_hash = _attached_faces_by_edge(edges, faces, shape, face_map)
    adjacency_set: set[tuple[int, int]] = set()

    edge_error_count = 0
    for edge_entry in edges:
        attached = attached_faces_by_edge_hash.get(edge_entry.hash_code, [])
        convexity = "unknown"
        dihedral_angle = None
        dihedral_signal = None
        try:
            length = edge_length(edge_entry.edge)
            curvature = _edge_midpoint_curvature(edge_entry.edge)
        except Exception:
            edge_error_count += 1
            length = 0.0
            curvature = 0.0
        if len(attached) >= 2:
            face_a, face_b = attached[0], attached[1]
            convexity, dihedral_angle, dihedral_signal = _convexity_from_normals(
                face_normals.get(face_a, (0.0, 0.0, 0.0)),
                face_normals.get(face_b, (0.0, 0.0, 0.0)),
            )
            adjacency_set.add(tuple(sorted((face_a, face_b))))
        graph.edge_features.append(
            {
                "edge_index": edge_entry.index,
                "length": length,
                "midpoint_curvature": curvature,
                "connected_faces": attached,
                "convexity": convexity,
                "dihedral_angle": dihedral_angle,
                "dihedral_signal": dihedral_signal,
            }
        )

    graph.adjacency = sorted(adjacency_set)

    coedge_index = 0
    if TopExp_Explorer is not None and TopAbs_FACE is not None and TopAbs_WIRE is not None and WireExplorer is not None:
        for face_entry in faces:
            face = face_entry.face
            graph.face_to_coedges.setdefault(face_entry.index, [])
            try:
                wire_explorer = TopExp_Explorer(face, TopAbs_WIRE)
            except Exception:
                continue
            while wire_explorer.More():
                wire = topods.Wire(wire_explorer.Current()) if topods is not None else wire_explorer.Current()
                try:
                    ordered_edges = list(WireExplorer(wire).ordered_edges())
                except Exception:
                    ordered_edges = []
                for position, oriented_edge in enumerate(ordered_edges):
                    edge_index = _shape_map_find_index(oriented_edge, edge_map, edges)
                    if edge_index is None:
                        continue
                    graph.coedge_features.append(
                        {
                            "coedge_index": coedge_index,
                            "face_index": face_entry.index,
                            "edge_index": edge_index,
                            "orientation": _coedge_orientation_value(oriented_edge),
                            "loop_position": position,
                        }
                    )
                    graph.face_to_coedges[face_entry.index].append(coedge_index)
                    graph.edge_to_coedges.setdefault(edge_index, []).append(coedge_index)
                    graph.coedge_to_face[coedge_index] = face_entry.index
                    graph.coedge_to_edge[coedge_index] = edge_index
                    coedge_index += 1
                wire_explorer.Next()

    for edge_index, coedges in graph.edge_to_coedges.items():
        if len(coedges) == 2:
            graph.coedge_to_mate[coedges[0]] = coedges[1]
            graph.coedge_to_mate[coedges[1]] = coedges[0]

    graph.metadata.update(
        {
            "extractor": "custom-brepnet-phase2",
            "face_feature_count": len(graph.node_features),
            "edge_feature_count": len(graph.edge_features),
            "coedge_count": len(graph.coedge_features),
            "adjacency_count": len(graph.adjacency),
            "face_feature_errors": face_error_count,
            "edge_feature_errors": edge_error_count,
        }
    )
    return graph
