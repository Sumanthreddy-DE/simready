"""Tests for analyze_file_safe — the subprocess-isolated pipeline entry.

Rationale: Python thread timeouts (analyze_file's own guard included)
cannot interrupt a hung OCC C++ call; only a spawn subprocess +
Process.terminate() can. analyze_file_safe wraps the full analysis in
one and is the entry point for the copilot tool, Streamlit UIs and CLI.
"""

from __future__ import annotations

import pytest

occ = pytest.importorskip(
    "OCC.Core.BRepPrimAPI",
    reason="pythonocc-core not available (run under the sr env)",
)

from simready.pipeline import analyze_file_safe


@pytest.fixture()
def box_step(tmp_path):
    from simready.gen.spec import PartSpec
    from simready.gen.build import build_shape, write_step

    p = tmp_path / "box.step"
    write_step(
        build_shape(
            PartSpec.model_validate(
                {"steps": [{"op": "box", "dx": 20, "dy": 20, "dz": 20}]}
            )
        ),
        p,
    )
    return p


def test_safe_happy_path_matches_report_shape(box_step):
    report = analyze_file_safe(str(box_step), timeout=180)
    assert report["status"] != "InvalidInput"
    assert report["geometry"]["face_count"] == 6
    assert "score" in report
    assert "findings" in report
    assert "ml" in report


def test_safe_timeout_returns_timeout_report(box_step):
    # Impossible budget: spawn + interpreter start alone exceed it, so the
    # kill path triggers deterministically without needing a real OCC hang.
    report = analyze_file_safe(str(box_step), timeout=0.01)
    assert report["status"] == "InvalidInput"
    errors = report["validation"]["errors"]
    assert errors and errors[0]["check"] == "AnalysisTimeout"


def test_safe_missing_file_reports_like_analyze_file(tmp_path):
    report = analyze_file_safe(str(tmp_path / "nope.step"), timeout=120)
    # analyze_file's contract for unloadable input: invalid report, no raise.
    assert report["validation"]["is_valid"] is False
