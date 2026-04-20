"""SimReady end-to-end analysis pipeline."""

from __future__ import annotations

from typing import Any

from simready.parser import parse_geometry
from simready.report import build_report
from simready.validator import validate_step_file


SHORT_EDGE_RATIO = 0.005


def _compute_dimensions(bounding_box: dict[str, float] | None) -> tuple[float, float, float]:
    if not bounding_box:
        return 0.0, 0.0, 0.0
    return (
        bounding_box["xmax"] - bounding_box["xmin"],
        bounding_box["ymax"] - bounding_box["ymin"],
        bounding_box["zmax"] - bounding_box["zmin"],
    )


def run_checks(geometry_summary: Any) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    if geometry_summary.face_count <= 0 or geometry_summary.edge_count <= 0:
        findings.append(
            {
                "check": "DegenerateGeometry",
                "severity": "Major",
                "detail": "Shape has no faces or edges after parsing.",
                "suggestion": "Inspect the exported geometry for collapsed topology.",
            }
        )

    if geometry_summary.solid_count > 1:
        findings.append(
            {
                "check": "MultiBodyDetected",
                "severity": "Info",
                "detail": f"Detected {geometry_summary.solid_count} solids.",
                "suggestion": "Split and analyze bodies individually in a later phase.",
            }
        )

    dimensions = _compute_dimensions(geometry_summary.bounding_box)
    max_dim = max(dimensions) if dimensions else 0.0
    min_dim = min((d for d in dimensions if d > 0), default=0.0)

    if max_dim > 0 and min_dim > 0 and (min_dim / max_dim) < SHORT_EDGE_RATIO:
        findings.append(
            {
                "check": "ShortEdgeRisk",
                "severity": "Minor",
                "detail": "Model bounding box suggests at least one very small characteristic dimension.",
                "suggestion": "Inspect for short edges or tiny sliver features.",
            }
        )

    return findings


def analyze_file(filepath: str) -> dict[str, Any]:
    validation_result = validate_step_file(filepath)
    if not validation_result.is_valid:
        return build_report(filepath, validation_result, None, [])

    geometry_summary = parse_geometry(validation_result.shape)
    findings = run_checks(geometry_summary)
    return build_report(filepath, validation_result, geometry_summary, findings)
