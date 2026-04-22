from simready.html_report import render_html_report


def test_render_html_report_writes_file(tmp_path):
    report = {
        "input_file": "part.step",
        "status": "ReviewRecommended",
        "score": {"overall": 72.0, "label": "ReviewRecommended", "combined_face_mean": 0.61, "ml_penalty_applied": False, "ml_penalty_points": 0.0},
        "geometry": {"face_count": 6, "edge_count": 12, "solid_count": 1},
        "elapsed_seconds": 1.2,
        "findings": [{"severity": "Minor", "check": "SmallFeatures", "detail": "Detected 1 tiny face.", "suggestion": "Inspect before meshing."}],
        "ml": {"score_source": "heuristic-fallback", "weights_path": None},
    }
    output = tmp_path / "report.html"
    path = render_html_report(report, str(output))
    assert path == str(output)
    html = output.read_text(encoding="utf-8")
    assert "SimReady Analysis" in html
    assert "72.0/100" in html
    assert "SmallFeatures" in html
