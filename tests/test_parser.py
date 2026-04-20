from simready.parser import GeometrySummary, parse_geometry
from simready.validator import validate_step_file


def test_geometry_summary_dataclass_fields():
    summary = GeometrySummary(face_count=1, edge_count=2, solid_count=1, bounding_box=None)
    assert summary.face_count == 1
    assert summary.edge_count == 2
    assert summary.solid_count == 1
    assert summary.bounding_box is None


def test_parse_geometry_valid_box(valid_step_file):
    validation = validate_step_file(valid_step_file)
    summary = parse_geometry(validation.shape)
    assert summary.face_count == 6
    assert summary.solid_count == 1
    assert summary.bounding_box is not None
