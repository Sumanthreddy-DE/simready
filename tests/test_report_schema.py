import json
from pathlib import Path

import pytest

from simready.pipeline import analyze_file_safe


def test_smoke_box_report_matches_schema():
    jsonschema = pytest.importorskip("jsonschema")
    schema_path = Path(__file__).resolve().parents[1] / "simready" / "report_schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    report = analyze_file_safe("tests/data/smoke_box.step")

    assert report["validation"]["is_valid"] is True
    assert report["geometry"]["face_count"] == 6
    jsonschema.validate(instance=report, schema=schema)
