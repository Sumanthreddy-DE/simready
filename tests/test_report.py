from types import SimpleNamespace

import click

from simready.report import build_report, determine_status, render_terminal_report


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


def test_build_report_includes_elapsed_seconds_when_present():
    validation = SimpleNamespace(is_valid=True, errors=[])
    report = build_report("part.step", validation, None, [], bodies=[], elapsed_seconds=1.25)
    assert report["elapsed_seconds"] == 1.25


def test_terminal_report_shows_validation_failure_not_clean_geometry():
    report = {
        "input_file": "broken.step",
        "status": "InvalidInput",
        "validation": {
            "is_valid": False,
            "errors": [{
                "check": "MissingDependency",
                "severity": "Critical",
                "detail": "pythonocc-core is not available.",
                "suggestion": "Install the geometry dependencies.",
            }],
        },
        "findings": [],
    }

    output = render_terminal_report(report)

    assert "MissingDependency" in output
    assert "pythonocc-core is not available." in output
    assert "Install the geometry dependencies." in output
    assert "Clean geometry" not in output


def test_terminal_report_is_encodable_through_click_windows_stream(monkeypatch):
    class Cp1252Stream:
        encoding = "cp1252"

        def __init__(self):
            self.parts = []

        def write(self, value):
            value.encode("cp1252")
            self.parts.append(value)

        def flush(self):
            pass

    stream = Cp1252Stream()
    monkeypatch.setattr(click.utils, "_default_text_stdout", lambda: stream)
    report = {
        "input_file": "valid.step",
        "status": "SimulationReady",
        "validation": {"is_valid": True, "errors": []},
        "findings": [],
    }

    click.echo(render_terminal_report(report), nl=False)

    assert "No findings. Clean geometry." in "".join(stream.parts)
