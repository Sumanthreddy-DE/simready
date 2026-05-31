"""Pydantic schema for the geometry-gen-mvp DSL.

The grammar matches ``scripts/generate_parametric_steps.py`` exactly:

- ``box(dx, dy, dz, at)``        — 3 positive mm dims + 3-tuple origin (mm)
- ``cyl(r, h, at)``              — radius + height (mm), axis fixed to +Z
- ``fuse(a, b)`` / ``cut(a, b)`` — boolean ops; ``a``/``b`` are integer
  step indices that must be strictly less than the op's own position

A ``PartSpec`` is a non-empty, capped list of ``Op`` (1..16 steps). Bounds
on dims keep the LLM's output inside the parametric distribution the
BRepSAGE checkpoint was trained on (20–100 mm typical, allowing 0–1000 mm
for valid edge cases).

The last step in ``steps`` is the part returned by ``build_shape``.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeInt,
    model_validator,
)

# Mm bounds. Picked to be looser than `generate_parametric_steps.py`'s
# 20–100 mm range so the LLM has headroom, but tight enough that one bad
# token can't produce a 1 km box that crashes downstream tools.
DIM_MIN = 0.01
DIM_MAX = 1000.0
RADIUS_MAX = 500.0
PLACEMENT_MIN = -10_000.0
PLACEMENT_MAX = 10_000.0
STEPS_MIN = 1
STEPS_MAX = 16


PositiveDim = Annotated[float, Field(gt=0, le=DIM_MAX, description="Millimetres; (0, 1000].")]
PositiveRadius = Annotated[float, Field(gt=0, le=RADIUS_MAX, description="Millimetres; (0, 500].")]
Coord = Annotated[float, Field(ge=PLACEMENT_MIN, le=PLACEMENT_MAX, description="Millimetres; [-10000, 10000].")]
Placement = tuple[Coord, Coord, Coord]


class _OpBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BoxOp(_OpBase):
    """Axis-aligned box, ``at`` is the min-corner (mm)."""

    op: Literal["box"]
    dx: PositiveDim
    dy: PositiveDim
    dz: PositiveDim
    at: Placement = (0.0, 0.0, 0.0)


class CylOp(_OpBase):
    """Cylinder along +Z, ``at`` is the base centre (mm)."""

    op: Literal["cyl"]
    r: PositiveRadius
    h: PositiveDim
    at: Placement = (0.0, 0.0, 0.0)


class FuseOp(_OpBase):
    """Boolean fuse of two prior steps. ``a``/``b`` are 0-based step indices."""

    op: Literal["fuse"]
    a: NonNegativeInt
    b: NonNegativeInt


class CutOp(_OpBase):
    """Boolean cut: subtract step ``b`` from step ``a``. Indices are 0-based."""

    op: Literal["cut"]
    a: NonNegativeInt
    b: NonNegativeInt


Op = Annotated[
    Union[BoxOp, CylOp, FuseOp, CutOp],
    Field(discriminator="op"),
]


class PartSpec(BaseModel):
    """Top-level spec the LLM emits via the ``build_part`` tool."""

    model_config = ConfigDict(extra="forbid")

    steps: list[Op] = Field(min_length=STEPS_MIN, max_length=STEPS_MAX)

    @model_validator(mode="after")
    def _check_refs(self) -> "PartSpec":
        """Every fuse/cut ref must be a prior step index (a, b < own index, and a != b)."""
        for i, step in enumerate(self.steps):
            if isinstance(step, (FuseOp, CutOp)):
                if step.a >= i:
                    raise ValueError(
                        f"steps[{i}].a={step.a} must refer to a prior step (< {i})"
                    )
                if step.b >= i:
                    raise ValueError(
                        f"steps[{i}].b={step.b} must refer to a prior step (< {i})"
                    )
                if step.a == step.b:
                    raise ValueError(
                        f"steps[{i}] cannot reference the same step on both sides ({step.a})"
                    )
        return self
