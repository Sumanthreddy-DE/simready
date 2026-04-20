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
    assert report["status"] in {"SimulationReady", "ReviewRecommended", "NeedsAttention"}
    assert set(report.keys()) == {"input_file", "status", "validation", "geometry", "findings", "bodies"}


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


def test_analyze_open_face_file():
    report = analyze_file("tests/data/open_face.step")
    assert report["validation"]["is_valid"] is True
    checks = {finding["check"] for finding in report["findings"]}
    assert "OpenBoundaries" in checks
    assert report["status"] in {"NeedsAttention", "ReviewRecommended"}
