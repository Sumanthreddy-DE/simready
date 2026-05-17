from simready.checks import (
    CheckResult,
    THIN_SOLID_ASPECT_RATIO,
    check_short_edges,
    check_thin_solid,
    run_essential_checks,
    run_essential_checks_detailed,
    summarize_findings,
)
from simready.parser import parse_geometry
from simready.validator import validate_step_file


def test_essential_checks_clean_box(valid_step_file):
    validation = validate_step_file(valid_step_file)
    assert validation.is_valid is True

    geometry = parse_geometry(validation.shape)
    findings = run_essential_checks(validation.shape, geometry)
    check_names = {finding["check"] for finding in findings}

    assert "DegenerateGeometry" not in check_names
    assert "NonManifoldEdges" not in check_names
    assert "OpenBoundaries" not in check_names
    assert "ShortEdges" not in check_names


def test_short_edge_check_on_fake_summary():
    class FakeShape:
        pass

    class FakeSummary:
        bounding_box = {
            "xmin": 0.0,
            "ymin": 0.0,
            "zmin": 0.0,
            "xmax": 100.0,
            "ymax": 1.0,
            "zmax": 1.0,
        }

    result = check_short_edges(FakeShape(), FakeSummary())
    assert isinstance(result, CheckResult)
    assert result.findings == []
    assert result.per_face == {}


def test_thin_plate_flags_thin_walls():
    validation = validate_step_file("tests/data/thin_plate.step")
    geometry = parse_geometry(validation.shape)
    findings = run_essential_checks(validation.shape, geometry)
    check_names = {finding["check"] for finding in findings}
    assert "ThinWalls" in check_names


def test_small_feature_fixture_flags_small_geometry():
    validation = validate_step_file("tests/data/small_feature_hole.step")
    geometry = parse_geometry(validation.shape)
    findings = run_essential_checks(validation.shape, geometry)
    check_names = {finding["check"] for finding in findings}
    assert "SmallFilletsOrHoles" in check_names or "SmallFeatures" in check_names


def test_open_face_flags_orientation_nuance():
    validation = validate_step_file("tests/data/open_face.step")
    geometry = parse_geometry(validation.shape)
    findings = run_essential_checks(validation.shape, geometry)
    check_names = {finding["check"] for finding in findings}
    assert "OrientationNuance" in check_names


def test_duplicate_body_fixture_flags_duplicate_body_heuristic():
    validation = validate_step_file("tests/data/duplicate_body.step")
    geometry = parse_geometry(validation.shape)
    findings = run_essential_checks(validation.shape, geometry)
    check_names = {finding["check"] for finding in findings}
    assert "DuplicateBodyHeuristic" in check_names


def test_duplicate_face_fixture_flags_duplicate_face_heuristic():
    validation = validate_step_file("tests/data/duplicate_face_compound.step")
    geometry = parse_geometry(validation.shape)
    findings = run_essential_checks(validation.shape, geometry)
    check_names = {finding["check"] for finding in findings}
    assert "DuplicateFaceHeuristic" in check_names


def test_run_essential_checks_detailed_returns_per_face_scores(valid_step_file):
    validation = validate_step_file(valid_step_file)
    geometry = parse_geometry(validation.shape)
    result = run_essential_checks_detailed(validation.shape, geometry)
    assert isinstance(result, CheckResult)
    assert isinstance(result.findings, list)
    assert isinstance(result.per_face, dict)


def test_thin_solid_clean_box_returns_no_finding(valid_step_file):
    """A normal box solid (aspect ratio ~1:1) must not trigger ThinSolid."""
    validation = validate_step_file(valid_step_file)
    geometry = parse_geometry(validation.shape)
    result = check_thin_solid(validation.shape, geometry)
    assert result.findings == []


def test_thin_solid_no_solids_returns_no_finding():
    """No solids -> short-circuit, no exception, empty result."""
    class FakeShape:
        pass

    class FakeSummary:
        solid_count = 0
        bounding_box = None

    result = check_thin_solid(FakeShape(), FakeSummary())
    assert result.findings == []


def test_thin_solid_fires_on_sliver_compound():
    """The synth sliver_face generator yields a Compound with a 0.001-thick
    sliver solid; ThinSolid must flag at Major and report the worst ratio."""
    import pytest
    from pathlib import Path

    fixture = Path("data/parametric_degraded/bracket_with_hole_0000__sliver_face.step")
    if not fixture.exists():
        pytest.skip("regen via scripts/generate_degraded_steps.py --max-inputs 1")

    validation = validate_step_file(str(fixture))
    geometry = parse_geometry(validation.shape)
    result = check_thin_solid(validation.shape, geometry)
    thin_findings = [f for f in result.findings if f["check"] == "ThinSolid"]
    assert len(thin_findings) == 1
    finding = thin_findings[0]
    assert finding["severity"] == "Major"
    assert "sliver" in finding["detail"].lower()
    # Generator uses 0.1*diag x 0.1*diag x 1e-3 -> ratio >> threshold.
    assert f"{THIN_SOLID_ASPECT_RATIO:.0f}" in finding["detail"]


def test_summarize_findings_counts_by_severity():
    summary = summarize_findings(
        [
            {"check": "A", "severity": "Major"},
            {"check": "B", "severity": "Minor"},
            {"check": "C", "severity": "Minor"},
        ]
    )
    assert summary["total"] == 3
    assert summary["by_severity"]["Major"] == 1
    assert summary["by_severity"]["Minor"] == 2
    assert summary["major_checks"] == ["A"]
