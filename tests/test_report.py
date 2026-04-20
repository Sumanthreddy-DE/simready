from types import SimpleNamespace

from simready.report import build_report, determine_status


def test_determine_status_invalid_input():
    status = determine_status([{"severity": "Critical"}], [])
    assert status == "InvalidInput"


def test_determine_status_major_finding():
    status = determine_status([], [{"severity": "Major"}])
    assert status == "NeedsAttention"


def test_determine_status_minor_finding():
    status = determine_status([], [{"severity": "Minor"}])
    assert status == "ReviewRecommended"


def test_build_report_shape():
    validation = SimpleNamespace(is_valid=True, errors=[])
    geometry = SimpleNamespace(face_count=6, edge_count=12, solid_count=1, bounding_box=None)
    report = build_report("part.step", validation, geometry, [], bodies=[])
    assert report["input_file"] == "part.step"
    assert report["status"] == "SimulationReady"
    assert report["summary"]["total"] == 0
    assert report["geometry"]["face_count"] == 6
    assert report["validation"] == {"is_valid": True, "errors": []}
    assert report["findings"] == []
    assert report["bodies"] == []
    assert set(report.keys()) == {"input_file", "status", "summary", "validation", "geometry", "findings", "bodies"}
