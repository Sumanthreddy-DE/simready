"""Geometry measurements on hand-built shapes (skips without OCC bindings)."""

from __future__ import annotations

import math

import pytest

from simready.occ_compat import OCC_AVAILABLE, BRep_Builder, BRepPrimAPI_MakeBox, TopoDS_Shell, topods

if not OCC_AVAILABLE:
    pytest.skip("OCC bindings not available", allow_module_level=True)

from simready.bench import geometry as geo
from simready.gen.build import build_shape
from simready.gen.spec import PartSpec
from simready.occ_utils import iter_faces


def mk(steps):
    return build_shape(PartSpec.model_validate({"steps": steps}))


PLATE = [
    {"op": "box", "dx": 42, "dy": 42, "dz": 5},
    {"op": "cyl", "r": 1.6, "h": 5, "at": [5.5, 5.5, 0]},
    {"op": "cut", "a": 0, "b": 1},
    {"op": "cyl", "r": 11, "h": 3, "at": [21, 21, 2]},
    {"op": "cut", "a": 2, "b": 3},
]


def _holes(shape):
    return sorted((f for f in geo.cylindrical_features(shape) if f.concave), key=lambda f: f.diameter)


def test_gate_passes_valid_box_and_reports_volume():
    g = geo.run_gate(BRepPrimAPI_MakeBox(10.0, 20.0, 30.0).Shape())
    assert g.passed and g.reason == "" and math.isclose(g.volume, 6000.0)


def test_gate_fails_open_shell():
    box = BRepPrimAPI_MakeBox(10.0, 20.0, 30.0).Shape()
    builder, shell = BRep_Builder(), TopoDS_Shell()
    builder.MakeShell(shell)
    for i, face in iter_faces(box):
        if i < 5:
            builder.Add(shell, face)
    g = geo.run_gate(shell)
    assert not g.passed and g.reason == "open_shell" and g.free_edges > 0


def test_gate_fails_reversed_solid_on_volume():
    rev = topods.Solid(BRepPrimAPI_MakeBox(10.0, 20.0, 30.0).Shape().Reversed())
    g = geo.run_gate(rev)
    assert not g.passed and g.reason == "non_positive_volume"


def test_gate_fails_disjoint_fuse_on_solid_count():
    s = mk([
        {"op": "box", "dx": 10, "dy": 10, "dz": 10},
        {"op": "box", "dx": 10, "dy": 10, "dz": 10, "at": [50, 0, 0]},
        {"op": "fuse", "a": 0, "b": 1},
    ])
    g = geo.run_gate(s)
    assert not g.passed and g.reason == "solid_count 2 != 1"
    assert geo.run_gate(s, expected_solids=2).passed


def test_sorted_extents_are_placement_invariant():
    assert geo.sorted_extents(mk(PLATE)) == pytest.approx([5.0, 42.0, 42.0])


def test_through_hole_and_blind_recess():
    small, big = _holes(mk(PLATE))
    assert small.diameter == pytest.approx(3.2) and small.through and small.full
    assert small.depth == pytest.approx(5.0)
    assert big.diameter == pytest.approx(22.0) and big.through is False
    assert big.depth == pytest.approx(3.0)


def test_counterbore_small_is_through_large_is_blind():
    s = mk([
        {"op": "box", "dx": 20, "dy": 20, "dz": 10},
        {"op": "cyl", "r": 1.7, "h": 10, "at": [10, 10, 0]},
        {"op": "cut", "a": 0, "b": 1},
        {"op": "cyl", "r": 3, "h": 3, "at": [10, 10, 7]},
        {"op": "cut", "a": 2, "b": 3},
    ])
    small, big = _holes(s)
    assert small.through is True and big.through is False


def test_stacked_flange_bosses_and_bore():
    s = mk([
        {"op": "cyl", "r": 10, "h": 5},
        {"op": "cyl", "r": 6, "h": 10, "at": [0, 0, 5]},
        {"op": "fuse", "a": 0, "b": 1},
        {"op": "cyl", "r": 3, "h": 15},
        {"op": "cut", "a": 2, "b": 3},
    ])
    feats = geo.cylindrical_features(s)
    convex = sorted(f.diameter for f in feats if not f.concave)
    assert convex == pytest.approx([12.0, 20.0])
    (bore,) = [f for f in feats if f.concave]
    assert bore.diameter == pytest.approx(6.0) and bore.through and bore.depth == pytest.approx(15.0)


def test_hole_through_two_fused_slabs_merges_into_one_feature():
    s = mk([
        {"op": "box", "dx": 20, "dy": 20, "dz": 5},
        {"op": "box", "dx": 20, "dy": 20, "dz": 5, "at": [0, 0, 5]},
        {"op": "fuse", "a": 0, "b": 1},
        {"op": "cyl", "r": 2, "h": 10, "at": [10, 10, 0]},
        {"op": "cut", "a": 2, "b": 3},
    ])
    (hole,) = _holes(s)
    assert hole.depth == pytest.approx(10.0) and hole.through


def test_edge_notch_is_not_a_full_hole():
    s = mk([
        {"op": "box", "dx": 20, "dy": 20, "dz": 5},
        {"op": "cyl", "r": 3, "h": 5, "at": [0, 10, 0]},
        {"op": "cut", "a": 0, "b": 1},
    ])
    (notch,) = _holes(s)
    assert not notch.full


def test_axis_distance_between_parallel_holes():
    s = mk([
        {"op": "box", "dx": 42, "dy": 42, "dz": 5},
        {"op": "cyl", "r": 1.7, "h": 5, "at": [5.5, 5.5, 0]},
        {"op": "cut", "a": 0, "b": 1},
        {"op": "cyl", "r": 1.7, "h": 5, "at": [36.5, 36.5, 0]},
        {"op": "cut", "a": 2, "b": 3},
    ])
    a, b = _holes(s)
    assert geo.axis_distance(a, b) == pytest.approx(31.0 * math.sqrt(2))


def test_fingerprint_is_stable_across_rebuilds():
    fp = geo.fingerprint(mk(PLATE))
    assert fp == geo.fingerprint(mk(PLATE))
    assert fp["extents"] == [5.0, 42.0, 42.0] and fp["solids"] == 1


def test_nominal_cylinder_extent_within_engineer_range():
    extents = geo.sorted_extents(mk([{"op": "cyl", "r": 10, "h": 5}]))
    assert 19.987 <= extents[2] <= 20.0


def test_nominal_plate_extent_does_not_exceed_thickness():
    extents = geo.sorted_extents(mk([{"op": "box", "dx": 42, "dy": 42, "dz": 2}]))
    assert extents[0] <= 2.0


@pytest.mark.parametrize("floor_mm", [0.2, 0.02])
def test_blind_hole_with_thin_floor_is_not_through(floor_mm):
    s = mk([
        {"op": "box", "dx": 20, "dy": 20, "dz": 10},
        {"op": "cyl", "r": 2.5, "h": 10.0 - floor_mm, "at": [10, 10, floor_mm]},
        {"op": "cut", "a": 0, "b": 1},
    ])
    (hole,) = _holes(s)
    assert hole.through is False
