"""Deterministic correctness checks for generated parts and their final analysis."""

from __future__ import annotations

from typing import Any

from simready.gen.spec import BoxOp, CutOp, CylOp, FuseOp, PartSpec


def analyze_generated_part(step_path: str, *, timeout_seconds: int = 120) -> dict[str, Any]:
    """Analyze a generated STEP and reject error or InvalidInput summaries."""
    from simready.copilot.tools import analyze_geometry

    result = analyze_geometry(step_path, timeout_seconds=timeout_seconds, render_image=False)
    if result.get("error") or result.get("status") == "InvalidInput":
        return {
            "ok": False,
            "step_path": step_path,
            "status": result.get("status"),
            "error": result.get("error") or "analysis_failed",
            "analysis": result,
        }
    return {"ok": True, "step_path": step_path, "status": result.get("status"), "analysis": result}


def select_final_build(build_calls: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Select one terminal OCC-valid build transaction, never mix calls.

    A failed later build invalidates the run instead of silently falling back to an
    older artifact. The returned transaction carries the call's spec, result and path.
    """
    if not build_calls:
        return None
    final = build_calls[-1]
    result = final.get("result") or {}
    if not result.get("occ_valid"):
        return None
    try:
        import json
        spec = json.loads(final["arguments"]).get("spec")
    except (KeyError, TypeError, AttributeError, ValueError):
        return None
    return {"spec": spec, "result": result, "step_path": result.get("step_path")}


def verify_part_spec(spec_dict: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    """Return mechanical spec violations; empty means all declared checks passed."""
    try:
        spec = PartSpec.model_validate(spec_dict)
    except Exception as exc:
        return [f"invalid spec: {exc}"]

    errors: list[str] = []
    boxes = [step for step in spec.steps if isinstance(step, BoxOp)]
    cuts = [step for step in spec.steps if isinstance(step, CutOp)]
    if "bbox_mm" in expected:
        if len(boxes) != 1 or len(spec.steps) != 1:
            errors.append("bbox_mm check requires exactly one box step")
        else:
            box = boxes[0]
            actual = [box.dx, box.dy, box.dz]
            wanted = expected["bbox_mm"]
            if any(abs(a - b) > 0.1 for a, b in zip(actual, wanted)):
                errors.append(f"box dimensions {actual} do not match expected {wanted}")

    if "l_bracket" in expected:
        wanted = expected["l_bracket"]
        fuses = [step for step in spec.steps if isinstance(step, FuseOp)]
        if len(spec.steps) != 3 or len(boxes) != 2 or len(fuses) != 1:
            errors.append("L-bracket requires exactly two boxes followed by one fuse")
        else:
            base, upright = boxes
            for label, box, key in [("base", base, "base_mm"), ("upright", upright, "upright_mm")]:
                actual = [box.dx, box.dy, box.dz]
                target = wanted[key]
                if any(abs(a - b) > 0.1 for a, b in zip(actual, target)):
                    errors.append(f"{label} dimensions {actual} do not match expected {target}")
            on_top = abs(upright.at[2] - (base.at[2] + base.dz)) <= 0.1
            x_overlap = min(upright.at[0] + upright.dx, base.at[0] + base.dx) - max(upright.at[0], base.at[0])
            y_overlap = min(upright.at[1] + upright.dy, base.at[1] + base.dy) - max(upright.at[1], base.at[1])
            x_edge = (
                abs(upright.at[0] - base.at[0]) <= 0.1
                or abs(upright.at[0] + upright.dx - base.at[0] - base.dx) <= 0.1
            ) and y_overlap > 0.1
            y_edge = (
                abs(upright.at[1] - base.at[1]) <= 0.1
                or abs(upright.at[1] + upright.dy - base.at[1] - base.dy) <= 0.1
            ) and x_overlap > 0.1
            if not on_top or not (x_edge or y_edge):
                errors.append("upright must sit on top of the base along one edge")

    if "through_hole" in expected:
        hole = expected["through_hole"]
        if len(cuts) != 1 or not isinstance(spec.steps[-1], CutOp):
            errors.append("expected exactly one through-hole cut as the final operation")
        else:
            cut = cuts[0]
            base = spec.steps[cut.a]
            cutter = spec.steps[cut.b]
            if not isinstance(base, BoxOp) or not isinstance(cutter, CylOp):
                errors.append("through-hole cut must subtract a cylinder from a box")
            else:
                if "plate_mm" in hole:
                    actual_plate = [base.dx, base.dy, base.dz]
                    if any(abs(a - b) > 0.1 for a, b in zip(actual_plate, hole["plate_mm"])):
                        errors.append(f"plate dimensions {actual_plate} do not match expected {hole['plate_mm']}")
                center = [base.at[0] + base.dx / 2, base.at[1] + base.dy / 2]
                actual_center = list(cutter.at[:2])
                if any(abs(a - b) > 0.1 for a, b in zip(actual_center, center)):
                    errors.append(f"hole centre {actual_center} is not box centre {center}")
                diameter = 2 * cutter.r
                if abs(diameter - hole["diameter_mm"]) > 0.1:
                    errors.append(f"hole diameter {diameter} does not match {hole['diameter_mm']}")
                if cutter.r * 2 >= min(base.dx, base.dy):
                    errors.append("hole cutter removes the entire box cross-section")
                if cutter.at[2] > base.at[2] or cutter.at[2] + cutter.h < base.at[2] + base.dz:
                    errors.append("cylinder does not span the full box thickness")
    return errors
