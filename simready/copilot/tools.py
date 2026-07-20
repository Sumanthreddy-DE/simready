"""Tool resolvers for the SimReady Copilot.

Four tools exposed to the LLM:
- analyze_geometry: runs the SimReady pipeline on a STEP file.
- suggest_fixes: ranks per-finding fix suggestions by severity.
- lookup_standard: RAG lookup over indexed FEA standards docs.
- build_part: generates a STEP file from a typed parametric spec (simready.gen).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from simready.pipeline import analyze_file_safe
from simready.copilot import rag

logger = logging.getLogger(__name__)

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
    {
        "type": "function",
        "function": {
            "name": "build_part",
            "description": (
                "Generate a new STEP file from a typed parametric spec. Use this when "
                "the user asks you to CREATE a part (not to analyze an existing one). "
                "The spec is a list of ops drawn from a tiny grammar: box(dx, dy, dz, at), "
                "cyl(r, h, at) [axis is +Z], fuse(a, b), cut(a, b). 'a' and 'b' are "
                "0-based indices into earlier steps. The last step is the part returned; "
                "every other step MUST be referenced by a later fuse/cut, so multi-primitive "
                "parts always end with the boolean op that combines them. "
                "After calling this, ALWAYS call analyze_geometry on the returned step_path "
                "to validate it before describing the result to the user."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "spec": {
                        "type": "object",
                        "description": (
                            "Parametric spec. Shape: "
                            "{\"steps\": [{\"op\": \"box\"|\"cyl\"|\"fuse\"|\"cut\", ...}, ...]}. "
                            "Dims are in millimetres. Example for a bracket with a hole: "
                            "{\"steps\": [{\"op\":\"box\",\"dx\":80,\"dy\":60,\"dz\":10},"
                            "{\"op\":\"cyl\",\"r\":5,\"h\":10,\"at\":[40,30,0]},"
                            "{\"op\":\"cut\",\"a\":0,\"b\":1}]}."
                        ),
                    },
                    "timeout_seconds": {
                        "type": "number",
                        "description": "Optional hard wall-clock for the build, in seconds. Default 15.",
                        "default": 15,
                    },
                },
                "required": ["spec"],
            },
        },
    },
]


RENDER_OUT_DIR = Path("data/copilot_renders")
HEALED_STEP_DIR = Path("data/healed_steps")


def analyze_geometry(
    step_path: str,
    timeout_seconds: int = 120,
    findings_limit: int = DEFAULT_FINDINGS_LIMIT,
    render_image: bool = True,
) -> dict[str, Any]:
    """Run SimReady analysis pipeline and return an LLM-friendly summary.

    Per-face score dicts and large ML internals are dropped. Pass `findings_limit=0`
    to keep all findings. When `render_image` is true (default), a static
    colored-face PNG is rendered to ``data/copilot_renders/`` and its path is
    attached as ``image_path`` for the UI to embed. A best-effort healed STEP
    is written to ``data/healed_steps/`` and attached as ``healed_step_path``.
    """
    resolved = Path(step_path).expanduser().resolve()
    if not resolved.exists():
        return {
            "error": "FileNotFound",
            "step_path": str(resolved),
            "message": f"No CAD file at {resolved}.",
        }
    # Subprocess-isolated: a hung OCC C++ call on real CAD gets hard-killed
    # instead of freezing the agent/UI (real_eval.md §3).
    full_report = analyze_file_safe(str(resolved), timeout=timeout_seconds)
    summary = _summarize_report(full_report, str(resolved), findings_limit=findings_limit)
    if render_image:
        png_path = _maybe_render_png(str(resolved), full_report)
        if png_path is not None:
            summary["image_path"] = str(png_path)
    healed_path = _maybe_heal_step(str(resolved), resolved.stem)
    if healed_path is not None:
        summary["healed_step_path"] = str(healed_path)
    return summary


def _maybe_render_png(step_path: str, full_report: dict[str, Any]) -> Path | None:
    """Best-effort PNG render. Returns None silently on any failure."""
    try:
        from simready.copilot.png_render import render_face_score_png
    except ImportError:
        return None
    scores = full_report.get("combined_per_face_scores") or {}
    return render_face_score_png(
        step_path=step_path,
        per_face_scores=scores,
        out_dir=RENDER_OUT_DIR,
    )


def _maybe_heal_step(step_path: str, stem: str) -> Path | None:
    """Best-effort: re-parse STEP with OCC, run ShapeFix, export healed STEP.

    Returns the output path on success, None on any failure (never raises).
    Healed files land in data/healed_steps/<stem>_healed_<ts>.step.
    """
    try:
        from OCC.Core.STEPControl import STEPControl_Reader
        from OCC.Core.IFSelect import IFSelect_RetDone
        from simready.healer import heal_shape
    except ImportError:
        return None
    try:
        reader = STEPControl_Reader()
        status = reader.ReadFile(step_path)
        if status != IFSelect_RetDone:
            return None
        reader.TransferRoots()
        shape = reader.OneShape()
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        out_path = HEALED_STEP_DIR / f"{stem}_healed_{ts}.step"
        result = heal_shape(shape, export_path=str(out_path))
        if result.export_path is None:
            return None
        return Path(result.export_path)
    except Exception:
        logger.debug("_maybe_heal_step failed for %s", step_path, exc_info=True)
        return None


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


def build_part(spec: dict[str, Any], timeout_seconds: float = 15.0) -> dict[str, Any]:
    """Tool entry point for ``geometry-gen``. Delegates to the subprocess-isolated
    executor in ``simready.gen.build``.

    Returns a dict shaped for the LLM's next turn: ``{step_path, schema_valid,
    occ_valid, faces, bbox_mm, ...}`` on success, or ``{schema_valid, occ_valid,
    error}`` on failure. See ``docs/exec-plans/geometry-gen-mvp.md``.
    """
    from simready.gen.build import build_part as _build_part

    return _build_part(spec, timeout_s=float(timeout_seconds))


_DISPATCH = {
    "analyze_geometry": analyze_geometry,
    "suggest_fixes": suggest_fixes,
    "lookup_standard": lookup_standard,
    "build_part": build_part,
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
