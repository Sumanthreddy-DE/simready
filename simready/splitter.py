"""Multi-body splitting helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    from OCC.Core.TopAbs import TopAbs_SOLID
    from OCC.Core.TopExp import TopExp_Explorer
except ImportError:  # pragma: no cover
    TopAbs_SOLID = None
    TopExp_Explorer = None


@dataclass
class SplitResult:
    body_count: int
    bodies: list[Any]


def split_bodies(shape: Any) -> SplitResult:
    if TopExp_Explorer is None or TopAbs_SOLID is None:
        return SplitResult(body_count=1, bodies=[shape])

    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    bodies: list[Any] = []
    while explorer.More():
        bodies.append(explorer.Current())
        explorer.Next()

    if not bodies:
        return SplitResult(body_count=1, bodies=[shape])

    return SplitResult(body_count=len(bodies), bodies=bodies)
