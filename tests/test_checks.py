import pytest

from simready.checks import check_short_edges, run_essential_checks
from simready.parser import parse_geometry
from simready.validator import validate_step_file


def test_essential_checks_clean_box(valid_step_file):
    validation = validate_step_file(valid_step_file)
    assert validation.is_valid is True

    geometry = parse_geometry(validation.shape)
    findings = run_essential_checks(validation.shape, geometry)
    check_names = {finding["check"] for finding in findings}

    assert "DegenerateGeometry" not in check_names
    assert "NonManifoldEdges" not in check_names
    assert "OpenBoundaries" not in check_names
    assert "ShortEdges" not in check_names


def test_short_edge_check_on_fake_summary():
    class FakeShape:
        pass

    class FakeSummary:
        bounding_box = {
            "xmin": 0.0,
            "ymin": 0.0,
            "zmin": 0.0,
            "xmax": 100.0,
            "ymax": 1.0,
            "zmax": 1.0,
        }

    findings = check_short_edges(FakeShape(), FakeSummary())
    assert findings == []
