"""Tool resolvers for the SimReady Copilot.

Three tools exposed to the LLM:
- analyze_geometry: runs the SimReady pipeline on a STEP file.
- suggest_fixes: ranks per-finding fix suggestions by severity.
- lookup_standard: RAG lookup over FEA standards docs (stubbed in day 1).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from simready.pipeline import analyze_file


SEVERITY_ORDER = {"Critical": 0, "Major": 1, "Minor": 2, "Info": 3}


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "analyze_geometry",
            "description": (
                "Run SimReady's geometry analysis pipeline on a CAD file (STEP/STP). "
                "Returns findings (defects, warnings), per-face scores, complexity tier, "
                "overall manufacturability score, and ML-backed face classifications. "
                "Use this first when the user uploads or references a CAD file."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "step_path": {
                        "type": "string",
                        "description": "Absolute or repo-relative path to a .step / .stp / .STEP file.",
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "description": "Optional analysis timeout. Defaults to 120s.",
                        "default": 120,
                    },
                },
                "required": ["step_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "suggest_fixes",
            "description": (
                "Given a list of findings produced by analyze_geometry, return ranked "
                "text-only fix suggestions sorted by severity (Critical > Major > Minor > Info). "
                "Does NOT modify the part — text suggestions only (L1 modification scope)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "findings": {
                        "type": "array",
                        "description": "List of finding dicts from analyze_geometry.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "check": {"type": "string"},
                                "severity": {"type": "string"},
                                "detail": {"type": "string"},
                                "suggestion": {"type": "string"},
                            },
                        },
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Cap on number of suggestions returned. Default 5.",
                        "default": 5,
                    },
                },
                "required": ["findings"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_standard",
            "description": (
                "Search indexed FEA / mechanical-standards documents (NAFEMS, ASME, etc.) "
                "for a paragraph relevant to the query. Returns top matches with source citation. "
                "STUBBED in day 1; real RAG lands on day 3."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural-language query about FEA / mesh / manufacturing standards.",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of paragraph hits to return. Default 3.",
                        "default": 3,
                    },
                },
                "required": ["query"],
            },
        },
    },
]


def analyze_geometry(step_path: str, timeout_seconds: int = 120) -> dict[str, Any]:
    """Run SimReady analysis pipeline. Returns the full report dict."""
    resolved = Path(step_path).expanduser().resolve()
    if not resolved.exists():
        return {
            "error": "FileNotFound",
            "step_path": str(resolved),
            "message": f"No CAD file at {resolved}.",
        }
    return analyze_file(str(resolved), timeout=timeout_seconds)


def suggest_fixes(findings: list[dict[str, Any]], max_results: int = 5) -> dict[str, Any]:
    """Rank findings by severity, dedupe by check, return top suggestions."""
    if not findings:
        return {"suggestions": [], "note": "No findings to suggest fixes for — part looks clean."}

    seen_checks: set[str] = set()
    ranked: list[dict[str, Any]] = []
    for finding in sorted(findings, key=lambda f: SEVERITY_ORDER.get(f.get("severity", "Info"), 99)):
        check = finding.get("check", "Unknown")
        if check in seen_checks:
            continue
        seen_checks.add(check)
        ranked.append({
            "check": check,
            "severity": finding.get("severity", "Info"),
            "issue": finding.get("detail", ""),
            "fix": finding.get("suggestion", "No suggestion available."),
        })
        if len(ranked) >= max_results:
            break
    return {"suggestions": ranked, "total_findings": len(findings), "returned": len(ranked)}


def lookup_standard(query: str, top_k: int = 3) -> dict[str, Any]:
    """RAG lookup over FEA standards. Day-1 stub returns canned response."""
    return {
        "status": "stub",
        "query": query,
        "results": [
            {
                "source": "PLACEHOLDER",
                "paragraph": (
                    "RAG index not yet built. Day 3 of Path C wk-1 will scrape NAFEMS / ASME "
                    "public docs and index them as JSON + cosine search."
                ),
                "score": 0.0,
            }
        ],
        "top_k_requested": top_k,
    }


_DISPATCH = {
    "analyze_geometry": analyze_geometry,
    "suggest_fixes": suggest_fixes,
    "lookup_standard": lookup_standard,
}


def dispatch_tool(name: str, arguments: str | dict[str, Any]) -> dict[str, Any]:
    """Invoke a tool by name. `arguments` may be a JSON string (from LLM) or a dict."""
    if name not in _DISPATCH:
        return {"error": "UnknownTool", "tool": name, "available": list(_DISPATCH.keys())}

    if isinstance(arguments, str):
        try:
            kwargs = json.loads(arguments) if arguments.strip() else {}
        except json.JSONDecodeError as exc:
            return {"error": "InvalidArguments", "tool": name, "detail": str(exc)}
    else:
        kwargs = arguments or {}

    try:
        result = _DISPATCH[name](**kwargs)
    except TypeError as exc:
        return {"error": "BadArguments", "tool": name, "detail": str(exc)}
    except Exception as exc:  # pragma: no cover — tool internals own their own errors
        return {"error": "ToolException", "tool": name, "detail": str(exc)}
    return result
