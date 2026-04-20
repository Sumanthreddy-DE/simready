"""Report generation for SimReady."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any


def determine_status(errors: list[dict[str, Any]], findings: list[dict[str, Any]]) -> str:
    if any(error.get("severity") == "Critical" for error in errors):
        return "InvalidInput"
    if any(finding.get("severity") == "Major" for finding in findings):
        return "NeedsAttention"
    if findings:
        return "ReviewRecommended"
    return "SimulationReady"


def build_report(filepath: str, validation_result: Any, geometry_summary: Any | None, findings: list[dict[str, Any]]) -> dict[str, Any]:
    geometry = asdict(geometry_summary) if geometry_summary is not None else None
    return {
        "input_file": filepath,
        "status": determine_status(validation_result.errors, findings),
        "validation": {
            "is_valid": validation_result.is_valid,
            "errors": validation_result.errors,
        },
        "geometry": geometry,
        "findings": findings,
    }
