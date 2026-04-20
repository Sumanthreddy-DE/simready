"""SimReady end-to-end analysis pipeline."""

from __future__ import annotations

from typing import Any

from simready.checks import run_essential_checks, summarize_findings
from simready.healer import heal_shape
from simready.parser import parse_geometry
from simready.report import build_report
from simready.splitter import split_bodies
from simready.validator import validate_step_file


def _body_report(shape: Any, index: int) -> dict[str, Any]:
    heal_result = heal_shape(shape)
    geometry_summary = parse_geometry(heal_result.healed_shape)
    findings = run_essential_checks(heal_result.healed_shape, geometry_summary)
    status = "NeedsAttention" if any(f.get("severity") == "Major" for f in findings) else ("ReviewRecommended" if findings else "SimulationReady")
    return {
        "body_index": index,
        "status": status,
        "summary": summarize_findings(findings),
        "heal": heal_result.summary,
        "geometry": {
            "face_count": geometry_summary.face_count,
            "edge_count": geometry_summary.edge_count,
            "solid_count": geometry_summary.solid_count,
            "bounding_box": geometry_summary.bounding_box,
        },
        "findings": findings,
    }


def analyze_file(filepath: str, export_healed_path: str | None = None) -> dict[str, Any]:
    validation_result = validate_step_file(filepath)
    if not validation_result.is_valid:
        return build_report(filepath, validation_result, None, [], bodies=[])

    heal_result = heal_shape(validation_result.shape, export_path=export_healed_path)
    geometry_summary = parse_geometry(heal_result.healed_shape)
    findings = run_essential_checks(heal_result.healed_shape, geometry_summary)

    split = split_bodies(heal_result.healed_shape)
    body_reports: list[dict[str, Any]] = []
    if split.body_count > 1:
        body_reports = [_body_report(body_shape, idx + 1) for idx, body_shape in enumerate(split.bodies)]

    report = build_report(filepath, validation_result, geometry_summary, findings, bodies=body_reports)
    report["heal"] = heal_result.summary
    if heal_result.export_path:
        report["healed_export"] = heal_result.export_path
    return report
