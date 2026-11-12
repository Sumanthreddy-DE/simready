"""OCC-dependent copilot tests, separate so pure tool tests run without pythonocc."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.occ

occ = pytest.importorskip(
    "OCC.Core.BRepPrimAPI",
    reason="pythonocc-core not available (run under the sr env)",
)


def test_build_part_dispatch_happy_box(tmp_path, monkeypatch) -> None:
    # Redirect the executor's default output dir to a tempdir so the test
    # doesn't litter data/gen_parts/.
    monkeypatch.chdir(tmp_path)
    from simready.copilot.tools import dispatch_tool

    result = dispatch_tool(
        "build_part",
        {"spec": {"steps": [{"op": "box", "dx": 15, "dy": 15, "dz": 15}]}, "timeout_seconds": 60},
    )
    assert result["schema_valid"] is True
    assert result["occ_valid"] is True
    assert result["faces"] == 6
    assert result["step_path"].endswith(".step")


@pytest.mark.parametrize("slim", [False, True])
def test_analysis_artifact_policy(tmp_path, monkeypatch, slim) -> None:
    """Default emits both artifacts; verifier emits neither, even on disk."""
    from pathlib import Path

    from OCC.Core.STEPControl import STEPControl_AsIs, STEPControl_Writer
    from OCC.Core.IFSelect import IFSelect_RetDone
    from simready.copilot.tools import analyze_geometry
    from simready.gen.verify import analyze_generated_part

    step = tmp_path / "box.step"
    writer = STEPControl_Writer()
    writer.Transfer(occ.BRepPrimAPI_MakeBox(60, 40, 30).Shape(), STEPControl_AsIs)
    assert writer.Write(str(step)) == IFSelect_RetDone
    monkeypatch.chdir(tmp_path)
    if slim:
        verified = analyze_generated_part(str(step))
        assert verified["ok"] is True
        result = verified["analysis"]
        assert "image_path" not in result
        assert "healed_step_path" not in result
        assert not list((tmp_path / "data/copilot_renders").glob("**/*"))
        assert not list((tmp_path / "data/healed_steps").glob("**/*"))
    else:
        result = analyze_geometry(str(step))
        assert Path(result["image_path"]).is_file()
        assert Path(result["healed_step_path"]).is_file()
    assert result["status"] != "InvalidInput"
    assert result["geometry"]["face_count"] == 6
