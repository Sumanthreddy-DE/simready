"""Guards on check_self_intersection (real-CAD OCC hang, diagnosed 2026-07-19).

Per-stage probes (docs/validation/occ_hang_diagnosis.md) showed BOPAlgo
hanging >90 s on 58-face cast/forged flanges — parts UNDER the 150-face
limit — while its 30 s thread watchdog never fired (OCC C++ holds the
GIL, so the join cannot wake). The separating predictor on the real-eval
set: B-spline/Bezier face count > 0. These tests pin the freeform-face
precheck that closes that gap.
"""

from __future__ import annotations

import pytest

occ = pytest.importorskip(
    "OCC.Core.BRepPrimAPI",
    reason="pythonocc-core not available (run under the sr env)",
)

from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert
from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox

from simready import checks


def _box(dx=20.0, dy=20.0, dz=20.0):
    return BRepPrimAPI_MakeBox(dx, dy, dz).Shape()


def _nurbs_box():
    """Box with every planar face converted to a genuine B-spline surface."""
    return BRepBuilderAPI_NurbsConvert(_box()).Shape()


def test_count_freeform_faces_zero_on_planar_box():
    assert checks._count_freeform_faces(_box()) == 0


def test_count_freeform_faces_positive_on_nurbs_converted_box():
    assert checks._count_freeform_faces(_nurbs_box()) == 6


def test_self_intersection_runs_on_planar_box():
    # Clean planar box: analyzer actually runs and reports no findings.
    result = checks.check_self_intersection(_box())
    assert result.findings == []


def test_self_intersection_skips_on_freeform_faces():
    result = checks.check_self_intersection(_nurbs_box())
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding["check"] == "SelfIntersectionSkipped"
    assert finding["severity"] == "Minor"
    assert "freeform" in finding["detail"].lower()


def test_freeform_limit_is_monkeypatchable(monkeypatch):
    # Raising the limit re-enables the analyzer on freeform parts.
    monkeypatch.setattr(checks, "SELF_INTERSECTION_FREEFORM_LIMIT", 100)
    result = checks.check_self_intersection(_nurbs_box())
    assert all(f["check"] != "SelfIntersectionSkipped" for f in result.findings)
