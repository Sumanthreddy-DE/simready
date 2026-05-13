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
    assert set(report.keys()) >= {"input_file", "status", "summary", "validation", "geometry", "findings", "bodies", "heal", "elapsed_seconds", "per_face_scores", "combined_per_face_scores", "score", "ml", "graph"}


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
    assert "per_face_scores" in report["bodies"][0]
    assert "combined_per_face_scores" in report["bodies"][0]
    assert "score" in report["bodies"][0]
    assert "ml" in report["bodies"][0]
    assert "graph" in report["bodies"][0]


def test_analyze_open_face_file():
    report = analyze_file("tests/data/open_face.step")
    assert report["validation"]["is_valid"] is True
    checks = {finding["check"] for finding in report["findings"]}
    assert "OpenBoundaries" in checks
    assert "OrientationNuance" in checks
    assert report["status"] in {"NotReady", "NeedsAttention", "ReviewRecommended"}


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


def test_clean_box_has_no_self_intersection():
    """Regression: BRepAlgoAPI_Common(shape, copy) used to flag every clean solid.

    BOPAlgo_ArgumentAnalyzer should report no faulty topology for a simple box.
    """
    report = analyze_file("tests/data/smoke_box.step")
    checks = {finding["check"] for finding in report["findings"]}
    assert "SelfIntersection" not in checks
    assert report["summary"]["by_severity"]["Major"] == 0
    assert report["score"]["overall"] == 100.0


def test_combined_per_face_scores_match_face_count():
    """Regression: face-index union of rule (1-based) and ML (0-based) used
    to produce N+1 entries with a phantom face 0. After 0-based unification,
    combined keys must equal exactly 0..face_count-1.
    """
    report = analyze_file("tests/data/smoke_box.step")
    face_count = report["geometry"]["face_count"]
    combined = report["combined_per_face_scores"]
    assert len(combined) == face_count
    assert set(combined.keys()) == set(range(face_count))


def test_rule_face_mean_is_a_mean_not_a_count():
    """Regression: pipeline reported `rule_face_count` under the name
    `rule_face_mean`. Must be a [0, 1] mean.
    """
    report = analyze_file("tests/data/thin_plate.step")
    mean = report["score"]["rule_face_mean"]
    assert isinstance(mean, float)
    assert 0.0 <= mean <= 1.0
    assert "rule_face_count" in report["score"]


def test_thin_walls_spreads_per_face_across_all_faces():
    """Regression: ThinWalls was a body-level finding that wrote {0: score}
    into per_face, colliding with the real face index 0. It should now
    spread uniformly across every face of the body.
    """
    report = analyze_file("tests/data/thin_plate.step")
    face_count = report["geometry"]["face_count"]
    per_face = report["per_face_scores"]
    assert "ThinWalls" in {f["check"] for f in report["findings"]}
    assert len(per_face) == face_count
    assert set(per_face.keys()) == set(range(face_count))
    values = list(per_face.values())
    assert all(0.0 < v <= 1.0 for v in values)
    assert max(values) - min(values) < 1e-6  # uniform spread


def test_brepnet_inference_is_honestly_labelled_heuristic():
    """Regression: TorchBRepNetAdapter claimed `weights_loaded=True` and
    `score_source="checkpoint-adapter"` while still running the heuristic.
    The honest module reports weights_loaded=False with a graph-feature label.
    """
    report = analyze_file("tests/data/smoke_box.step")
    ml = report["ml"]
    assert ml["weights_loaded"] is False
    assert ml["weights_path"] is None
    assert "heuristic" in ml["score_source"].lower()
    assert "heuristic" in ml["model_name"].lower()
    assert any("heuristic" in note.lower() or "not a learned model" in note.lower() for note in ml["notes"])
