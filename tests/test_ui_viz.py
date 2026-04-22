from simready.ui.viz import build_face_overlay_payload, face_score_color, ml_heatmap_color


def test_face_score_color_thresholds():
    assert face_score_color(0.8) == "#ef4444"
    assert face_score_color(0.5) == "#f59e0b"
    assert face_score_color(0.1) == "#22c55e"


def test_ml_heatmap_color_thresholds():
    assert ml_heatmap_color(0.8) == "#fb923c"
    assert ml_heatmap_color(0.5) == "#60a5fa"
    assert ml_heatmap_color(0.1) == "#1d4ed8"


def test_build_face_overlay_payload():
    report = {
        "combined_per_face_scores": {1: 0.2, 2: 0.9},
        "ml": {"per_face_scores": {1: 0.3, 2: 0.8}},
    }
    payload = build_face_overlay_payload(report)
    assert len(payload) == 2
    assert payload[1]["combined_color"] == "#ef4444"
