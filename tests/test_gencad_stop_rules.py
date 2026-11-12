"""Stop rules must preserve complete programs and cut only at safe prefixes."""
import ast

import pytest

from scripts.gencad_stop_rules import positive_control, r1, r2, r3


def block(k: int, depth: int = 1) -> str:
    return (
        f"# Generating a workplane for sketch {k}\n"
        f"wp_sketch{k} = cq.Workplane('XY')\n"
        f"loop{k}=wp_sketch{k}.circle(1)\n"
        f"solid{k}=wp_sketch{k}.add(loop{k}).extrude({depth})\n"
        + ("solid=solid0\n" if k == 0 else f"solid=solid.union(solid{k})\n")
    )


PREFIX = "import cadquery as cq\n"


def test_r1_complete_is_byte_identical() -> None:
    code = PREFIX + block(0) + block(1) + "\n# trailing comment\n"
    assert r1(code) == code


def test_r1_mid_call_cuts_to_last_solid() -> None:
    complete = PREFIX + block(0)
    assert r1(complete + "# next sketch\nwp_sketch1 = cq.Workplane(") == complete


def test_r2_stops_at_first_exact_normalized_repeat() -> None:
    complete = PREFIX + block(0) + block(1)
    assert r2(complete + block(2) + block(3, 2)) == complete


def test_r2_does_not_stop_on_similar_geometry() -> None:
    code = PREFIX + block(0) + block(1) + block(2, 2)
    assert r2(code) == code


@pytest.mark.parametrize("k", [1, 2, 3])
def test_r3_keeps_exactly_k_complete_blocks(k: int) -> None:
    code = PREFIX + block(0) + block(1) + block(2) + "wp_sketch3 = cq.Workplane("
    expected = PREFIX + "".join(block(i) for i in range(k))
    assert r3(code, k) == expected


@pytest.mark.parametrize("rule", [r1, r2, lambda code: r3(code, 2)])
@pytest.mark.parametrize("suffix", ["wp_sketch2 = cq.Workplane(", "solid=solid.union(\n"])
def test_rules_do_not_leave_unclosed_parentheses(rule, suffix: str) -> None:
    result = rule(PREFIX + block(0) + block(1) + suffix)
    ast.parse(result)


def test_incomplete_first_block_returns_empty() -> None:
    assert r1(PREFIX + "wp_sketch0 = cq.Workplane(") == ""


def test_r3_rejects_nonpositive_cap() -> None:
    with pytest.raises(ValueError):
        r3(PREFIX + block(0), 0)


def test_positive_control_accepts_tolerance() -> None:
    rows = [{"idx": i, "valid": True, "iou": 0.5} for i in range(100)]
    baseline = {i: {"valid": True, "iou": 0.5004} for i in range(100)}
    flags, difference = positive_control(rows, baseline)
    assert flags == 0
    assert difference == pytest.approx(0.0004)


@pytest.mark.parametrize("change", ["flag", "iou", "missing"])
def test_positive_control_rejects_mismatch(change: str) -> None:
    rows = [{"idx": i, "valid": True, "iou": 0.5} for i in range(100)]
    baseline = {i: {"valid": True, "iou": 0.5} for i in range(100)}
    if change == "flag":
        rows[0]["valid"] = False
    elif change == "iou":
        rows[0]["iou"] = 0.502
    else:
        rows.pop()
    with pytest.raises(ValueError):
        positive_control(rows, baseline)
