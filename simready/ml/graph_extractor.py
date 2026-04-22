"""B-Rep graph extraction scaffolding for Phase 2 ML integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

try:
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
except ImportError:  # pragma: no cover
    BRepAdaptor_Surface = None

from simready.checks import FaceRecord
from simready.occ_utils import build_edge_face_map, count_topology, edge_length

try:
    from OCC.Core.TopAbs import GeomAbs_BSplineSurface, GeomAbs_Cone, GeomAbs_Cylinder, GeomAbs_Plane, GeomAbs_Sphere, GeomAbs_Torus
except ImportError:  # pragma: no cover
    GeomAbs_BSplineSurface = GeomAbs_Cone = GeomAbs_Cylinder = GeomAbs_Plane = GeomAbs_Sphere = GeomAbs_Torus = None

try:
    from OCC.Core.TopAbs import TopAbs_FACE
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopoDS import topods
except ImportError:  # pragma: no cover
    TopAbs_FACE = None
    TopExp_Explorer = None
    topods = None


SURFACE_TYPE_MAP = {
    GeomAbs_Plane: "plane",
    GeomAbs_Cylinder: "cylinder",
    GeomAbs_Cone: "cone",
    GeomAbs_Sphere: "sphere",
    GeomAbs_Torus: "torus",
    GeomAbs_BSplineSurface: "bspline",
}


@dataclass
class GraphData:
    node_features: list[dict[str, Any]] = field(default_factory=list)
    edge_features: list[dict[str, Any]] = field(default_factory=list)
    adjacency: list[tuple[int, int]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def _iter_faces(shape: Any) -> list[FaceRecord]:
    if TopExp_Explorer is None or TopAbs_FACE is None:
        return []
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    faces: list[FaceRecord] = []
    index = 1
    while explorer.More():
        face = topods.Face(explorer.Current()) if topods is not None else explorer.Current()
        faces.append(FaceRecord(index=index, face=face))
        index += 1
        explorer.Next()
    return faces


def _surface_type_name(face: Any) -> str:
    if BRepAdaptor_Surface is None:
        return "unknown"
    try:
        surface = BRepAdaptor_Surface(face, True)
        return SURFACE_TYPE_MAP.get(surface.GetType(), "other")
    except Exception:
        return "unknown"


def extract_brep_graph(shape: Any) -> GraphData:
    faces = _iter_faces(shape)
    graph = GraphData(metadata=count_topology(shape))

    for record in faces:
        graph.node_features.append(
            {
                "face_index": record.index,
                "surface_type": _surface_type_name(record.face),
            }
        )

    edge_face_map = build_edge_face_map(shape)
    if edge_face_map is None:
        graph.metadata["extractor"] = "fallback-no-occ-map"
        return graph

    for edge_index in range(1, edge_face_map.Size() + 1):
        attached = edge_face_map.FindFromIndex(edge_index)
        attached_indices: list[int] = []
        for pos in range(1, attached.Size() + 1):
            attached_indices.append(pos)
        if len(attached_indices) >= 2:
            a, b = attached_indices[:2]
            graph.adjacency.append((a, b))
            graph.edge_features.append(
                {
                    "edge_index": edge_index,
                    "length": edge_length(edge_face_map.FindKey(edge_index)),
                    "connected_faces": [a, b],
                    "convexity": "unknown",
                    "dihedral_angle": None,
                }
            )

    graph.metadata["extractor"] = "custom-phase2-scaffold"
    return graph
