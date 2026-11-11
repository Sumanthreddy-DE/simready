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
