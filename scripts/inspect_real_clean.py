#!/usr/bin/env python3
"""Inspect real STEP files and record evidence, never clean-label eligibility."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import multiprocessing as mp
import sys
import time
from pathlib import Path

from simready.checks import (
    SELF_INTERSECTION_FACE_LIMIT,
    SELF_INTERSECTION_FREEFORM_LIMIT,
    _count_freeform_faces,
    THIN_SOLID_ASPECT_RATIO,
)
from simready.ml.graph_extractor import extract_brep_graph
from simready.parser import parse_geometry
from simready.validator import validate_step_file

try:
    from OCC.Core.BOPAlgo import BOPAlgo_ArgumentAnalyzer
except ImportError:  # pragma: no cover
    BOPAlgo_ArgumentAnalyzer = None


DEFAULT_TIMEOUT_SECONDS = 60.0
INSPECTION_CHECKS = (
    "OpenBoundaries",
    "PotentialGaps",
    "SelfIntersection",
    "SelfIntersectionSkipped",
    "SelfIntersectionTimeout",
    "ThinSolid",
)
UNKNOWN_INSPECTION = {
    "open_shell": "unknown",
    "sliver_face": "unknown",
    "self_intersection": "unknown",
}


def iter_step_files(input_dir: Path):
    """Yield direct-child STEP paths, deduplicated case-insensitively."""
    seen: set[str] = set()
    for path in sorted(input_dir.iterdir(), key=lambda item: item.name.lower()):
        if not path.is_file() or path.suffix.lower() not in {".step", ".stp"}:
            continue
        key = str(path.resolve()).casefold()
        if key not in seen:
            seen.add(key)
            yield path


def source_sha256(path: Path) -> str:
    """Hash the source bytes, not parsed or regenerated geometry."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _new_record(step_path: Path, sha256: str) -> dict:
    return {
        "source_id": step_path.stem,
        "file": step_path.name,
        "source_sha256": sha256,
        "status": "not_inspected",
        "inspection": dict(UNKNOWN_INSPECTION),
        "completion": {name: False for name in INSPECTION_CHECKS if name not in {"SelfIntersectionSkipped", "SelfIntersectionTimeout"}},
        "findings": {name: [] for name in INSPECTION_CHECKS},
        "errors": [],
    }


def _error_text(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"


def _build_open_topology(shape) -> tuple[int, int, list[dict]]:
    """Count boundary and nonmanifold edges; returning proves traversal completed."""
    from OCC.Core.BRep import BRep_Tool
    from simready.occ_utils import build_edge_face_map

    edge_face_map = build_edge_face_map(shape)
    if edge_face_map is None:
        raise RuntimeError("open topology map unavailable or failed")
    boundary_edges = 0
    nonmanifold_edges = 0
    for index in range(1, edge_face_map.Size() + 1):
        edge = edge_face_map.FindKey(index)
        face_count = edge_face_map.FindFromIndex(index).Size()
        if not BRep_Tool.Degenerated(edge) and face_count != 2:
            if face_count < 2:
                boundary_edges += 1
            else:
                nonmanifold_edges += 1
    findings = []
    if boundary_edges:
        findings.append({
            "check": "OpenBoundaries",
            "severity": "Major",
            "detail": f"Inspection topology map found {boundary_edges} non-degenerate boundary edges with fewer than two face ancestors.",
        })
    if nonmanifold_edges:
        findings.append({
            "check": "OpenBoundaries",
            "severity": "Major",
            "detail": f"Inspection topology map found {nonmanifold_edges} non-degenerate non-manifold edges with more than two face ancestors.",
        })
    return boundary_edges, nonmanifold_edges, findings


def _find_potential_gaps(shape) -> list[dict]:
    from OCC.Core.ShapeAnalysis import ShapeAnalysis_Shell
    from OCC.Core.TopAbs import TopAbs_FACE
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopoDS import topods

    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    has_gaps = False
    while explorer.More():
        face = topods.Face(explorer.Current())
        if ShapeAnalysis_Shell().CheckOrientedShells(face, True):
            has_gaps = True
        explorer.Next()
    return [] if not has_gaps else [{
        "check": "PotentialGaps",
        "severity": "Major",
        "detail": "Inspection shell orientation analysis suggests open or inconsistent boundaries.",
    }]


def inspect_open_topology(shape, summary=None) -> dict:
    """Direct topology evidence; no absent result is inferred from empty findings."""
    if summary is None:
        summary = parse_geometry(shape)
    evidence = {"result": "unknown", "completion": {"OpenBoundaries": False, "PotentialGaps": False}, "findings": [], "errors": []}
    try:
        boundary_edges, nonmanifold_edges, findings = _build_open_topology(shape)
        evidence["findings"].extend(findings)
        evidence["completion"]["OpenBoundaries"] = True
        evidence["open_edge_count"] = boundary_edges + nonmanifold_edges
        evidence["boundary_edge_count"] = boundary_edges
        evidence["nonmanifold_edge_count"] = nonmanifold_edges
        if summary.solid_count == 0 and summary.face_count > 0:
            evidence["findings"].append({
                "check": "OpenBoundaries",
                "severity": "Major",
                "detail": "Geometry contains faces but no closed solid volume.",
            })
            evidence["result"] = "present"
        elif boundary_edges or nonmanifold_edges:
            evidence["result"] = "present"
    except Exception as exc:
        evidence["errors"].append(f"OpenBoundaries: {_error_text(exc)}")

    if evidence["completion"]["OpenBoundaries"]:
        try:
            gap_findings = _find_potential_gaps(shape)
            evidence["findings"].extend(gap_findings)
            evidence["completion"]["PotentialGaps"] = True
            if gap_findings:
                evidence["result"] = "present"
            elif evidence["result"] == "unknown":
                evidence["result"] = "absent"
        except Exception as exc:
            evidence["result"] = "unknown"
            evidence["errors"].append(f"PotentialGaps: {_error_text(exc)}")
    if len(evidence["errors"]) == 1:
        evidence["error"] = evidence["errors"][0]
    return evidence


def inspect_self_intersection(shape, face_count: int) -> dict:
    """Run guarded BOPAlgo directly; successful Perform alone proves completion."""
    evidence = {"result": "unknown", "completion": {"SelfIntersection": False}, "findings": [], "errors": []}
    if BOPAlgo_ArgumentAnalyzer is None:
        evidence["error"] = "SelfIntersection: BOPAlgo_ArgumentAnalyzer unavailable"
        evidence["errors"].append(evidence["error"])
        return evidence
    try:
        freeform_count = _count_freeform_faces(shape)
    except Exception as exc:
        evidence["error"] = f"SelfIntersection: freeform inspection failed: {_error_text(exc)}"
        evidence["errors"].append(evidence["error"])
        return evidence
    if face_count > SELF_INTERSECTION_FACE_LIMIT or freeform_count > SELF_INTERSECTION_FREEFORM_LIMIT:
        reason = f"face_count={face_count}, freeform_count={freeform_count}"
        evidence["findings"].append({"check": "SelfIntersectionSkipped", "detail": f"Guarded inspection skipped: {reason}."})
        evidence["error"] = f"SelfIntersection: inconclusive ({reason})"
        evidence["errors"].append(evidence["error"])
        return evidence
    try:
        analyzer = BOPAlgo_ArgumentAnalyzer()
        analyzer.SetShape1(shape)
        analyzer.SetSelfInterMode(True)
        analyzer.SetArgumentTypeMode(False)
        analyzer.SetSmallEdgeMode(False)
        analyzer.SetRebuildFaceMode(False)
        analyzer.SetTangentMode(False)
        analyzer.SetMergeVertexMode(False)
        analyzer.SetMergeEdgeMode(False)
        analyzer.SetContinuityMode(False)
        analyzer.SetCurveOnSurfaceMode(False)
        analyzer.Perform()
        has_faulty = bool(analyzer.HasFaulty())
        evidence["completion"]["SelfIntersection"] = True
        evidence["result"] = "present" if has_faulty else "absent"
        if has_faulty:
            evidence["findings"].append({"check": "SelfIntersection", "severity": "Major", "detail": "Completed BOPAlgo analyzer reported self-interfering faces or edges."})
    except Exception as exc:
        evidence["error"] = f"SelfIntersection: {_error_text(exc)}"
        evidence["errors"].append(evidence["error"])
    return evidence


def _thin_solid_solid_count(shape) -> int:
    from OCC.Core.TopAbs import TopAbs_SOLID
    from OCC.Core.TopExp import TopExp_Explorer

    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    count = 0
    while explorer.More():
        count += 1
        explorer.Next()
    return count


def _checked_thin_solid_findings(shape) -> tuple[list[dict], int, list[str]]:
    """Evaluate every discovered solid; unlike the general check, never skip failures."""
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib
    from OCC.Core.TopAbs import TopAbs_SOLID
    from OCC.Core.TopExp import TopExp_Explorer

    sliver_count = 0
    evaluated_count = 0
    worst_ratio = 0.0
    errors = []
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    while explorer.More():
        solid = explorer.Current()
        try:
            box = Bnd_Box()
            brepbndlib.Add(solid, box)
            if box.IsVoid():
                raise ValueError("bounding box is void")
            xmin, ymin, zmin, xmax, ymax, zmax = box.Get()
            dimensions = [xmax - xmin, ymax - ymin, zmax - zmin]
            nonzero = [dimension for dimension in dimensions if dimension > 0]
            if len(nonzero) != 3:
                raise ValueError(f"degenerate bounding box dimensions: {dimensions!r}")
            ratio = max(nonzero) / min(nonzero)
            if ratio >= THIN_SOLID_ASPECT_RATIO:
                sliver_count += 1
                worst_ratio = max(worst_ratio, ratio)
            evaluated_count += 1
        except Exception as exc:
            errors.append(f"solid {evaluated_count + len(errors)}: {_error_text(exc)}")
        explorer.Next()
    findings = [] if sliver_count == 0 else [{
        "check": "ThinSolid",
        "severity": "Major",
        "detail": (
            f"Detected {sliver_count} sliver-shaped solid(s); worst aspect "
            f"ratio {worst_ratio:.0f}:1 (threshold {THIN_SOLID_ASPECT_RATIO:.0f}:1)."
        ),
        "suggestion": "Remove or thicken the sliver body — its aspect ratio will force pathological mesh element shapes.",
    }]
    return findings, evaluated_count, errors


def inspect_sliver_class(shape, geometry_summary) -> dict:
    """Class-specific thin-sibling-solid evidence, not general sliver certification."""
    evidence = {
        "result": "unknown",
        "completed": False,
        "completion": {"ThinSolid": False},
        "findings": [],
        "errors": [],
        "solid_count": geometry_summary.solid_count,
        "evaluated_solid_count": 0,
        "evidence_scope": "class_specific_thin_solid_not_general_sliver_certificate",
    }
    try:
        solid_count = _thin_solid_solid_count(shape)
        if solid_count != geometry_summary.solid_count:
            raise ValueError(f"solid traversal found {solid_count}, summary declares {geometry_summary.solid_count}")
        findings, evaluated_count, errors = _checked_thin_solid_findings(shape)
        evidence["evaluated_solid_count"] = evaluated_count
        if errors:
            raise RuntimeError("; ".join(errors))
        if evaluated_count != solid_count:
            raise ValueError(f"evaluated {evaluated_count} of {solid_count} solids")
        evidence["findings"] = findings
        evidence["completed"] = True
        evidence["completion"]["ThinSolid"] = True
        evidence["result"] = "present" if findings else "absent"
    except Exception as exc:
        evidence["error"] = f"ThinSolid: {_error_text(exc)}"
        evidence["errors"].append(evidence["error"])
    return evidence


def _apply_evidence(record: dict, defect: str, evidence: dict) -> None:
    record["inspection"][defect] = evidence["result"]
    if "completed" in evidence:
        record[f"{defect}_completed"] = evidence["completed"]
    if "evidence_scope" in evidence:
        record[f"{defect}_evidence_scope"] = evidence["evidence_scope"]
    record["completion"].update(evidence["completion"])
    for field in ("open_edge_count", "boundary_edge_count", "nonmanifold_edge_count", "solid_count", "evaluated_solid_count"):
        if field in evidence:
            record[field] = evidence[field]
    for finding in evidence["findings"]:
        name = finding.get("check")
        if name in INSPECTION_CHECKS:
            record["findings"][name].append(finding)
    record["errors"].extend(evidence["errors"])


def inspect_one(step_path: Path, sha256: str | None = None) -> dict:
    """Run load, BRep validation, selected checks and graph extraction in-process."""
    record = _new_record(step_path, sha256 or source_sha256(step_path))
    try:
        validation = validate_step_file(str(step_path))
        record["validation"] = {"status": "ok" if validation.is_valid else "error", "errors": validation.errors}
        if not validation.is_valid:
            record["status"] = "validation_error"
            return record
        summary = parse_geometry(validation.shape)
        record["face_count"] = summary.face_count
        record["geometry"] = {"face_count": summary.face_count, "edge_count": summary.edge_count, "solid_count": summary.solid_count}

        _apply_evidence(record, "open_shell", inspect_open_topology(validation.shape, summary))
        _apply_evidence(record, "self_intersection", inspect_self_intersection(validation.shape, summary.face_count))
        _apply_evidence(record, "sliver_face", inspect_sliver_class(validation.shape, summary))

        try:
            graph = extract_brep_graph(validation.shape)
            if not graph.node_features:
                raise ValueError("graph extraction returned no node_features")
            record["graph_extraction"] = {"status": "ok", "face_count": len(graph.node_features)}
        except Exception as exc:
            record["graph_extraction"] = {"status": "error", "error": _error_text(exc)}
            record["errors"].append(f"graph_extraction: {_error_text(exc)}")

        record["status"] = "graph_error" if record["graph_extraction"]["status"] == "error" else "ok"
        if any(error.startswith(("OpenBoundaries:", "PotentialGaps:", "ThinSolid:")) for error in record["errors"]):
            record["status"] = "inspection_error"
        return record
    except Exception as exc:
        record["status"] = "inspection_error"
        record["errors"].append(_error_text(exc))
        return record


def _inspection_worker(step_path_str: str, sha256: str, queue) -> None:
    """Spawn entry point; the parent can terminate a stuck OCC C++ call."""
    try:
        queue.put(inspect_one(Path(step_path_str), sha256))
    except BaseException as exc:
        queue.put({"status": "process_error", "errors": [_error_text(exc)]})


def _validate_timeout(timeout_s: float) -> float:
    if isinstance(timeout_s, bool):
        raise ValueError("timeout must be positive and finite")
    try:
        value = float(timeout_s)
    except (TypeError, ValueError):
        raise ValueError("timeout must be positive and finite") from None
    if not math.isfinite(value) or value <= 0:
        raise ValueError("timeout must be positive and finite")
    return value


def run_spawn_worker(target, args: tuple, timeout_s: float, result_timeout_s: float = 2.0) -> dict:
    """Run a pickleable worker with hard timeout and unconditional queue cleanup."""
    timeout_s = _validate_timeout(timeout_s)
    context = mp.get_context("spawn")
    queue = context.Queue()
    process = context.Process(target=target, args=(*args, queue))
    outcome: dict = {"kind": "process_error", "error": "worker did not start", "process": {}}
    try:
        process.start()
        deadline = time.monotonic() + timeout_s
        # Drain before join: a child cannot exit while its feeder flushes a large payload.
        payload = None
        payload_received = False
        queue_error = None
        while not payload_received and time.monotonic() < deadline:
            try:
                payload = queue.get(timeout=min(result_timeout_s, max(0, deadline - time.monotonic())))
                payload_received = True
            except Exception as exc:
                queue_error = exc
                if not process.is_alive():
                    break
        process.join(max(0, deadline - time.monotonic()))
        process_record = {"exit_code": process.exitcode, "terminated": False}
        if process.is_alive():
            process.terminate()
            process.join(5)
            if process.is_alive():
                process.kill()
                process.join(5)
            process_record["terminated"] = True
            if process.is_alive():
                process_record["alive_after_kill"] = True
                outcome = {"kind": "process_error", "error": "worker remains alive after terminate and kill", "process": process_record}
            else:
                outcome = {"kind": "timeout", "error": f"worker_timeout (>{timeout_s:g}s)", "process": process_record}
        elif payload_received:
            outcome = {"kind": "result", "payload": payload, "process": process_record}
        else:
            outcome = {"kind": "process_error", "error": f"no_result_from_worker: {_error_text(queue_error)}", "process": process_record}
        return outcome
    except Exception as exc:
        outcome["kind"] = "process_error"
        outcome["error"] = _error_text(exc)
        return outcome
    finally:
        try:
            queue.close()
            queue.join_thread()
        except Exception:
            pass


def inspect_one_in_subprocess(step_path: Path, timeout_s: float = DEFAULT_TIMEOUT_SECONDS) -> dict:
    """Inspect one source with a hard wall-clock bound and explicit process errors."""
    timeout_s = _validate_timeout(timeout_s)
    sha256 = source_sha256(step_path)
    outcome = run_spawn_worker(_inspection_worker, (str(step_path), sha256), timeout_s)
    if outcome["kind"] == "result" and isinstance(outcome["payload"], dict) and "source_id" in outcome["payload"]:
        record = outcome["payload"]
    else:
        record = _new_record(step_path, sha256)
        record["status"] = "timeout" if outcome["kind"] == "timeout" else "process_error"
        record["errors"].append(outcome["error"])
    record["process"] = outcome["process"]
    return record


def _positive_finite_timeout(value: str) -> float:
    try:
        return _validate_timeout(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("tests/data/real_eval"))
    parser.add_argument("--output", type=Path, default=Path("data/real_clean_v1/inspection.json"))
    parser.add_argument("--timeout", type=_positive_finite_timeout, default=DEFAULT_TIMEOUT_SECONDS)
    args = parser.parse_args(argv)
    if not args.input.is_dir():
        print(f"Input dir {args.input} missing.", file=sys.stderr)
        return 1
    steps = list(iter_step_files(args.input))
    if not steps:
        print(f"No STEP files in {args.input}.", file=sys.stderr)
        return 1
    records = []
    for index, step in enumerate(steps, 1):
        print(f"[inspect {index}/{len(steps)}] {step.name}", flush=True)
        try:
            record = inspect_one_in_subprocess(step, args.timeout)
        except Exception as exc:
            record = _new_record(step, source_sha256(step))
            record["status"] = "process_error"
            record["errors"].append(_error_text(exc))
        records.append(record)
        print(f"    -> status={record['status']} inspection={record['inspection']}", flush=True)
    evidence = {
        "schema_version": "real_clean_inspection_v1",
        "purpose": "evidence_only_not_training_eligibility",
        "input_dir": str(args.input),
        "timeout_seconds": args.timeout,
        "sliver_evidence": "class_specific_thin_solid_not_general_sliver_certificate",
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(f"Wrote {args.output} ({len(records)} evidence records)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
