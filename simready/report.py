"""Report generation for SimReady."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from simready.checks import summarize_findings


def determine_status(errors: list[dict[str, Any]], findings: list[dict[str, Any]]) -> str:
    if any(error.get("severity") == "Critical" for error in errors):
        return "InvalidInput"
    if any(finding.get("severity") == "Major" for finding in findings):
        return "NeedsAttention"
    if findings:
        return "ReviewRecommended"
    return "SimulationReady"


def build_report(
    filepath: str,
    validation_result: Any,
    geometry_summary: Any | None,
    findings: list[dict[str, Any]],
    bodies: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if geometry_summary is None:
        geometry = None
    elif is_dataclass(geometry_summary):
        geometry = asdict(geometry_summary)
    else:
        geometry = dict(vars(geometry_summary))
    status = determine_status(validation_result.errors, findings)
    return {
        "input_file": filepath,
        "status": status,
        "summary": summarize_findings(findings),
        "validation": {
            "is_valid": validation_result.is_valid,
            "errors": validation_result.errors,
        },
        "geometry": geometry,
        "findings": findings,
        "bodies": bodies or [],
    }
