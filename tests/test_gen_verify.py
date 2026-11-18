"""Deterministic mechanical and analysis gates for geometry generation."""

from simready.gen.verify import analyze_generated_part, select_final_build, verify_part_spec


def box_spec(dx=60, dy=40, dz=30):
    return {"steps": [{"op": "box", "dx": dx, "dy": dy, "dz": dz}]}


def hole_spec(center=(40, 30), diameter=10, cutter_z=0, cutter_h=10):
    return {"steps": [
        {"op": "box", "dx": 80, "dy": 60, "dz": 10},
        {"op": "cyl", "r": diameter / 2, "h": cutter_h, "at": [*center, cutter_z]},
        {"op": "cut", "a": 0, "b": 1},
    ]}


def test_box_dimensions_gate_accepts_requested_dimensions():
    assert verify_part_spec(box_spec(), {"bbox_mm": [60, 40, 30]}) == []


def test_box_dimensions_gate_rejects_wrong_dimensions():
    assert verify_part_spec(box_spec(dx=50), {"bbox_mm": [60, 40, 30]})


def test_through_hole_gate_checks_center_diameter_and_full_thickness():
    expected = {"through_hole": {"diameter_mm": 10, "centered": True}}
    assert verify_part_spec(hole_spec(cutter_z=-1, cutter_h=12), expected) == []
    assert verify_part_spec(hole_spec(center=(10, 10)), expected)
    assert verify_part_spec(hole_spec(diameter=4), expected)
    assert verify_part_spec(hole_spec(cutter_z=5), expected)


def l_bracket_spec(base=(60, 60, 10), upright=(60, 10, 50), at=(0, 0, 10)):
    return {"steps": [
        {"op": "box", "dx": base[0], "dy": base[1], "dz": base[2]},
        {"op": "box", "dx": upright[0], "dy": upright[1], "dz": upright[2], "at": at},
        {"op": "fuse", "a": 0, "b": 1},
    ]}


def test_l_bracket_gate_checks_both_boxes_and_upright_on_base():
    expected = {"l_bracket": {
        "base_mm": [60, 60, 10], "upright_mm": [60, 10, 50],
    }}
    assert verify_part_spec(l_bracket_spec(), expected) == []
    assert verify_part_spec(l_bracket_spec(base=(50, 60, 10)), expected)
    assert verify_part_spec(l_bracket_spec(upright=(60, 1, 50)), expected)
    assert verify_part_spec(l_bracket_spec(at=(0, 0, 20)), expected)
    assert verify_part_spec(l_bracket_spec(at=(0, 100, 10)), expected)


def test_hole_gate_checks_plate_dimensions():
    expected = {"through_hole": {"diameter_mm": 10, "centered": True, "plate_mm": [80, 60, 10]}}
    assert verify_part_spec(hole_spec(), expected) == []
    spec = hole_spec()
    spec["steps"][0]["dx"] = 70
    assert verify_part_spec(spec, expected)


def test_hole_gate_rejects_oversized_cutter_and_later_operations():
    expected = {"through_hole": {"diameter_mm": 10, "centered": True}}
    assert verify_part_spec(hole_spec(diameter=200), expected)
    spec = hole_spec()
    spec["steps"].append({"op": "box", "dx": 5, "dy": 5, "dz": 5})
    spec["steps"].append({"op": "cut", "a": 2, "b": 3})
    assert verify_part_spec(spec, expected)


def build_call(spec, result):
    import json
    return {"arguments": json.dumps({"spec": spec}), "result": result}


def test_final_build_selection_never_mixes_valid_old_artifact_with_failed_new_spec():
    old = build_call(box_spec(), {"occ_valid": True, "step_path": "old.step"})
    failed = build_call(hole_spec(), {"occ_valid": False, "error": "build failed"})

    assert select_final_build([old, failed]) is None


def test_final_build_selection_keeps_one_transaction():
    call = build_call(box_spec(), {"occ_valid": True, "step_path": "final.step"})
    selected = select_final_build([call])
    assert selected["spec"] == box_spec()
    assert selected["step_path"] == "final.step"


def test_generated_analysis_requires_final_artifact_success(monkeypatch):
    seen = {}

    def failed_analysis(path, **kwargs):
        seen["path"] = path
        return {"status": "InvalidInput", "error": "MissingDependency"}

    monkeypatch.setattr("simready.copilot.tools.analyze_geometry", failed_analysis)
    result = analyze_generated_part("final.step")

    assert seen["path"] == "final.step"
    assert result["ok"] is False
    assert result["error"] == "MissingDependency"


def test_generated_analysis_returns_success_summary(monkeypatch):
    monkeypatch.setattr(
        "simready.copilot.tools.analyze_geometry",
        lambda *args, **kwargs: {"status": "SimulationReady", "geometry": {"face_count": 6}},
    )
    result = analyze_generated_part("final.step")
    assert result["ok"] is True
    assert result["analysis"]["geometry"]["face_count"] == 6
