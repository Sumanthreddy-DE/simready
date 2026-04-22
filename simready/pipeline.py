"""SimReady end-to-end analysis pipeline."""

from __future__ import annotations

import time
from types import SimpleNamespace
from typing import Any

from simready.checks import run_essential_checks_detailed, summarize_findings
from simready.healer import heal_shape
from simready.parser import parse_geometry
from simready.report import build_report
from simready.splitter import split_bodies
from simready.validator import validate_brep, validate_file_load


def _body_report(shape: Any, index: int, heal_summary: dict[str, Any] | None = None) -> dict[str, Any]:
    geometry_summary = parse_geometry(shape)
    check_result = run_essential_checks_detailed(shape, geometry_summary)
    findings = check_result.findings
    status = "NeedsAttention" if any(f.get("severity") == "Major" for f in findings) else ("ReviewRecommended" if findings else "SimulationReady")
    return {
        "body_index": index,
        "status": status,
        "summary": summarize_findings(findings),
        "heal": heal_summary or {
            "attempted": False,
            "applied": False,
            "valid_before": None,
            "valid_after": None,
            "notes": ["Body reused top-level healed geometry without per-body re-healing."],
        },
        "geometry": {
            "face_count": geometry_summary.face_count,
            "edge_count": geometry_summary.edge_count,
            "solid_count": geometry_summary.solid_count,
            "bounding_box": geometry_summary.bounding_box,
        },
        "findings": findings,
        "per_face_scores": check_result.per_face,
    }


def analyze_file(filepath: str, export_healed_path: str | None = None) -> dict[str, Any]:
    started = time.perf_counter()

    load_result = validate_file_load(filepath)
    if not load_result.is_valid:
        report = build_report(
            filepath,
            SimpleNamespace(is_valid=False, errors=load_result.errors),
            None,
            [],
            bodies=[],
            elapsed_seconds=time.perf_counter() - started,
        )
        return report

    working_shape = load_result.shape
    initial_validation = validate_brep(working_shape)
    heal_result = None
    final_validation = initial_validation

    if not initial_validation.is_valid:
        heal_result = heal_shape(working_shape, export_path=export_healed_path)
        working_shape = heal_result.healed_shape
        final_validation = validate_brep(working_shape)
        if not final_validation.is_valid:
            report = build_report(
                filepath,
                final_validation,
                None,
                [],
                bodies=[],
                elapsed_seconds=time.perf_counter() - started,
            )
            report["heal"] = heal_result.summary
            if heal_result.export_path:
                report["healed_export"] = heal_result.export_path
            return report
    else:
        heal_result = heal_shape(working_shape, export_path=export_healed_path)
        working_shape = heal_result.healed_shape
        final_validation = validate_brep(working_shape)

    geometry_summary = parse_geometry(working_shape)
    check_result = run_essential_checks_detailed(working_shape, geometry_summary)
    findings = check_result.findings

    split = split_bodies(working_shape)
    body_reports: list[dict[str, Any]] = []
    if split.body_count > 1:
        body_reports = [
            _body_report(
                body_shape,
                idx + 1,
                {
                    "attempted": False,
                    "applied": False,
                    "valid_before": heal_result.summary.get("valid_after") if heal_result else None,
                    "valid_after": heal_result.summary.get("valid_after") if heal_result else None,
                    "notes": ["Top-level healed geometry reused; per-body healing intentionally skipped."],
                },
            )
            for idx, body_shape in enumerate(split.bodies)
        ]

    report = build_report(
        filepath,
        final_validation,
        geometry_summary,
        findings,
        bodies=body_reports,
        elapsed_seconds=time.perf_counter() - started,
    )
    report["per_face_scores"] = check_result.per_face
    if heal_result is not None:
        report["heal"] = heal_result.summary
        if not initial_validation.is_valid:
            report["validation"]["initial_errors"] = initial_validation.errors
            report["validation"]["healed_after_validation_failure"] = final_validation.is_valid
    if heal_result and heal_result.export_path:
        report["healed_export"] = heal_result.export_path
    return report
