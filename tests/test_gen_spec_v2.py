"""DSL v2 schema contracts. Pure Pydantic, no OCC."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from simready.bench.concepts import CONCEPTS_V1, load_concepts
from simready.gen.spec_v2 import (
    BUILD_PART_TOOL_SCHEMA_V2,
    EDGE_SELECTORS,
    KNOWN_OPS_V2,
    CylOpV2,
    PartSpecV2,
)


def v2(*steps):
    return PartSpecV2.model_validate({"steps": list(steps)})


def test_every_v1_reference_spec_is_a_valid_v2_spec():
    for c in load_concepts(CONCEPTS_V1):
        if c.in_vocab:
            v2(*c.reference_spec["steps"])


def test_cyl_axis_defaults_to_z():
    step = v2({"op": "cyl", "r": 5, "h": 10}).steps[0]
    assert isinstance(step, CylOpV2) and step.axis == "z"


def test_cone_rejects_equal_or_double_zero_radii():
    v2({"op": "cone", "r1": 4, "r2": 0, "h": 3})
    with pytest.raises(ValidationError):
        v2({"op": "cone", "r1": 0, "r2": 0, "h": 3})
    with pytest.raises(ValidationError):
        v2({"op": "cone", "r1": 4, "r2": 4, "h": 3})


def test_prism_needs_3_to_12_points():
    v2({"op": "prism", "points": [[0, 0], [30, 0], [0, 30]], "h": 5})
    with pytest.raises(ValidationError):
        v2({"op": "prism", "points": [[0, 0], [1, 0]], "h": 5})
    with pytest.raises(ValidationError):
        v2({"op": "prism", "points": [[i, i * i] for i in range(13)], "h": 5})


def test_regular_prism_sides_bounds():
    v2({"op": "regular_prism", "sides": 6, "across_flats": 8, "h": 3})
    with pytest.raises(ValidationError):
        v2({"op": "regular_prism", "sides": 2, "across_flats": 8, "h": 3})


def test_polar_and_grid_reference_rules():
    v2({"op": "cyl", "r": 1, "h": 5}, {"op": "polar", "of": 0, "count": 8, "center": [0, 0, 0]})
    with pytest.raises(ValidationError, match="prior step"):
        v2({"op": "cyl", "r": 1, "h": 5}, {"op": "polar", "of": 1, "count": 8, "center": [0, 0, 0]})
    with pytest.raises(ValidationError):
        v2({"op": "cyl", "r": 1, "h": 5}, {"op": "grid", "of": 0, "nx": 1, "ny": 1, "dx": 5, "dy": 5})


def test_pattern_counts_as_reference_for_orphan_rule():
    v2(
        {"op": "box", "dx": 80, "dy": 60, "dz": 5},
        {"op": "cyl", "r": 1, "h": 5, "at": [10, 10, 0]},
        {"op": "grid", "of": 1, "nx": 2, "ny": 2, "dx": 60, "dy": 40},
        {"op": "cut", "a": 0, "b": 2},
    )
    with pytest.raises(ValidationError, match="never referenced"):
        v2({"op": "box", "dx": 8, "dy": 6, "dz": 5}, {"op": "sphere", "r": 3})


def test_fillet_selector_vocabulary():
    assert EDGE_SELECTORS == frozenset({"all", ">x", "<x", "|x", ">y", "<y", "|y", ">z", "<z", "|z"})
    v2({"op": "box", "dx": 8, "dy": 6, "dz": 5}, {"op": "fillet", "a": 0, "r": 1, "edges": ">z"})
    with pytest.raises(ValidationError):
        v2({"op": "box", "dx": 8, "dy": 6, "dz": 5}, {"op": "fillet", "a": 0, "r": 1, "edges": "top"})


def test_step_cap_is_still_16():
    with pytest.raises(ValidationError, match="at most 16"):
        v2(*[{"op": "box", "dx": 1, "dy": 1, "dz": 1}] * 17)


def test_known_ops_and_tool_schema_mention_every_op():
    assert KNOWN_OPS_V2 == frozenset({"box", "cyl", "cone", "sphere", "prism", "regular_prism",
                                      "polar", "grid", "fillet", "chamfer", "fuse", "cut"})
    desc = BUILD_PART_TOOL_SCHEMA_V2["function"]["description"]
    for op in KNOWN_OPS_V2:
        assert op in desc, op
