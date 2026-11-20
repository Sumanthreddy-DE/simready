"""DSL v2 executor: each op against an analytic volume or extent (OCC)."""

from __future__ import annotations

import math

import pytest

from simready.occ_compat import OCC_AVAILABLE

if not OCC_AVAILABLE:
    pytest.skip("OCC bindings not available", allow_module_level=True)

from simready.bench import geometry as geo  # noqa: E402
from simready.bench.concepts import CONCEPTS_V1, load_concepts  # noqa: E402
from simready.gen.build import build_shape  # noqa: E402
from simready.gen.build_v2 import KernelBuildError, build_shape_v2  # noqa: E402
from simready.gen.spec import PartSpec  # noqa: E402
from simready.gen.spec_v2 import PartSpecV2  # noqa: E402


def build(*steps):
    return build_shape_v2(PartSpecV2.model_validate({"steps": list(steps)}))


@pytest.mark.parametrize("c", [c for c in load_concepts(CONCEPTS_V1) if c.in_vocab][:10], ids=lambda c: c.concept_id)
def test_v1_specs_build_identically(c):
    a = geo.fingerprint(build_shape(PartSpec.model_validate(c.reference_spec)))
    b = geo.fingerprint(build_shape_v2(PartSpecV2.model_validate(c.reference_spec)))
    assert a == b


def test_cyl_axis_x_extent():
    assert geo.sorted_extents(build({"op": "cyl", "r": 5, "h": 40, "axis": "x"})) == pytest.approx([10, 10, 40], abs=1e-6)


def test_cone_and_sphere_volumes():
    assert geo.volume(build({"op": "cone", "r1": 3, "r2": 0, "h": 9})) == pytest.approx(math.pi * 9 * 9 / 3, rel=1e-6)
    assert geo.volume(build({"op": "sphere", "r": 10})) == pytest.approx(4 / 3 * math.pi * 1000, rel=1e-6)


def test_prism_triangle_volume_and_plane_mapping():
    tri = {"op": "prism", "points": [[0, 0], [30, 0], [0, 30]], "h": 5, "axis": "y"}
    shape = build(tri)
    assert geo.volume(shape) == pytest.approx(0.5 * 30 * 30 * 5, rel=1e-6)
    assert geo.sorted_extents(shape) == pytest.approx([5, 30, 30], abs=1e-6)


def test_regular_hexagon_flats_parallel_to_u():
    shape = build({"op": "regular_prism", "sides": 6, "across_flats": 10, "h": 4})
    assert geo.sorted_extents(shape) == pytest.approx([4, 10, 20 / math.sqrt(3)], abs=1e-6)


def test_polar_eight_holes_on_bolt_circle():
    shape = build(
        {"op": "cyl", "r": 50, "h": 10},
        {"op": "cyl", "r": 4.5, "h": 10, "at": [37.5, 0, 0]},
        {"op": "polar", "of": 1, "count": 8, "center": [0, 0, 0]},
        {"op": "cut", "a": 0, "b": 2},
    )
    holes = [f for f in geo.cylindrical_features(shape) if f.concave and abs(f.diameter - 9) < 1e-6]
    assert len(holes) == 8


def test_grid_two_by_two():
    shape = build(
        {"op": "box", "dx": 80, "dy": 60, "dz": 5},
        {"op": "cyl", "r": 2, "h": 5, "at": [10, 10, 0]},
        {"op": "grid", "of": 1, "nx": 2, "ny": 2, "dx": 60, "dy": 40},
        {"op": "cut", "a": 0, "b": 2},
    )
    assert geo.volume(shape) == pytest.approx(80 * 60 * 5 - 4 * math.pi * 4 * 5, rel=1e-6)


def test_fillet_top_edges_removes_material():
    plain = 80 * 50 * 10
    shape = build({"op": "box", "dx": 80, "dy": 50, "dz": 10}, {"op": "fillet", "a": 0, "r": 3, "edges": ">z"})
    removed = (1 - math.pi / 4) * 9 * (2 * 80 + 2 * 50)  # straight runs; corners add a little more
    assert plain - geo.volume(shape) == pytest.approx(removed, rel=0.05)


def test_chamfer_shaft_ends():
    shape = build({"op": "cyl", "r": 6, "h": 60}, {"op": "chamfer", "a": 0, "d": 1, "edges": "all"})
    assert geo.sorted_extents(shape) == pytest.approx([12, 12, 60], abs=1e-6)
    assert geo.volume(shape) < math.pi * 36 * 60


def test_impossible_fillet_is_a_kernel_build_error():
    with pytest.raises(KernelBuildError):
        build({"op": "box", "dx": 4, "dy": 4, "dz": 4}, {"op": "fillet", "a": 0, "r": 3, "edges": "all"})
