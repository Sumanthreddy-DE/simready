from simready.pipeline import analyze_file


def test_analyze_missing_file(missing_step_file):
    report = analyze_file(missing_step_file)
    assert report["status"] == "InvalidInput"
    assert report["validation"]["is_valid"] is False


def test_analyze_valid_file(valid_step_file):
    report = analyze_file(valid_step_file)
    assert report["validation"]["is_valid"] is True
    assert report["geometry"]["face_count"] == 6
    assert report["status"] in {"SimulationReady", "ReviewRecommended", "NeedsAttention"}
