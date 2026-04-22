"""Shared OCC traversal and geometry helpers."""

from __future__ import annotations

from typing import Any

try:
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
    from OCC.Core.BRepBndLib import brepbndlib
    from OCC.Core.GCPnts import GCPnts_AbscissaPoint
    from OCC.Core.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_SOLID
    from OCC.Core.TopExp import TopExp_Explorer, topexp
    from OCC.Core.TopTools import TopTools_IndexedDataMapOfShapeListOfShape
except ImportError:  # pragma: no cover
    Bnd_Box = None
    BRepAdaptor_Curve = None
    brepbndlib = None
    GCPnts_AbscissaPoint = None
    TopAbs_EDGE = TopAbs_FACE = TopAbs_SOLID = None
    TopExp_Explorer = None
    topexp = None
    TopTools_IndexedDataMapOfShapeListOfShape = None


OCC_AVAILABLE = TopExp_Explorer is not None


def count_shapes(shape: Any, shape_type: Any) -> int:
    if TopExp_Explorer is None or shape_type is None:
        return 0
    explorer = TopExp_Explorer(shape, shape_type)
    count = 0
    while explorer.More():
        count += 1
        explorer.Next()
    return count


def shape_bounding_box(shape: Any) -> dict[str, float] | None:
    if Bnd_Box is None or brepbndlib is None:
        return None
    box = Bnd_Box()
    brepbndlib.Add(shape, box)
    xmin, ymin, zmin, xmax, ymax, zmax = box.Get()
    return {
        "xmin": xmin,
        "ymin": ymin,
        "zmin": zmin,
        "xmax": xmax,
        "ymax": ymax,
        "zmax": zmax,
    }


def edge_length(edge: Any) -> float:
    if BRepAdaptor_Curve is None:
        return 0.0
    try:
        curve = BRepAdaptor_Curve(edge)
        if GCPnts_AbscissaPoint is not None:
            return float(GCPnts_AbscissaPoint.Length(curve))
        return abs(curve.LastParameter() - curve.FirstParameter())
    except Exception:
        return 0.0


def build_edge_face_map(shape: Any):
    if topexp is None or TopTools_IndexedDataMapOfShapeListOfShape is None or TopAbs_EDGE is None or TopAbs_FACE is None:
        return None
    edge_face_map = TopTools_IndexedDataMapOfShapeListOfShape()
    try:
        topexp.MapShapesAndAncestors(shape, TopAbs_EDGE, TopAbs_FACE, edge_face_map)
    except Exception:
        return None
    return edge_face_map


def count_topology(shape: Any) -> dict[str, int]:
    return {
        "face_count": count_shapes(shape, TopAbs_FACE),
        "edge_count": count_shapes(shape, TopAbs_EDGE),
        "solid_count": count_shapes(shape, TopAbs_SOLID),
    }
