"""SimReady end-to-end analysis pipeline."""

from __future__ import annotations

import time
from types import SimpleNamespace
from typing import Any

from simready.checks import run_essential_checks_detailed, summarize_findings
from simready.healer import heal_shape
from simready.ml.brepnet import run_brepnet_inference
from simready.ml.combiner import score_label, score_report
from simready.ml.graph_extractor import extract_brep_graph
from simready.parser import parse_geometry
from simready.report import build_report
from simready.splitter import split_bodies
from simready.validator import validate_brep, validate_file_load


def _body_report(shape: Any, index: int, heal_summary: dict[str, Any] | None = None) -> dict[str, Any]:
    geometry_summary = parse_geometry(shape)
    check_result = run_essential_checks_detailed(shape, geometry_summary)
    findings = check_result.findings
    graph = extract_brep_graph(shape)
    ml_result = run_brepnet_inference(graph)
    fusion = score_report(findings, check_result.per_face, ml_result.per_face_scores, ml_available=ml_result.weights_loaded)
    status = score_label(fusion.overall_score)
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
        "ml": {
            "available": ml_result.available,
            "weights_loaded": ml_result.weights_loaded,
            "weights_path": ml_result.weights_path,
            "model_name": ml_result.model_name,
            "score_source": ml_result.score_source,
            "aggregate_score": ml_result.aggregate_score,
            "notes": ml_result.notes,
        },
        "graph": {
            "face_count": graph.metadata.get("face_count", 0),
            "edge_count": graph.metadata.get("edge_count", 0),
            "coedge_count": graph.metadata.get("coedge_count", 0),
            "adjacency_count": graph.metadata.get("adjacency_count", 0),
            "extractor": graph.metadata.get("extractor"),
        },
        "score": {
            "overall": fusion.overall_score,
            "label": status,
            "body_combined_mean": fusion.body_score,
            "ml_penalty_applied": fusion.ml_penalty_applied,
            "ml_penalty_points": fusion.ml_penalty_points,
        },
        "combined_per_face_scores": fusion.combined_per_face,
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
    graph = extract_brep_graph(working_shape)
    ml_result = run_brepnet_inference(graph)
    fusion = score_report(findings, check_result.per_face, ml_result.per_face_scores, ml_available=ml_result.weights_loaded)

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
    report["status"] = score_label(fusion.overall_score)
    report["per_face_scores"] = check_result.per_face
    report["combined_per_face_scores"] = fusion.combined_per_face
    report["score"] = {
        "overall": fusion.overall_score,
        "label": score_label(fusion.overall_score),
        "rule_face_mean": fusion.breakdown.get("rule_face_count", 0),
        "combined_face_mean": fusion.body_score,
        "ml_penalty_applied": fusion.ml_penalty_applied,
        "ml_penalty_points": fusion.ml_penalty_points,
    }
    report["ml"] = {
        "available": ml_result.available,
        "weights_loaded": ml_result.weights_loaded,
        "weights_path": ml_result.weights_path,
        "model_name": ml_result.model_name,
        "score_source": ml_result.score_source,
        "aggregate_score": ml_result.aggregate_score,
        "notes": ml_result.notes,
    }
    report["graph"] = {
        "face_count": graph.metadata.get("face_count", 0),
        "edge_count": graph.metadata.get("edge_count", 0),
        "coedge_count": graph.metadata.get("coedge_count", 0),
        "adjacency_count": graph.metadata.get("adjacency_count", 0),
        "extractor": graph.metadata.get("extractor"),
    }
    if heal_result is not None:
        report["heal"] = heal_result.summary
        if not initial_validation.is_valid:
            report["validation"]["initial_errors"] = initial_validation.errors
            report["validation"]["healed_after_validation_failure"] = final_validation.is_valid
    if heal_result and heal_result.export_path:
        report["healed_export"] = heal_result.export_path
    return report
