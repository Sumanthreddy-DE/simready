"""Smoke tests for real-world GrabCAD STEP files.

These tests are skipped if the GrabCAD sample files are not present.
They verify that the pipeline does not crash on real-world geometry
and produces a structurally valid report.
"""
import pytest
from pathlib import Path

from simready.pipeline import analyze_file

GRABCAD_DIR = Path("tests/data/grabcad")
GRABCAD_FILES = list(GRABCAD_DIR.glob("*.step")) + list(GRABCAD_DIR.glob("*.stp"))

REQUIRED_REPORT_KEYS = {"input_file", "status", "summary", "validation", "geometry", "findings"}


@pytest.mark.skipif(not GRABCAD_FILES, reason="No GrabCAD sample files in tests/data/grabcad/")
@pytest.mark.parametrize("step_file", GRABCAD_FILES, ids=lambda p: p.name)
def test_grabcad_no_crash(step_file):
    """Pipeline must not crash on real-world STEP files."""
    report = analyze_file(str(step_file))
    assert isinstance(report, dict)
    assert REQUIRED_REPORT_KEYS <= set(report.keys())
    assert report["status"] in {"SimulationReady", "ReviewRecommended", "NeedsAttention", "NotReady", "InvalidInput"}


@pytest.mark.skipif(not GRABCAD_FILES, reason="No GrabCAD sample files in tests/data/grabcad/")
@pytest.mark.parametrize("step_file", GRABCAD_FILES, ids=lambda p: p.name)
def test_grabcad_score_in_range(step_file):
    """Score must be a number between 0 and 100."""
    report = analyze_file(str(step_file))
    score = report.get("score", {}).get("overall")
    assert score is not None
    assert 0 <= score <= 100


@pytest.mark.skipif(not GRABCAD_FILES, reason="No GrabCAD sample files in tests/data/grabcad/")
@pytest.mark.parametrize("step_file", GRABCAD_FILES, ids=lambda p: p.name)
def test_grabcad_has_complexity_tier(step_file):
    """Report must include complexity tier after Task 8."""
    report = analyze_file(str(step_file))
    assert "complexity" in report
    assert report["complexity"]["tier"] in {"simple", "moderate", "complex", "very_complex"}
    assert report["complexity"]["confidence"] in {"high", "medium", "low", "minimal"}
