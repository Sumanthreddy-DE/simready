from simready.parser import GeometrySummary


def test_geometry_summary_dataclass_fields():
    summary = GeometrySummary(face_count=1, edge_count=2, solid_count=1, bounding_box=None)
    assert summary.face_count == 1
    assert summary.edge_count == 2
    assert summary.solid_count == 1
    assert summary.bounding_box is None
