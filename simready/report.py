"""Report generation for SimReady."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from typing import Any

from simready.checks import summarize_findings

try:
    from rich.console import Console
    from rich.table import Table
except ImportError:  # pragma: no cover
    Console = None
    Table = None


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
    elapsed_seconds: float | None = None,
) -> dict[str, Any]:
    if geometry_summary is None:
        geometry = None
    elif is_dataclass(geometry_summary):
        geometry = asdict(geometry_summary)
    else:
        geometry = dict(vars(geometry_summary))
    status = determine_status(validation_result.errors, findings)
    report = {
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
    if elapsed_seconds is not None:
        report["elapsed_seconds"] = elapsed_seconds
    return report


def render_terminal_report(report: dict[str, Any], verbose: bool = False) -> str:
    if Console is None or Table is None:
        return json.dumps(report, indent=2)

    console = Console(record=True, width=120)
    score = report.get("score", {})
    status = report.get("status", "")
    color = {"SimulationReady": "green", "ReviewRecommended": "yellow", "NeedsAttention": "dark_orange", "NotReady": "red", "InvalidInput": "red"}.get(status, "white")
    console.print(f"[bold]SimReady Analysis:[/bold] {report.get('input_file', '')}")
    console.print(f"Score: [bold {color}]{score.get('overall', 'n/a')}[/bold {color}]/100  {status}")
    complexity = report.get("complexity", {})
    if complexity:
        console.print(f"Complexity: {complexity.get('label', 'Unknown')} (confidence: {complexity.get('confidence', 'n/a')})")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Category")
    table.add_column("Value")
    table.add_row("Validation", "PASS" if report.get("validation", {}).get("is_valid") else "FAIL")
    geometry = report.get("geometry") or {}
    table.add_row("Faces", str(geometry.get("face_count", "n/a")))
    table.add_row("Edges", str(geometry.get("edge_count", "n/a")))
    table.add_row("Solids", str(geometry.get("solid_count", "n/a")))
    graph = report.get("graph") or {}
    table.add_row("Graph Edges", str(graph.get("edge_count", "n/a")))
    table.add_row("Coedges", str(graph.get("coedge_count", "n/a")))
    table.add_row("Elapsed", str(report.get("elapsed_seconds", "n/a")))
    console.print(table)

    findings = report.get("findings", [])
    if findings:
        console.print("[bold]Top issues:[/bold]")
        for finding in findings[:8]:
            console.print(f"[{finding.get('severity', 'Info')}] {finding.get('check')}: {finding.get('detail')}")
            console.print(f"  -> {finding.get('suggestion')}")
    else:
        console.print("No findings. Clean geometry.")

    ml = report.get("ml") or {}
    if ml.get("available"):
        console.print(f"ML: {ml.get('model_name', 'unknown')} ({ml.get('score_source', 'n/a')})")

    if verbose and report.get("combined_per_face_scores"):
        console.print("[bold]Per-face combined scores:[/bold]")
        for face_index, value in sorted(report["combined_per_face_scores"].items()):
            console.print(f"  Face {face_index}: {value:.3f}")

    return console.export_text()
