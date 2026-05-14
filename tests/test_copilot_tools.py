"""Tests for the SimReady Copilot tool resolvers.

Day 1 scope: tool dispatch correctness, error paths, schema validity.
Live API calls are NOT exercised here — see test_copilot_agent.py for that.
"""

from __future__ import annotations

import json

import pytest

from simready.copilot.tools import (
    SEVERITY_ORDER,
    TOOL_SCHEMAS,
    analyze_geometry,
    dispatch_tool,
    lookup_standard,
    suggest_fixes,
)


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


def test_lookup_standard_returns_stub_marker() -> None:
    result = lookup_standard("mesh quality")
    assert result["status"] == "stub"
    assert result["results"][0]["source"] == "PLACEHOLDER"
    assert result["query"] == "mesh quality"


def test_dispatch_tool_routes_to_correct_resolver() -> None:
    result = dispatch_tool("suggest_fixes", json.dumps({"findings": []}))
    assert "suggestions" in result


def test_dispatch_tool_accepts_dict_arguments() -> None:
    result = dispatch_tool("lookup_standard", {"query": "FEA"})
    assert result["status"] == "stub"


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
