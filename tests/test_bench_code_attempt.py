from __future__ import annotations

import pytest

from simready.bench.attempt import F1, F2, F4, F8, evaluate_code_reply

GOOD = "```python\nfrom build123d import *\npart = Box(1, 1, 1)\n```"


def fake_run(stage, **extra):
    class _W:
        def cleanup(self):
            pass
    return lambda code, timeout_s=90.0: {"stage": stage, "step_path": "/x/part.step", "workdir": _W(), **extra}


def graded(passed):
    report = {"passed": passed, "partial": 1.0 if passed else 0.0, "failure_class": None if passed else "F6_dimension_miss",
              "checks": [], "gate": {"passed": True}}
    return lambda path, checks, solids: {"stage": "graded", "fingerprint": {"volume": 1.0}, "report": report}


def test_no_block_is_f1():
    assert evaluate_code_reply("I cannot.", [], 1, run=fake_run("built"), grade=graded(True))["failure_class"] == F1


def test_gate_rejection_is_f2():
    out = evaluate_code_reply("```python\nimport os\npart=None\n```", [], 1, run=fake_run("built"), grade=graded(True))
    assert out["failure_class"] == F2 and out["schema_errors"]


def test_build_error_and_timeout():
    assert evaluate_code_reply(GOOD, [], 1, run=fake_run("build_error", error="boom"), grade=graded(True))["failure_class"] == F4
    assert evaluate_code_reply(GOOD, [], 1, run=fake_run("timeout", error="slow"), grade=graded(True))["failure_class"] == F8


def test_graded_pass_keeps_code():
    out = evaluate_code_reply(GOOD, [], 1, run=fake_run("built"), grade=graded(True))
    assert out["passed"] is True and out["code"].startswith("from build123d")


def test_grader_exception_is_excluded_not_raised():
    def boom(path, checks, solids):
        raise RuntimeError("grader bug")
    out = evaluate_code_reply(GOOD, [], 1, run=fake_run("built"), grade=boom)
    assert out["failure_class"] == "checker_error" and out["passed"] is None


def test_corrupt_step_is_build_error(tmp_path):
    from simready.occ_compat import OCC_AVAILABLE
    if not OCC_AVAILABLE:
        pytest.skip("OCC bindings not available")
    from simready.bench.attempt import grade_step
    bad = tmp_path / "part.step"
    bad.write_text("ISO-10303-21;\nnot a step file\n", encoding="utf-8")
    result = grade_step(str(bad), [], 1)
    assert result["stage"] == "build_error" and result["error_type"] == "step_read"
