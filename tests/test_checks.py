from simready.checks import (
    check_short_edges,
    run_essential_checks,
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

    findings = check_short_edges(FakeShape(), FakeSummary())
    assert findings == []


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
