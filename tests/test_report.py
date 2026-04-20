from types import SimpleNamespace

from simready.report import build_report, determine_status


def test_determine_status_invalid_input():
    status = determine_status([{"severity": "Critical"}], [])
    assert status == "InvalidInput"


def test_build_report_shape():
    validation = SimpleNamespace(is_valid=True, errors=[])
    geometry = SimpleNamespace(face_count=6, edge_count=12, solid_count=1, bounding_box=None)
    report = build_report("part.step", validation, geometry, [])
    assert report["input_file"] == "part.step"
    assert report["status"] == "SimulationReady"
    assert report["geometry"]["face_count"] == 6
