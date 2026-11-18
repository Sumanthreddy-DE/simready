"""Checker: one known-pass and one known-fail per check type (spec done-criterion 2)."""

from __future__ import annotations

import pytest

from simready.occ_compat import OCC_AVAILABLE

if not OCC_AVAILABLE:
    pytest.skip("OCC bindings not available", allow_module_level=True)

from simready.bench.checker import grade_shape  # noqa: E402
from simready.bench.concepts import CHECK_LIST  # noqa: E402
from simready.gen.build import build_shape  # noqa: E402
from simready.gen.spec import PartSpec  # noqa: E402


def mk(steps):
    return build_shape(PartSpec.model_validate({"steps": steps}))


NEMA = mk([
    {"op": "box", "dx": 42, "dy": 42, "dz": 5},
    {"op": "cyl", "r": 11.25, "h": 5, "at": [21, 21, 0]},
    {"op": "cut", "a": 0, "b": 1},
    {"op": "cyl", "r": 1.7, "h": 5, "at": [5.5, 5.5, 0]},
    {"op": "cut", "a": 2, "b": 3},
    {"op": "cyl", "r": 1.7, "h": 5, "at": [36.5, 5.5, 0]},
    {"op": "cut", "a": 4, "b": 5},
    {"op": "cyl", "r": 1.7, "h": 5, "at": [5.5, 36.5, 0]},
    {"op": "cut", "a": 6, "b": 7},
    {"op": "cyl", "r": 1.7, "h": 5, "at": [36.5, 36.5, 0]},
    {"op": "cut", "a": 8, "b": 9},
])
FLANGE = mk([
    {"op": "cyl", "r": 10, "h": 5},
    {"op": "cyl", "r": 6, "h": 10, "at": [0, 0, 5]},
    {"op": "fuse", "a": 0, "b": 1},
    {"op": "cyl", "r": 3, "h": 15},
    {"op": "cut", "a": 2, "b": 3},
])
SQ = [[30.9, 31.1]] * 4 + [[43.74, 43.94]] * 2


def grade(shape, checks, solids=1):
    return grade_shape(shape, CHECK_LIST.validate_python(checks), solids)


@pytest.mark.parametrize(
    "shape,check,expected",
    [
        (NEMA, {"type": "bbox_sorted", "ranges": [[4.9, 5.1], [41.9, 42.1], [41.9, 42.1]]}, "pass"),
        (NEMA, {"type": "bbox_sorted", "ranges": [[5.9, 6.1], [41.9, 42.1], [41.9, 42.1]]}, "fail"),
        (NEMA, {"type": "bbox_min_dim", "min": 4.0}, "pass"),
        (NEMA, {"type": "bbox_min_dim", "min": 6.0}, "fail"),
        (NEMA, {"type": "volume", "range": [6500, 6800]}, "pass"),
        (NEMA, {"type": "volume", "range": [8000, 9000]}, "fail"),
        (NEMA, {"type": "hole_set", "diameter": [3.3, 3.5], "count": [4, 4], "through": True, "pattern": SQ}, "pass"),
        (NEMA, {"type": "hole_set", "diameter": [3.3, 3.5], "count": [6, 6]}, "fail"),
        (NEMA, {"type": "hole_set", "diameter": [3.3, 3.5], "count": [4, 4],
                "pattern": [[25.9, 26.1]] * 4 + [[36.7, 36.9]] * 2}, "fail"),
        (NEMA, {"type": "hole_set", "diameter": [3.3, 3.5], "count": [4, 4], "through": False}, "fail"),
        (NEMA, {"type": "bore", "diameter": [22.4, 22.6], "through": True}, "pass"),
        (NEMA, {"type": "bore", "diameter": [7.9, 8.1]}, "fail"),
        (FLANGE, {"type": "bore", "diameter": [5.9, 6.1], "depth_min": 15.0}, "pass"),
        (FLANGE, {"type": "bore", "diameter": [5.9, 6.1], "depth_min": 20.0}, "fail"),
        (FLANGE, {"type": "boss", "diameter": [11.9, 12.1], "height_min": 9.5}, "pass"),
        (FLANGE, {"type": "boss", "diameter": [11.9, 12.1], "height_min": 12.0}, "fail"),
        (FLANGE, {"type": "any_of", "checks": [{"type": "bore", "diameter": [7.9, 8.1]},
                                              {"type": "bore", "diameter": [5.9, 6.1]}]}, "pass"),
        (FLANGE, {"type": "any_of", "checks": [{"type": "bore", "diameter": [7.9, 8.1]},
                                              {"type": "boss", "diameter": [29, 31]}]}, "fail"),
        (FLANGE, {"type": "not_checked", "what": "flange outline"}, "not_checked"),
    ],
)
def test_each_check_type_pass_and_fail(shape, check, expected):
    report = grade(shape, [check])
    assert report["checks"][0]["status"] == expected, report["checks"][0]["detail"]


def test_attempt_passes_only_if_no_check_fails_and_partial_is_logged():
    report = grade(NEMA, [
        {"type": "bbox_min_dim", "min": 4.0},
        {"type": "bore", "diameter": [7.9, 8.1]},
        {"type": "not_checked", "what": "outline"},
    ])
    assert report["passed"] is False
    assert report["partial"] == pytest.approx(0.5)
    assert (report["n_pass"], report["n_fail"], report["n_not_checked"]) == (1, 1, 1)
    assert report["failure_class"] == "F6_dimension_miss"


def test_first_failing_check_sets_class_hole_set_is_feature_miss():
    report = grade(NEMA, [{"type": "hole_set", "diameter": [3.3, 3.5], "count": [6, 6]},
                          {"type": "bbox_min_dim", "min": 6.0}])
    assert report["failure_class"] == "F7_feature_miss"


def test_gate_failure_short_circuits_checks():
    two = mk([
        {"op": "box", "dx": 10, "dy": 10, "dz": 10},
        {"op": "box", "dx": 10, "dy": 10, "dz": 10, "at": [50, 0, 0]},
        {"op": "fuse", "a": 0, "b": 1},
    ])
    report = grade(two, [{"type": "bbox_min_dim", "min": 1.0}])
    assert report["gate"]["passed"] is False and report["checks"] == []
    assert report["failure_class"] == "F5_invalid_solid" and report["partial"] == 0.0


def test_all_pass_has_no_failure_class():
    report = grade(NEMA, [{"type": "bbox_min_dim", "min": 4.0}])
    assert report["passed"] is True and report["failure_class"] is None


def test_bbox_sorted_tolerates_occt_bspline_submicron_noise():
    from simready.occ_compat import BRepAlgoAPI_Cut, BRepPrimAPI_MakeCylinder, gp_Ax2, gp_Dir, gp_Pnt

    shaft = BRepPrimAPI_MakeCylinder(5.0, 50.0).Shape()
    cross = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(-10.0, 0.0, 25.0), gp_Dir(1.0, 0.0, 0.0)), 1.5, 20.0).Shape()
    shape = BRepAlgoAPI_Cut(shaft, cross).Shape()
    # AddOptimal on the perpendicular-cylinder B-spline seam yields 10.0000002 mm.
    report = grade(shape, [{"type": "bbox_sorted", "ranges": [[9.991, 10.0], [9.991, 10.0], [49.9, 50.1]]}])
    assert report["passed"] is True, report["checks"]
    # Real misses (e.g. 9 microns over 10.0) still fail.
    miss = grade(
        BRepPrimAPI_MakeCylinder(5.0045, 50.0).Shape(),
        [{"type": "bbox_sorted", "ranges": [[9.991, 10.0], [9.991, 10.0], [49.9, 50.1]]}],
    )
    assert miss["passed"] is False
