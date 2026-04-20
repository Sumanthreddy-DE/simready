"""Basic geometry parsing for validated shapes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib
    from OCC.Core.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_SOLID
    from OCC.Core.TopExp import TopExp_Explorer
except ImportError:  # pragma: no cover
    Bnd_Box = None
    brepbndlib = None
    TopAbs_EDGE = TopAbs_FACE = TopAbs_SOLID = None
    TopExp_Explorer = None


@dataclass
class GeometrySummary:
    face_count: int
    edge_count: int
    solid_count: int
    bounding_box: dict[str, float] | None


def _count_shapes(shape: Any, shape_type: Any) -> int:
    if TopExp_Explorer is None or shape_type is None:
        return 0
    explorer = TopExp_Explorer(shape, shape_type)
    count = 0
    while explorer.More():
        count += 1
        explorer.Next()
    return count


def _bounding_box(shape: Any) -> dict[str, float] | None:
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


def parse_geometry(shape: Any) -> GeometrySummary:
    return GeometrySummary(
        face_count=_count_shapes(shape, TopAbs_FACE),
        edge_count=_count_shapes(shape, TopAbs_EDGE),
        solid_count=_count_shapes(shape, TopAbs_SOLID),
        bounding_box=_bounding_box(shape),
    )
