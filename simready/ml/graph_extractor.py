"""B-Rep graph extraction for Phase 2 ML integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import sqrt
from typing import Any

try:
    from OCC.Core.BRep import BRep_Tool
except ImportError:  # pragma: no cover
    BRep_Tool = None

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
    from OCC.Core.BRepTools import breptools_UVBounds
except ImportError:  # pragma: no cover
    breptools_UVBounds = None

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

from simready.occ_utils import build_edge_face_map, count_topology, edge_length


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
    if TopExp_Explorer is None or TopAbs_EDGE is None:
        return []
    try:
        explorer = TopExp_Explorer(shape, TopAbs_EDGE)
    except Exception:
        return []

    edges: list[EdgeEntry] = []
    index = 0
    while explorer.More():
        edge = topods.Edge(explorer.Current()) if topods is not None else explorer.Current()
        edges.append(EdgeEntry(index=index, edge=edge, hash_code=_shape_hash(edge) or index))
        index += 1
        explorer.Next()
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
    return [1.0 if key == name else 0.0 for key in SURFACE_TYPE_ONE_HOT]


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


def _uv_bounds(face: Any) -> tuple[float, float, float, float]:
    if breptools_UVBounds is None:
        return (0.0, 0.0, 0.0, 0.0)
    try:
        return tuple(float(v) for v in breptools_UVBounds(face))
    except Exception:
        return (0.0, 0.0, 0.0, 0.0)


def _face_normal(face: Any) -> tuple[float, float, float]:
    if BRepAdaptor_Surface is None or GeomLProp_SLProps is None:
        return (0.0, 0.0, 0.0)
    try:
        surface = BRepAdaptor_Surface(face, True)
        umin, umax, vmin, vmax = _uv_bounds(face)
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


def _convexity_from_normals(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[str, float | None]:
    norm_a = _vector_norm(a)
    norm_b = _vector_norm(b)
    if norm_a == 0.0 or norm_b == 0.0:
        return ("unknown", None)
    cos_theta = max(-1.0, min(1.0, _vector_dot(a, b) / (norm_a * norm_b)))
    if cos_theta > 0.98:
        return ("smooth", 0.0)
    if cos_theta >= 0.0:
        return ("convex", cos_theta)
    return ("concave", cos_theta)


def extract_brep_graph(shape: Any) -> GraphData:
    faces = _iter_faces(shape)
    edges = _iter_edges(shape)
    face_hash_to_index = {entry.hash_code: entry.index for entry in faces}
    edge_hash_to_index = {entry.hash_code: entry.index for entry in edges}

    graph = GraphData(metadata=count_topology(shape))
    graph.metadata["surface_type_labels"] = SURFACE_TYPE_ONE_HOT

    face_normals: dict[int, tuple[float, float, float]] = {}
    for entry in faces:
        surface_type = _surface_type_name(entry.face)
        area = _face_area(entry.face)
        centroid = _face_centroid(entry.face)
        uv = _uv_bounds(entry.face)
        normal = _face_normal(entry.face)
        face_normals[entry.index] = normal
        graph.node_features.append(
            {
                "face_index": entry.index,
                "surface_type": surface_type,
                "surface_type_one_hot": _surface_type_vector(surface_type),
                "area": area,
                "centroid": centroid,
                "normal": normal,
                "uv_bounds": uv,
            }
        )

    edge_face_map = build_edge_face_map(shape)
    attached_faces_by_edge_hash: dict[int, list[int]] = {}
    if TopologyExplorer is not None:
        try:
            top_exp = TopologyExplorer(shape, ignore_orientation=True)
            for edge_entry in edges:
                attached_indices: list[int] = []
                for face in top_exp.faces_from_edge(edge_entry.edge):
                    face_index = face_hash_to_index.get(_shape_hash(face))
                    if face_index is not None:
                        attached_indices.append(face_index)
                attached_faces_by_edge_hash[edge_entry.hash_code] = attached_indices
        except Exception:
            attached_faces_by_edge_hash = {}
    elif edge_face_map is not None:
        for map_index in range(1, edge_face_map.Size() + 1):
            edge = edge_face_map.FindKey(map_index)
            edge_hash = _shape_hash(edge)
            if edge_hash is not None and edge_hash not in attached_faces_by_edge_hash:
                attached_faces_by_edge_hash[edge_hash] = []

    for edge_entry in edges:
        attached = attached_faces_by_edge_hash.get(edge_entry.hash_code, [])
        convexity = "unknown"
        dihedral_signal = None
        if len(attached) >= 2:
            convexity, dihedral_signal = _convexity_from_normals(face_normals.get(attached[0], (0.0, 0.0, 0.0)), face_normals.get(attached[1], (0.0, 0.0, 0.0)))
            graph.adjacency.append((attached[0], attached[1]))
        graph.edge_features.append(
            {
                "edge_index": edge_entry.index,
                "length": edge_length(edge_entry.edge),
                "midpoint_curvature": _edge_midpoint_curvature(edge_entry.edge),
                "connected_faces": attached,
                "convexity": convexity,
                "dihedral_angle": dihedral_signal,
            }
        )

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
                    edge_index = edge_hash_to_index.get(_shape_hash(oriented_edge))
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
        }
    )
    return graph
