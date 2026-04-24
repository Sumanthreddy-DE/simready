from simready.ml.combiner import aggregate_face_scores, complexity_tier, fuse_scores, score_label, score_report


def test_fuse_scores_prefers_higher_signal_but_keeps_both():
    combined = fuse_scores({1: 1.0, 2: 0.2}, {1: 0.5, 2: 0.8})
    assert combined[1] == 0.8
    assert combined[2] == 0.56


def test_aggregate_face_scores_returns_mean():
    assert aggregate_face_scores({1: 0.5, 2: 1.0, 3: 0.0}) == 0.5


def test_score_report_skips_ml_penalty_when_ml_unavailable():
    result = score_report(
        findings=[{"severity": "Major"}, {"severity": "Minor"}],
        rule_scores={1: 1.0},
        ml_scores={1: 0.5},
        ml_available=False,
    )
    assert result.overall_score == 80.0
    assert result.ml_penalty_applied is False
    assert result.ml_penalty_points == 0.0


def test_score_report_applies_ml_penalty_when_ml_available():
    result = score_report(
        findings=[{"severity": "Minor"}],
        rule_scores={1: 0.4, 2: 0.1},
        ml_scores={1: 0.5, 2: 1.0},
        ml_available=True,
    )
    assert result.overall_score == 80.0
    assert result.ml_penalty_applied is True
    assert result.ml_penalty_points == 15.0


def test_score_label_ranges():
    assert score_label(95) == "SimulationReady"
    assert score_label(75) == "ReviewRecommended"
    assert score_label(55) == "NeedsAttention"
    assert score_label(10) == "NotReady"


def test_complexity_tier_simple():
    result = complexity_tier(6)
    assert result["tier"] == "simple"
    assert result["confidence"] == "high"


def test_complexity_tier_moderate():
    result = complexity_tier(100)
    assert result["tier"] == "moderate"


def test_complexity_tier_complex():
    result = complexity_tier(500)
    assert result["tier"] == "complex"


def test_complexity_tier_very_complex():
    result = complexity_tier(1500)
    assert result["tier"] == "very_complex"
    assert result["confidence"] == "minimal"
