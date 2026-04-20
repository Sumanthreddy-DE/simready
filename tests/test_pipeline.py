from simready.pipeline import analyze_file


def test_analyze_missing_file(missing_step_file):
    report = analyze_file(missing_step_file)
    assert report["status"] == "InvalidInput"
    assert report["validation"]["is_valid"] is False
