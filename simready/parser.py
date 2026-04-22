"""Basic geometry parsing for validated shapes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from simready.occ_utils import TopAbs_EDGE, TopAbs_FACE, TopAbs_SOLID, count_shapes, shape_bounding_box


@dataclass
class GeometrySummary:
    face_count: int
    edge_count: int
    solid_count: int
    bounding_box: dict[str, float] | None


def parse_geometry(shape: Any) -> GeometrySummary:
    return GeometrySummary(
        face_count=count_shapes(shape, TopAbs_FACE),
        edge_count=count_shapes(shape, TopAbs_EDGE),
        solid_count=count_shapes(shape, TopAbs_SOLID),
        bounding_box=shape_bounding_box(shape),
    )
