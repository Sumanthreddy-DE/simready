"""Executor tests for the geometry-gen DSL.

Most of these touch OCC and only run under the sr env. They are skipped when
pythonocc-core is not importable (base env).
"""

from __future__ import annotations

import json

import pytest

from simready.gen.spec import PartSpec

occ = pytest.importorskip(
    "OCC.Core.BRepPrimAPI",
    reason="pythonocc-core not available (run under the sr env)",
)

from simready.gen.build import build_part, build_shape, write_step
from simready.occ_utils import count_topology, shape_bounding_box
from simready.validator import validate_brep


# ----------------------------------------------------------------------------
# build_shape — in-process
# ----------------------------------------------------------------------------


def test_build_shape_box_only_has_six_faces():
    spec = PartSpec.model_validate(
        {"steps": [{"op": "box", "dx": 30, "dy": 40, "dz": 50}]}
    )
    shape = build_shape(spec)
    assert count_topology(shape)["face_count"] == 6


def test_build_shape_cyl_only_has_three_faces():
    spec = PartSpec.model_validate({"steps": [{"op": "cyl", "r": 5, "h": 10}]})
    shape = build_shape(spec)
    # OCC cylinder = lateral surface + 2 caps.
    assert count_topology(shape)["face_count"] == 3


def test_build_shape_bracket_with_hole_face_count_in_range():
    spec = PartSpec.model_validate(
        {
            "steps": [
                {"op": "box", "dx": 80, "dy": 60, "dz": 10},
                {"op": "cyl", "r": 5, "h": 10, "at": [40, 30, 0]},
                {"op": "cut", "a": 0, "b": 1},
            ]
        }
    )
    shape = build_shape(spec)
    n_faces = count_topology(shape)["face_count"]
    # A through-hole cut yields 4 box sides + 2 holed caps + 1 inner cyl wall
    # = 7 faces; allow [6, 10] in case OCC produces extra trimmed caps.
    assert 6 <= n_faces <= 10, f"unexpected face count {n_faces}"


def test_build_shape_l_bracket_fuse_face_count_in_range():
    spec = PartSpec.model_validate(
        {
            "steps": [
                {"op": "box", "dx": 60, "dy": 60, "dz": 10},
                {"op": "box", "dx": 60, "dy": 10, "dz": 50, "at": [0, 0, 10]},
                {"op": "fuse", "a": 0, "b": 1},
            ]
        }
    )
    shape = build_shape(spec)
    n_faces = count_topology(shape)["face_count"]
    assert 10 <= n_faces <= 18, f"unexpected face count {n_faces}"


def test_build_shape_returns_occ_valid_solid_for_simple_box():
    spec = PartSpec.model_validate(
        {"steps": [{"op": "box", "dx": 10, "dy": 10, "dz": 10}]}
    )
    shape = build_shape(spec)
    assert validate_brep(shape).is_valid is True


def test_build_shape_bbox_matches_inputs_for_box():
    spec = PartSpec.model_validate(
        {"steps": [{"op": "box", "dx": 30, "dy": 40, "dz": 50, "at": [1, 2, 3]}]}
    )
    bbox = shape_bounding_box(build_shape(spec))
    assert bbox is not None
    assert pytest.approx(bbox["xmin"], abs=1e-6) == 1.0
    assert pytest.approx(bbox["ymax"], abs=1e-6) == 42.0
    assert pytest.approx(bbox["zmax"], abs=1e-6) == 53.0


def test_write_step_round_trips_through_validator(tmp_path):
    spec = PartSpec.model_validate(
        {"steps": [{"op": "box", "dx": 20, "dy": 20, "dz": 20}]}
    )
    shape = build_shape(spec)
    out = tmp_path / "smoke.step"
    write_step(shape, out)
    assert out.exists() and out.stat().st_size > 0

    from simready.validator import validate_step_file

    result = validate_step_file(str(out))
    assert result.is_valid is True


# ----------------------------------------------------------------------------
# build_part — subprocess wrapper
# ----------------------------------------------------------------------------


def test_build_part_subprocess_happy_path(tmp_path):
    spec_dict = {"steps": [{"op": "box", "dx": 25, "dy": 25, "dz": 25}]}
    result = build_part(spec_dict, output_dir=str(tmp_path), timeout_s=60)
    # Result must be JSON-serialisable for a tool call payload.
    json.dumps(result, default=str)

    assert result.get("schema_valid") is True
    assert result.get("occ_valid") is True
    assert result.get("faces") == 6
    assert result.get("wrote") is True
    assert result["step_path"].endswith(".step")
    assert (tmp_path / "gen_").name in result["step_path"] or result["step_path"].startswith(
        str(tmp_path)
    )


def test_build_part_subprocess_bracket_with_hole(tmp_path):
    spec_dict = {
        "steps": [
            {"op": "box", "dx": 80, "dy": 60, "dz": 10},
            {"op": "cyl", "r": 5, "h": 10, "at": [40, 30, 0]},
            {"op": "cut", "a": 0, "b": 1},
        ]
    }
    result = build_part(spec_dict, output_dir=str(tmp_path), timeout_s=60)
    assert result["schema_valid"] is True
    assert result["occ_valid"] is True
    assert 6 <= result["faces"] <= 10
    assert result["bbox_mm"]["xmax"] - result["bbox_mm"]["xmin"] == pytest.approx(80.0, abs=1e-6)


def test_build_part_rejects_malformed_spec_in_parent():
    # No subprocess spawn should happen — schema validation runs in the parent.
    result = build_part({"steps": [{"op": "sphere", "r": 5}]}, timeout_s=60)
    assert result["schema_valid"] is False
    assert "error" in result


def test_build_part_rejects_empty_steps_in_parent():
    result = build_part({"steps": []}, timeout_s=60)
    assert result["schema_valid"] is False
    assert "error" in result


# ----------------------------------------------------------------------------
# resolve_output_dir — pure path logic (no OCC use, but module import needs it
# via the file-level importorskip above, so these still run only under sr)
# ----------------------------------------------------------------------------


def test_resolve_output_dir_ignores_cwd(tmp_path, monkeypatch):
    """Default output dir is anchored to the repo root, not the process cwd."""
    from simready.gen.build import resolve_output_dir

    monkeypatch.chdir(tmp_path)
    resolved = resolve_output_dir(None, None)
    assert resolved.is_absolute()
    assert str(tmp_path) not in str(resolved)
    assert resolved.parts[-2:] == ("data", "gen_parts")


def test_resolve_output_dir_explicit_wins(tmp_path):
    from simready.gen.build import resolve_output_dir

    explicit = tmp_path / "out"
    assert resolve_output_dir(explicit, None) == explicit
