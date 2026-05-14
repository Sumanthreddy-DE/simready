"""Tests for the SimReady Copilot tool resolvers.

Day 1 scope: tool dispatch correctness, error paths, schema validity.
Day 3: lookup_standard wiring to rag (no-index + empty-query paths only;
real cosine retrieval is covered in test_copilot_rag.py).
Live API calls are NOT exercised here — see test_copilot_agent.py for that.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from simready.copilot import rag
from simready.copilot.tools import (
    SEVERITY_ORDER,
    TOOL_SCHEMAS,
    analyze_geometry,
    dispatch_tool,
    lookup_standard,
    suggest_fixes,
)


@pytest.fixture(autouse=True)
def _no_default_rag_index(monkeypatch, tmp_path) -> None:
    """Force lookup_standard to see no index, unless a test overrides."""
    monkeypatch.setattr(rag, "DEFAULT_INDEX_PATH", tmp_path / "no_such_index.json")
    monkeypatch.setenv("SIMREADY_RAG_INDEX", str(tmp_path / "no_such_index.json"))
    rag.clear_index_cache()
    yield
    rag.clear_index_cache()


def test_tool_schemas_have_expected_names() -> None:
    names = [s["function"]["name"] for s in TOOL_SCHEMAS]
    assert names == ["analyze_geometry", "suggest_fixes", "lookup_standard"]


def test_tool_schemas_declare_required_args() -> None:
    for schema in TOOL_SCHEMAS:
        params = schema["function"]["parameters"]
        assert params["type"] == "object"
        assert "properties" in params
        assert "required" in params
        for required_arg in params["required"]:
            assert required_arg in params["properties"]


def test_severity_order_keys_match_finding_severities() -> None:
    expected = {"Critical", "Major", "Minor", "Info"}
    assert set(SEVERITY_ORDER) == expected


def test_analyze_geometry_returns_error_for_missing_file(missing_step_file: str) -> None:
    result = analyze_geometry(missing_step_file)
    assert result.get("error") == "FileNotFound"
    assert missing_step_file.split("/")[-1] in result["step_path"].replace("\\", "/")


def test_suggest_fixes_returns_empty_when_no_findings() -> None:
    result = suggest_fixes([])
    assert result["suggestions"] == []
    assert "clean" in result["note"].lower()


def test_suggest_fixes_ranks_by_severity_and_dedupes_by_check() -> None:
    findings = [
        {"check": "ShortEdges", "severity": "Minor", "detail": "tiny edges", "suggestion": "merge"},
        {"check": "OpenBoundaries", "severity": "Major", "detail": "gaps", "suggestion": "stitch"},
        {"check": "ShortEdges", "severity": "Minor", "detail": "more tiny", "suggestion": "merge"},
        {"check": "DegenerateGeometry", "severity": "Critical", "detail": "bad", "suggestion": "rebuild"},
    ]
    result = suggest_fixes(findings, max_results=10)
    severities = [s["severity"] for s in result["suggestions"]]
    assert severities == ["Critical", "Major", "Minor"]
    checks = [s["check"] for s in result["suggestions"]]
    assert checks.count("ShortEdges") == 1  # deduped
    assert result["total_findings"] == 4
    assert result["returned"] == 3


def test_suggest_fixes_respects_max_results_cap() -> None:
    findings = [
        {"check": f"C{i}", "severity": "Major", "detail": "d", "suggestion": "s"}
        for i in range(10)
    ]
    result = suggest_fixes(findings, max_results=3)
    assert len(result["suggestions"]) == 3


def test_lookup_standard_no_index_returns_no_index_status() -> None:
    result = lookup_standard("mesh quality")
    assert result["status"] == "no_index"
    assert result["query"] == "mesh quality"
    assert result["results"] == []
    assert "scripts/index_fea_docs.py" in result["message"]


def test_lookup_standard_empty_query_short_circuits() -> None:
    result = lookup_standard("   ")
    assert result["status"] == "empty_query"
    assert result["results"] == []


def test_dispatch_tool_routes_to_correct_resolver() -> None:
    result = dispatch_tool("suggest_fixes", json.dumps({"findings": []}))
    assert "suggestions" in result


def test_dispatch_tool_accepts_dict_arguments() -> None:
    result = dispatch_tool("lookup_standard", {"query": "FEA"})
    assert result["query"] == "FEA"
    assert result["status"] in {"ok", "no_index", "empty_query"}


def test_dispatch_tool_unknown_tool_returns_error() -> None:
    result = dispatch_tool("nonexistent", "{}")
    assert result["error"] == "UnknownTool"
    assert "available" in result


def test_dispatch_tool_invalid_json_returns_error() -> None:
    result = dispatch_tool("suggest_fixes", "{not json")
    assert result["error"] == "InvalidArguments"


def test_dispatch_tool_missing_required_arg_returns_error() -> None:
    result = dispatch_tool("suggest_fixes", "{}")
    assert result["error"] == "BadArguments"
