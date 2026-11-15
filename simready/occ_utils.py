"""Shared OCC traversal and geometry helpers."""

from __future__ import annotations

from typing import Any

from simready.occ_compat import (
    Bnd_Box, BRepAdaptor_Curve, brepbndlib, breptools,
    GCPnts_AbscissaPoint, TopAbs_EDGE, TopAbs_FACE, TopAbs_SOLID,
    TopExp_Explorer, topexp, topods, TopTools_IndexedDataMapOfShapeListOfShape,
    OCC_AVAILABLE,
)


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
    lo, hi = box.CornerMin(), box.CornerMax()
    xmin, ymin, zmin = lo.X(), lo.Y(), lo.Z()
    xmax, ymax, zmax = hi.X(), hi.Y(), hi.Z()
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


def uv_bounds(face: Any) -> tuple[float, float, float, float]:
    """Return (umin, umax, vmin, vmax) for a face, with pythonocc version compat."""
    # Try new API first (pythonocc 7.9+)
    try:
        return tuple(float(v) for v in breptools.UVBounds(face))
    except Exception:
        pass
    # Fall back to deprecated free function
    try:
        from simready.occ_compat import breptools_UVBounds
        return tuple(float(v) for v in breptools_UVBounds(face))
    except Exception:
        pass
    return (0.0, 0.0, 0.0, 0.0)


def count_topology(shape: Any) -> dict[str, int]:
    return {
        "face_count": count_shapes(shape, TopAbs_FACE),
        "edge_count": count_shapes(shape, TopAbs_EDGE),
        "solid_count": count_shapes(shape, TopAbs_SOLID),
    }


def iter_faces(shape: Any) -> list[tuple[int, Any]]:
    """Canonical 0-based face iterator. Shared across checks and ML modules."""
    if TopExp_Explorer is None or TopAbs_FACE is None:
        return []
    try:
        explorer = TopExp_Explorer(shape, TopAbs_FACE)
    except Exception:
        return []
    faces: list[tuple[int, Any]] = []
    index = 0
    while explorer.More():
        current = explorer.Current()
        face = topods.Face(current) if topods is not None else current
        faces.append((index, face))
        index += 1
        explorer.Next()
    return faces
