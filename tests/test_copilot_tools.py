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
    DEFAULT_FINDINGS_LIMIT,
    SEVERITY_ORDER,
    TOOL_SCHEMAS,
    _summarize_report,
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
    assert names == ["analyze_geometry", "suggest_fixes", "lookup_standard", "build_part"]


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
    assert result["severity_counts"] == {"Critical": 0, "Major": 0, "Minor": 0, "Info": 0}
    assert "clean" in result["note"].lower()


def test_suggest_fixes_includes_severity_counts() -> None:
    findings = [
        {"check": "A", "severity": "Critical"},
        {"check": "B", "severity": "Major"},
        {"check": "C", "severity": "Major"},
        {"check": "D", "severity": "Minor"},
    ]
    result = suggest_fixes(findings, max_results=2)
    assert result["severity_counts"] == {
        "Critical": 1, "Major": 2, "Minor": 1, "Info": 0,
    }
    assert result["total_findings"] == 4
    assert result["returned"] == 2


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


def _fake_pipeline_report() -> dict:
    return {
        "status": "Caution",
        "complexity": "moderate",
        "score": {"overall": 72.5, "label": "Caution"},
        "geometry": {
            "face_count": 148,
            "edge_count": 412,
            "solid_count": 1,
            "bounding_box": [0, 0, 0, 100, 50, 25],
        },
        "bodies": [],
        "findings": [
            {"check": "ShortEdges", "severity": "Minor", "detail": "tiny", "suggestion": "merge"},
            {"check": "OpenBoundaries", "severity": "Major", "detail": "gap", "suggestion": "stitch"},
            {"check": "Degenerate", "severity": "Critical", "detail": "bad", "suggestion": "rebuild"},
            {"check": "Sliver", "severity": "Info", "detail": "ok", "suggestion": "ignore"},
        ],
        "ml": {
            "available": True,
            "weights_loaded": True,
            "score_source": "brepsage",
            "model_name": "BRepSAGE-v1",
            "per_face_scores": {i: 0.5 for i in range(500)},  # must be stripped
        },
        "validation": {"is_valid": True, "errors": []},
        "elapsed_seconds": 1.23,
        "per_face_scores": {i: 0.5 for i in range(500)},  # must be stripped
        "combined_per_face_scores": {i: 0.5 for i in range(500)},  # must be stripped
    }


def test_summarize_report_keeps_top_level_fields_and_strips_per_face_dicts() -> None:
    summary = _summarize_report(_fake_pipeline_report(), "/tmp/x.STEP")
    assert summary["step_path"] == "/tmp/x.STEP"
    assert summary["status"] == "Caution"
    assert summary["complexity"] == "moderate"
    assert summary["score"] == {"overall": 72.5, "label": "Caution"}
    assert summary["geometry"]["face_count"] == 148
    assert summary["body_count"] == 1
    assert summary["findings_total"] == 4
    assert "per_face_scores" not in summary
    assert "per_face_scores" not in summary["ml"]
    assert summary["ml"]["score_source"] == "brepsage"
    assert summary["validation"] == {"is_valid": True, "error_count": 0}


def test_summarize_report_orders_findings_by_severity_and_caps() -> None:
    summary = _summarize_report(_fake_pipeline_report(), "/tmp/x.STEP", findings_limit=2)
    severities = [f["severity"] for f in summary["findings"]]
    assert severities == ["Critical", "Major"]
    assert summary["findings_returned"] == 2
    assert summary["severity_counts"] == {
        "Critical": 1, "Major": 1, "Minor": 1, "Info": 1,
    }


def test_summarize_report_findings_limit_zero_returns_all() -> None:
    summary = _summarize_report(_fake_pipeline_report(), "/tmp/x.STEP", findings_limit=0)
    assert summary["findings_returned"] == 4


def test_analyze_geometry_schema_advertises_findings_limit() -> None:
    schema = next(s for s in TOOL_SCHEMAS if s["function"]["name"] == "analyze_geometry")
    props = schema["function"]["parameters"]["properties"]
    assert "findings_limit" in props
    assert props["findings_limit"]["default"] == DEFAULT_FINDINGS_LIMIT


# ---------------------------------------------------------------------------
# build_part — geometry-gen-mvp wiring
# ---------------------------------------------------------------------------


def test_build_part_schema_advertised_in_tool_list() -> None:
    schema = next(s for s in TOOL_SCHEMAS if s["function"]["name"] == "build_part")
    props = schema["function"]["parameters"]["properties"]
    assert "spec" in props
    assert "timeout_seconds" in props
    assert schema["function"]["parameters"]["required"] == ["spec"]


def test_build_part_dispatch_rejects_malformed_spec_in_parent() -> None:
    # No subprocess spawn should run — the parent-side Pydantic validation
    # returns schema_valid=False without paying spawn cost.
    from simready.copilot.tools import dispatch_tool

    result = dispatch_tool("build_part", {"spec": {"steps": []}})
    assert result.get("schema_valid") is False
    assert "error" in result


occ = pytest.importorskip(
    "OCC.Core.BRepPrimAPI",
    reason="pythonocc-core not available (run under the sr env)",
)


def test_build_part_dispatch_happy_box(tmp_path, monkeypatch) -> None:
    # Redirect the executor's default output dir to a tempdir so the test
    # doesn't litter data/gen_parts/.
    monkeypatch.chdir(tmp_path)
    from simready.copilot.tools import dispatch_tool

    result = dispatch_tool(
        "build_part",
        {"spec": {"steps": [{"op": "box", "dx": 15, "dy": 15, "dz": 15}]}, "timeout_seconds": 60},
    )
    assert result["schema_valid"] is True
    assert result["occ_valid"] is True
    assert result["faces"] == 6
    assert result["step_path"].endswith(".step")
