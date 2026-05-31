"""Pydantic-level schema contracts for the geometry-gen DSL.

These tests do not exercise OCC — they are pure validation tests, so they run
in both the base and sr envs.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from simready.gen.spec import (
    DIM_MAX,
    RADIUS_MAX,
    STEPS_MAX,
    BoxOp,
    CutOp,
    CylOp,
    FuseOp,
    PartSpec,
)


# ----------------------------------------------------------------------------
# Happy paths
# ----------------------------------------------------------------------------


def test_minimal_box_only_spec_accepts():
    spec = PartSpec.model_validate({"steps": [{"op": "box", "dx": 10, "dy": 20, "dz": 30}]})
    assert len(spec.steps) == 1
    assert isinstance(spec.steps[0], BoxOp)
    assert spec.steps[0].at == (0.0, 0.0, 0.0)


def test_box_with_placement_accepts():
    spec = PartSpec.model_validate(
        {"steps": [{"op": "box", "dx": 10, "dy": 20, "dz": 30, "at": [1.0, 2.0, 3.0]}]}
    )
    assert spec.steps[0].at == (1.0, 2.0, 3.0)


def test_cyl_op_accepts():
    spec = PartSpec.model_validate({"steps": [{"op": "cyl", "r": 5, "h": 10}]})
    assert isinstance(spec.steps[0], CylOp)


def test_l_bracket_fuse_spec_accepts():
    spec = PartSpec.model_validate(
        {
            "steps": [
                {"op": "box", "dx": 60, "dy": 60, "dz": 10},
                {"op": "box", "dx": 60, "dy": 10, "dz": 50, "at": [0, 0, 10]},
                {"op": "fuse", "a": 0, "b": 1},
            ]
        }
    )
    assert len(spec.steps) == 3
    assert isinstance(spec.steps[2], FuseOp)


def test_bracket_with_hole_cut_spec_accepts():
    spec = PartSpec.model_validate(
        {
            "steps": [
                {"op": "box", "dx": 80, "dy": 60, "dz": 10},
                {"op": "cyl", "r": 5, "h": 10, "at": [40, 30, 0]},
                {"op": "cut", "a": 0, "b": 1},
            ]
        }
    )
    assert isinstance(spec.steps[2], CutOp)


# ----------------------------------------------------------------------------
# Schema-level rejections
# ----------------------------------------------------------------------------


def test_empty_steps_rejects():
    with pytest.raises(ValidationError):
        PartSpec.model_validate({"steps": []})


def test_too_many_steps_rejects():
    with pytest.raises(ValidationError):
        PartSpec.model_validate(
            {"steps": [{"op": "box", "dx": 1, "dy": 1, "dz": 1}] * (STEPS_MAX + 1)}
        )


def test_unknown_op_rejects():
    with pytest.raises(ValidationError):
        PartSpec.model_validate({"steps": [{"op": "sphere", "r": 5}]})


def test_extra_field_on_op_rejects():
    with pytest.raises(ValidationError):
        PartSpec.model_validate(
            {"steps": [{"op": "box", "dx": 1, "dy": 1, "dz": 1, "rgb": "red"}]}
        )


def test_extra_field_on_spec_rejects():
    with pytest.raises(ValidationError):
        PartSpec.model_validate(
            {"steps": [{"op": "box", "dx": 1, "dy": 1, "dz": 1}], "rotation": 45}
        )


def test_zero_dim_rejects():
    with pytest.raises(ValidationError):
        PartSpec.model_validate({"steps": [{"op": "box", "dx": 0, "dy": 1, "dz": 1}]})


def test_negative_dim_rejects():
    with pytest.raises(ValidationError):
        PartSpec.model_validate({"steps": [{"op": "cyl", "r": -1, "h": 10}]})


def test_dim_above_cap_rejects():
    with pytest.raises(ValidationError):
        PartSpec.model_validate(
            {"steps": [{"op": "box", "dx": DIM_MAX + 1, "dy": 1, "dz": 1}]}
        )


def test_radius_above_cap_rejects():
    with pytest.raises(ValidationError):
        PartSpec.model_validate({"steps": [{"op": "cyl", "r": RADIUS_MAX + 1, "h": 10}]})


# ----------------------------------------------------------------------------
# Cross-step (model-level) rejections
# ----------------------------------------------------------------------------


def test_fuse_ref_to_self_rejects():
    with pytest.raises(ValidationError):
        PartSpec.model_validate(
            {
                "steps": [
                    {"op": "box", "dx": 1, "dy": 1, "dz": 1},
                    {"op": "fuse", "a": 1, "b": 0},  # a refs own index
                ]
            }
        )


def test_fuse_ref_to_future_rejects():
    with pytest.raises(ValidationError):
        PartSpec.model_validate(
            {
                "steps": [
                    {"op": "box", "dx": 1, "dy": 1, "dz": 1},
                    {"op": "fuse", "a": 0, "b": 2},  # b not yet defined
                    {"op": "box", "dx": 1, "dy": 1, "dz": 1},
                ]
            }
        )


def test_cut_ref_same_step_rejects():
    with pytest.raises(ValidationError):
        PartSpec.model_validate(
            {
                "steps": [
                    {"op": "box", "dx": 1, "dy": 1, "dz": 1},
                    {"op": "cut", "a": 0, "b": 0},
                ]
            }
        )
