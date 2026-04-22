from pathlib import Path

from simready.pipeline import analyze_file


def test_analyze_missing_file(missing_step_file):
    report = analyze_file(missing_step_file)
    assert report["status"] == "InvalidInput"
    assert report["validation"]["is_valid"] is False
    assert report["geometry"] is None
    assert report["findings"] == []
    assert report["bodies"] == []


def test_analyze_valid_file(valid_step_file):
    report = analyze_file(valid_step_file)
    assert report["validation"]["is_valid"] is True
    assert report["geometry"]["face_count"] == 6
    assert report["summary"]["total"] >= 0
    assert report["status"] in {"SimulationReady", "ReviewRecommended", "NeedsAttention"}
    assert set(report.keys()) >= {"input_file", "status", "summary", "validation", "geometry", "findings", "bodies", "heal", "elapsed_seconds"}


def test_analyze_valid_file_with_export(valid_step_file, tmp_path):
    export_path = tmp_path / "healed_export.step"
    report = analyze_file(valid_step_file, export_healed_path=str(export_path))
    if "healed_export" in report:
        assert Path(report["healed_export"]).exists()


def test_analyze_multi_body_file():
    report = analyze_file("tests/data/multi_body.step")
    assert report["validation"]["is_valid"] is True
    assert report["geometry"]["solid_count"] > 1
    checks = {finding["check"] for finding in report["findings"]}
    assert "MultiBodyDetected" in checks
    assert len(report["bodies"]) == 2
    assert report["bodies"][0]["body_index"] == 1
    assert "geometry" in report["bodies"][0]
    assert "findings" in report["bodies"][0]
    assert "heal" in report["bodies"][0]
    assert "summary" in report["bodies"][0]
    assert report["bodies"][0]["heal"]["attempted"] is False


def test_analyze_open_face_file():
    report = analyze_file("tests/data/open_face.step")
    assert report["validation"]["is_valid"] is True
    checks = {finding["check"] for finding in report["findings"]}
    assert "OpenBoundaries" in checks
    assert "OrientationNuance" in checks
    assert report["status"] in {"NeedsAttention", "ReviewRecommended"}


def test_analyze_thin_plate_file():
    report = analyze_file("tests/data/thin_plate.step")
    checks = {finding["check"] for finding in report["findings"]}
    assert "ThinWalls" in checks


def test_analyze_small_feature_file():
    report = analyze_file("tests/data/small_feature_hole.step")
    checks = {finding["check"] for finding in report["findings"]}
    assert "SmallFilletsOrHoles" in checks or "SmallFeatures" in checks


def test_analyze_duplicate_body_file():
    report = analyze_file("tests/data/duplicate_body.step")
    checks = {finding["check"] for finding in report["findings"]}
    assert "DuplicateBodyHeuristic" in checks


def test_analyze_duplicate_face_file():
    report = analyze_file("tests/data/duplicate_face_compound.step")
    checks = {finding["check"] for finding in report["findings"]}
    assert "DuplicateFaceHeuristic" in checks
