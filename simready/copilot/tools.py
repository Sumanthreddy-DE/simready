"""Tool resolvers for the SimReady Copilot.

Three tools exposed to the LLM:
- analyze_geometry: runs the SimReady pipeline on a STEP file.
- suggest_fixes: ranks per-finding fix suggestions by severity.
- lookup_standard: RAG lookup over indexed FEA standards docs.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from simready.pipeline import analyze_file
from simready.copilot import rag


SEVERITY_ORDER = {"Critical": 0, "Major": 1, "Minor": 2, "Info": 3}
DEFAULT_FINDINGS_LIMIT = 12


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "analyze_geometry",
            "description": (
                "Run SimReady's geometry analysis pipeline on a CAD file (STEP/STP) and "
                "return a structured summary: status, complexity tier, score, geometry "
                "metrics, body count, and the top findings ranked by severity. Designed "
                "for the LLM — per-face score dicts and large internals are stripped. "
                "Use this first whenever the user references a CAD file."
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
                    "findings_limit": {
                        "type": "integer",
                        "description": (
                            f"Cap on findings returned (sorted by severity). Default {DEFAULT_FINDINGS_LIMIT}."
                        ),
                        "default": DEFAULT_FINDINGS_LIMIT,
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
                "Search indexed FEA / mechanical-standards documents (NAFEMS, ASME, vendor "
                "whitepapers) for paragraphs relevant to the query. Returns top matches with "
                "source citation (file name + page number). Backed by sentence-transformers "
                "embeddings + cosine similarity over a JSON index."
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


def analyze_geometry(
    step_path: str,
    timeout_seconds: int = 120,
    findings_limit: int = DEFAULT_FINDINGS_LIMIT,
) -> dict[str, Any]:
    """Run SimReady analysis pipeline and return an LLM-friendly summary.

    Per-face score dicts and large ML internals are dropped. Pass `findings_limit=0`
    to keep all findings.
    """
    resolved = Path(step_path).expanduser().resolve()
    if not resolved.exists():
        return {
            "error": "FileNotFound",
            "step_path": str(resolved),
            "message": f"No CAD file at {resolved}.",
        }
    full_report = analyze_file(str(resolved), timeout=timeout_seconds)
    return _summarize_report(full_report, str(resolved), findings_limit=findings_limit)


def _severity_counts(findings: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {k: 0 for k in SEVERITY_ORDER}
    for f in findings:
        sev = f.get("severity", "Info")
        counts[sev] = counts.get(sev, 0) + 1
    return counts


def _summarize_report(
    report: dict[str, Any],
    step_path: str,
    findings_limit: int = DEFAULT_FINDINGS_LIMIT,
) -> dict[str, Any]:
    """Produce a slim, structured view of an analyze_file report for the LLM."""
    findings = list(report.get("findings", []) or [])
    sorted_findings = sorted(
        findings, key=lambda f: SEVERITY_ORDER.get(f.get("severity", "Info"), 99)
    )
    capped = sorted_findings if findings_limit <= 0 else sorted_findings[:findings_limit]
    score = report.get("score", {}) or {}
    geometry = report.get("geometry", {}) or {}
    ml = report.get("ml", {}) or {}
    bodies = report.get("bodies", []) or []
    summary: dict[str, Any] = {
        "step_path": step_path,
        "status": report.get("status"),
        "complexity": report.get("complexity"),
        "score": {
            "overall": score.get("overall"),
            "label": score.get("label"),
        },
        "geometry": {
            "face_count": geometry.get("face_count"),
            "edge_count": geometry.get("edge_count"),
            "solid_count": geometry.get("solid_count"),
            "bounding_box": geometry.get("bounding_box"),
        },
        "body_count": len(bodies) or 1,
        "findings_total": len(findings),
        "findings_returned": len(capped),
        "severity_counts": _severity_counts(findings),
        "findings": [
            {
                "check": f.get("check"),
                "severity": f.get("severity"),
                "detail": f.get("detail"),
                "suggestion": f.get("suggestion"),
            }
            for f in capped
        ],
        "ml": {
            "available": ml.get("available"),
            "weights_loaded": ml.get("weights_loaded"),
            "score_source": ml.get("score_source"),
            "model_name": ml.get("model_name"),
        },
        "elapsed_seconds": report.get("elapsed_seconds"),
    }
    if "validation" in report:
        validation = report["validation"]
        summary["validation"] = {
            "is_valid": validation.get("is_valid"),
            "error_count": len(validation.get("errors", []) or []),
        }
    return summary


def suggest_fixes(findings: list[dict[str, Any]], max_results: int = 5) -> dict[str, Any]:
    """Rank findings by severity, dedupe by check, return top suggestions w/ counts."""
    counts = _severity_counts(findings)
    if not findings:
        return {
            "suggestions": [],
            "severity_counts": counts,
            "total_findings": 0,
            "returned": 0,
            "note": "No findings to suggest fixes for — part looks clean.",
        }

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
    return {
        "suggestions": ranked,
        "severity_counts": counts,
        "total_findings": len(findings),
        "returned": len(ranked),
    }


def lookup_standard(query: str, top_k: int = 3) -> dict[str, Any]:
    """RAG lookup over FEA standards. Returns top-k cosine matches with citations."""
    if not query or not query.strip():
        return {
            "status": "empty_query",
            "query": query,
            "results": [],
            "top_k_requested": top_k,
        }
    try:
        index = rag.get_default_index()
    except FileNotFoundError as exc:
        return {
            "status": "no_index",
            "query": query,
            "results": [],
            "top_k_requested": top_k,
            "message": (
                f"{exc}. Build it with: "
                "python scripts/scrape_fea_docs.py && python scripts/index_fea_docs.py"
            ),
        }
    embedder = rag.get_default_embedder()
    matches = index.search(query, embedder=embedder, top_k=top_k)
    return {
        "status": "ok",
        "query": query,
        "results": matches,
        "top_k_requested": top_k,
        "index_meta": index.meta,
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
