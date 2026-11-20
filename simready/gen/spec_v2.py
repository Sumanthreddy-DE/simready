"""Pydantic schema for DSL v2 (SP2, design E2).

v1 (``simready.gen.spec``) is frozen; every v1 spec validates here and builds
the same shape. New: an ``axis`` on ``cyl``; ``cone``, ``sphere``, ``prism``,
``regular_prism``; patterns ``polar`` / ``grid``; ``fillet`` / ``chamfer`` with
CadQuery-style edge selectors. Same 16-step cap and orphan rule as v1;
patterns count as references to the step they copy.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt, model_validator

from simready.gen.spec import (
    DIM_MAX,
    PLACEMENT_MAX,
    PLACEMENT_MIN,
    RADIUS_MAX,
    STEPS_MAX,
    STEPS_MIN,
    BoxOp,
    CutOp,
    FuseOp,
    Placement,
    PositiveDim,
    PositiveRadius,
)

Axis = Literal["x", "y", "z"]
EDGE_SELECTORS = frozenset({"all"} | {f"{s}{a}" for s in "><|" for a in "xyz"})
EdgeSelector = Literal["all", ">x", "<x", "|x", ">y", "<y", "|y", ">z", "<z", "|z"]
NonNegRadius = Annotated[float, Field(ge=0, le=RADIUS_MAX)]
Point2 = tuple[
    Annotated[float, Field(ge=PLACEMENT_MIN, le=PLACEMENT_MAX)],
    Annotated[float, Field(ge=PLACEMENT_MIN, le=PLACEMENT_MAX)],
]
Offset = Annotated[float, Field(ge=-DIM_MAX, le=DIM_MAX)]


class _Op(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CylOpV2(_Op):
    """Cylinder from ``at`` along +``axis``."""

    op: Literal["cyl"]
    r: PositiveRadius
    h: PositiveDim
    at: Placement = (0.0, 0.0, 0.0)
    axis: Axis = "z"


class ConeOp(_Op):
    """Cone or frustum: radius ``r1`` at ``at``, ``r2`` at ``at + h * axis``."""

    op: Literal["cone"]
    r1: NonNegRadius
    r2: NonNegRadius
    h: PositiveDim
    at: Placement = (0.0, 0.0, 0.0)
    axis: Axis = "z"

    @model_validator(mode="after")
    def _radii(self) -> "ConeOp":
        if self.r1 == 0 and self.r2 == 0:
            raise ValueError("cone needs r1 > 0 or r2 > 0")
        if self.r1 == self.r2:
            raise ValueError("cone with r1 == r2 is a cylinder; use cyl")
        return self


class SphereOp(_Op):
    op: Literal["sphere"]
    r: PositiveRadius
    at: Placement = (0.0, 0.0, 0.0)


class PrismOp(_Op):
    """Closed polygon of [u, v] points (plane: z->(x,y), x->(y,z), y->(x,z)) extruded h along +axis."""

    op: Literal["prism"]
    points: list[Point2] = Field(min_length=3, max_length=12)
    h: PositiveDim
    at: Placement = (0.0, 0.0, 0.0)
    axis: Axis = "z"


class RegularPrismOp(_Op):
    """Regular polygon centred on ``at``, one flat parallel to u, extruded h along +axis."""

    op: Literal["regular_prism"]
    sides: int = Field(ge=3, le=12)
    across_flats: PositiveDim
    h: PositiveDim
    at: Placement = (0.0, 0.0, 0.0)
    axis: Axis = "z"


class PolarOp(_Op):
    """Union of ``count`` copies of step ``of`` rotated 360/count deg about the axis through ``center``."""

    op: Literal["polar"]
    of: NonNegativeInt
    count: int = Field(ge=2, le=64)
    center: Placement
    axis: Axis = "z"


class GridOp(_Op):
    """Union of nx * ny copies of step ``of`` translated i*dx along X and j*dy along Y."""

    op: Literal["grid"]
    of: NonNegativeInt
    nx: int = Field(ge=1, le=16)
    ny: int = Field(ge=1, le=16)
    dx: Offset
    dy: Offset

    @model_validator(mode="after")
    def _at_least_two(self) -> "GridOp":
        if self.nx * self.ny < 2:
            raise ValueError("grid needs nx * ny >= 2")
        return self


class FilletOp(_Op):
    op: Literal["fillet"]
    a: NonNegativeInt
    r: PositiveDim
    edges: EdgeSelector


class ChamferOp(_Op):
    op: Literal["chamfer"]
    a: NonNegativeInt
    d: PositiveDim
    edges: EdgeSelector


OpV2 = Annotated[
    Union[BoxOp, CylOpV2, ConeOp, SphereOp, PrismOp, RegularPrismOp, PolarOp, GridOp,
          FilletOp, ChamferOp, FuseOp, CutOp],
    Field(discriminator="op"),
]
KNOWN_OPS_V2 = frozenset({"box", "cyl", "cone", "sphere", "prism", "regular_prism",
                          "polar", "grid", "fillet", "chamfer", "fuse", "cut"})


def refs(step: BaseModel) -> tuple[int, ...]:
    """Step indices this step consumes."""
    if isinstance(step, (FuseOp, CutOp)):
        return (step.a, step.b)
    if isinstance(step, (PolarOp, GridOp)):
        return (step.of,)
    if isinstance(step, (FilletOp, ChamferOp)):
        return (step.a,)
    return ()


class PartSpecV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    steps: list[OpV2] = Field(min_length=STEPS_MIN, max_length=STEPS_MAX)

    @model_validator(mode="after")
    def _check_refs(self) -> "PartSpecV2":
        for i, step in enumerate(self.steps):
            r = refs(step)
            for ref in r:
                if ref >= i:
                    raise ValueError(f"steps[{i}] refers to step {ref}; it must refer to a prior step (< {i})")
            if len(r) == 2 and r[0] == r[1]:
                raise ValueError(f"steps[{i}] cannot reference the same step on both sides ({r[0]})")
        return self

    @model_validator(mode="after")
    def _check_orphans(self) -> "PartSpecV2":
        referenced = {ref for step in self.steps for ref in refs(step)}
        for i, step in enumerate(self.steps[:-1]):
            if i not in referenced:
                raise ValueError(
                    f"steps[{i}] ({step.op}) is never referenced by a later step; only the final step "
                    f"is returned as the part, so this step would be discarded"
                )
        return self


BUILD_PART_TOOL_SCHEMA_V2: dict = {
    "type": "function",
    "function": {
        "name": "build_part",
        "description": (
            "Generate a new STEP file from a typed parametric spec. The spec is a list of ops: "
            "box(dx, dy, dz, at) [at = min corner]; "
            "cyl(r, h, at, axis) [base centre at 'at', extends h along +axis; axis 'x'|'y'|'z', default 'z']; "
            "cone(r1, r2, h, at, axis) [radius r1 at 'at', r2 at the far end; one radius may be 0, not both, r1 != r2]; "
            "sphere(r, at) [at = centre]; "
            "prism(points, h, at, axis) [3-12 [u, v] points of a closed polygon, offset by 'at', extruded h along +axis; "
            "(u, v) is (x, y) for axis 'z', (y, z) for 'x', (x, z) for 'y']; "
            "regular_prism(sides, across_flats, h, at, axis) [3-12 sides, centred on 'at', one flat parallel to u]; "
            "polar(of, count, center, axis) [union of count copies of step 'of' rotated evenly about the axis through center]; "
            "grid(of, nx, ny, dx, dy) [union of nx*ny copies of step 'of' moved i*dx along X and j*dy along Y]; "
            "fillet(a, r, edges) and chamfer(a, d, edges) [round or bevel edges of step 'a'; edges is 'all', "
            "'>z' (edges at the highest z), '<z' (lowest z), '|z' (straight edges parallel to z), same for x and y]; "
            "fuse(a, b); cut(a, b) [subtract b from a]. "
            "'a', 'b' and 'of' are 0-based indices of earlier steps. The last step is the part returned; "
            "every other step MUST be used by a later step. "
            f"A spec has at most {STEPS_MAX} steps. Limits in mm: lengths in (0, {DIM_MAX:g}], radii in (0, {RADIUS_MAX:g}] "
            f"(cone radii may be 0), coordinates in [{PLACEMENT_MIN:g}, {PLACEMENT_MAX:g}]."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "spec": {
                    "type": "object",
                    "description": (
                        "Shape: {\"steps\": [{\"op\": ..., ...}, ...]}. Example, plate with 4 corner holes: "
                        "{\"steps\": [{\"op\":\"box\",\"dx\":80,\"dy\":60,\"dz\":5},"
                        "{\"op\":\"cyl\",\"r\":2,\"h\":5,\"at\":[10,10,0]},"
                        "{\"op\":\"grid\",\"of\":1,\"nx\":2,\"ny\":2,\"dx\":60,\"dy\":40},"
                        "{\"op\":\"cut\",\"a\":0,\"b\":2}]}."
                    ),
                },
            },
            "required": ["spec"],
        },
    },
}
