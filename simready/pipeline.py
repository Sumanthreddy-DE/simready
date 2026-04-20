"""SimReady end-to-end analysis pipeline."""

from __future__ import annotations

from simready.checks import run_essential_checks
from simready.parser import parse_geometry
from simready.report import build_report
from simready.validator import validate_step_file


def analyze_file(filepath: str) -> dict[str, Any]:
    validation_result = validate_step_file(filepath)
    if not validation_result.is_valid:
        return build_report(filepath, validation_result, None, [])

    geometry_summary = parse_geometry(validation_result.shape)
    findings = run_essential_checks(validation_result.shape, geometry_summary)
    return build_report(filepath, validation_result, geometry_summary, findings)
