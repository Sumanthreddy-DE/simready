"""Smoke tests for simready/copilot/renderer.py.

Asserts each event type renders without raising and that key strings reach
the captured output. Layout / colour / boxes are not asserted.
"""
from __future__ import annotations

import io

import pytest
from rich.console import Console

from simready.copilot.renderer import PlainRenderer, RichRenderer


@pytest.fixture
def captured_console() -> Console:
    return Console(file=io.StringIO(), width=120, force_terminal=False, color_system=None)


def _analyze_event() -> dict:
    return {
        "type": "tool_result",
        "iteration": 1,
        "name": "analyze_geometry",
        "result": {
            "status": "Caution",
            "complexity": "moderate",
            "score": {"overall": 72.5, "label": "Caution"},
            "geometry": {"face_count": 148, "edge_count": 412, "solid_count": 1},
            "body_count": 1,
            "severity_counts": {"Critical": 1, "Major": 2, "Minor": 1, "Info": 0},
            "findings_total": 4,
            "findings": [
                {"check": "Degenerate", "severity": "Critical", "detail": "bad"},
                {"check": "OpenBoundaries", "severity": "Major", "detail": "gap"},
            ],
        },
    }


def _fix_event() -> dict:
    return {
        "type": "tool_result",
        "iteration": 2,
        "name": "suggest_fixes",
        "result": {
            "suggestions": [
                {"check": "Degenerate", "severity": "Critical", "fix": "rebuild face"},
                {"check": "OpenBoundaries", "severity": "Major", "fix": "stitch gap"},
            ],
            "severity_counts": {"Critical": 1, "Major": 1, "Minor": 0, "Info": 0},
            "total_findings": 2,
            "returned": 2,
        },
    }


def _lookup_event() -> dict:
    return {
        "type": "tool_result",
        "iteration": 3,
        "name": "lookup_standard",
        "result": {
            "status": "ok",
            "query": "mesh quality",
            "results": [
                {"source": "NAFEMS_QA01.pdf", "page": 4, "score": 0.91,
                 "text": "aspect ratio < 5 for linear-elastic"},
            ],
        },
    }


def test_rich_renderer_handles_all_event_types(captured_console: Console) -> None:
    r = RichRenderer(console=captured_console)
    r.header("gpt-4o-mini", "/tmp/x.STEP", "What's wrong?")
    r({"type": "iteration_start", "iteration": 1})
    r({"type": "tool_call", "iteration": 1, "name": "analyze_geometry", "arguments": '{"step_path": "/tmp/x.STEP"}'})
    r(_analyze_event())
    r(_fix_event())
    r(_lookup_event())
    r({"type": "final_text", "text": "Verdict: Caution.", "iterations": 4, "usage": {"prompt_tokens": 100}})
    output = captured_console.file.getvalue()
    assert "SimReady Copilot" in output
    assert "analyze_geometry" in output
    assert "Caution" in output
    assert "Degenerate" in output
    assert "NAFEMS_QA01.pdf" in output
    assert "Verdict: Caution." in output


def test_rich_renderer_handles_error_result(captured_console: Console) -> None:
    r = RichRenderer(console=captured_console)
    r({
        "type": "tool_result",
        "iteration": 1,
        "name": "analyze_geometry",
        "result": {"error": "FileNotFound", "message": "No CAD file at /nope.step"},
    })
    output = captured_console.file.getvalue()
    assert "FileNotFound" in output
    assert "/nope.step" in output


def test_rich_renderer_handles_lookup_no_index(captured_console: Console) -> None:
    r = RichRenderer(console=captured_console)
    r({
        "type": "tool_result",
        "iteration": 1,
        "name": "lookup_standard",
        "result": {"status": "no_index", "message": "RAG index not found at data/fea_docs_index.json"},
    })
    output = captured_console.file.getvalue()
    assert "no_index" in output


def test_rich_renderer_handles_max_iterations(captured_console: Console) -> None:
    r = RichRenderer(console=captured_console)
    r({"type": "max_iterations", "iterations": 6})
    assert "max_iterations" in captured_console.file.getvalue()


def test_plain_renderer_outputs_text_for_each_event(capsys: pytest.CaptureFixture[str]) -> None:
    r = PlainRenderer()
    r.header("gpt-4o-mini", "/tmp/x.STEP", "Q?")
    r({"type": "tool_call", "iteration": 1, "name": "analyze_geometry", "arguments": "{}"})
    r({"type": "tool_result", "iteration": 1, "name": "analyze_geometry",
       "result": {"status": "Pass"}})
    r({"type": "final_text", "text": "all good", "iterations": 1, "usage": {"prompt_tokens": 5}})
    out = capsys.readouterr().out
    assert "MODEL: gpt-4o-mini" in out
    assert "tool_call #1" in out
    assert "all good" in out
