"""Attempt pipeline: provider attribution, pre-build classes, subprocess grading."""

from __future__ import annotations

import json
import multiprocessing as mp
import os
import time
from copy import deepcopy

import pytest

from simready.bench.attempt import (
    CHECKER_ERROR,
    F1,
    F2,
    F3,
    F4,
    F8,
    F9,
    ParsedReply,
    classify_spec,
    evaluate_reply,
    grade_spec,
    parse_reply,
)
from simready.occ_compat import OCC_AVAILABLE
from simready.bench import attempt

needs_occ = pytest.mark.skipif(not OCC_AVAILABLE, reason="needs pythonocc or OCP")

SPEC = {"steps": [{"op": "box", "dx": 40, "dy": 30, "dz": 5}]}


def test_parse_tool_call_with_spec_key():
    r = parse_reply([{"name": "build_part", "arguments": json.dumps({"spec": SPEC})}], None)
    assert r.spec == SPEC and r.via == "tool" and r.n_tool_calls == 1


def test_parse_tool_call_with_steps_at_top_and_stringified_spec():
    r1 = parse_reply([{"name": "build_part", "arguments": json.dumps(SPEC)}], None)
    r2 = parse_reply([{"name": "build_part", "arguments": json.dumps({"spec": json.dumps(SPEC)})}], None)
    assert r1.spec == SPEC and r2.spec == SPEC


def test_parse_json_in_text_fenced_and_bare():
    fenced = "Here you go:\n```json\n" + json.dumps(SPEC, indent=2) + "\n```"
    bare = "Plan: a plate. " + json.dumps({"spec": SPEC}) + " Done."
    assert parse_reply([], fenced).spec == SPEC and parse_reply([], fenced).via == "text"
    assert parse_reply([], bare).spec == SPEC


def test_parse_nothing_usable():
    r = parse_reply([], "I can't build that with these operations.")
    assert r.spec is None and r.via is None and "no tool call" in r.error
    bad = parse_reply([{"name": "build_part", "arguments": "{not json"}], None)
    assert bad.spec is None and bad.via == "tool"


def test_classify_unknown_op_is_f9_before_schema():
    cls, errs = classify_spec({"steps": [{"op": "box", "dx": 1, "dy": 1, "dz": 1},
                                         {"op": "fillet", "edges": "all", "r": 1}]})
    assert cls == F9 and "fillet" in errs[0]


def test_classify_schema_vs_reference():
    assert classify_spec({"steps": [{"op": "box", "dx": -1, "dy": 1, "dz": 1}]})[0] == F2
    assert classify_spec({"steps": [{"dx": 1}]})[0] == F2  # missing op is schema, not F9
    orphan = {"steps": [{"op": "box", "dx": 1, "dy": 1, "dz": 1}, {"op": "cyl", "r": 1, "h": 1}]}
    assert classify_spec(orphan)[0] == F3
    assert classify_spec(SPEC) == (None, [])


@pytest.mark.parametrize("bad_op", [["box"], {"name": "fillet"}])
def test_classify_unhashable_op_is_f2_not_type_error(bad_op):
    spec = {"steps": [{"op": bad_op, "dx": 40, "dy": 30, "dz": 5}]}
    cls, errors = classify_spec(spec)
    assert cls == F2 and errors
    out = evaluate_reply(ParsedReply(spec, "tool", 1), [], 1, grade=_must_not_grade)
    assert out["failure_class"] == F2 and out["passed"] is False and out["partial"] == 0.0


def test_deeply_nested_json_and_spec_wrappers_return_f1_not_recursion_error():
    deep_json = '{"spec":' * 1500 + "{}" + "}" * 1500
    deep_brackets = "[" * 10_000 + "]" * 10_000
    deep_braces = '{"x":' + deep_brackets + "}"
    deep_dict: dict = {}
    for _ in range(1500):
        deep_dict = {"spec": deep_dict}

    with pytest.raises(RecursionError):
        json.JSONDecoder().raw_decode(deep_braces, 0)

    cases = [
        ([{"name": "build_part", "arguments": deep_json}], None),
        ([{"name": "build_part", "arguments": deep_brackets}], None),
        ([{"name": "build_part", "arguments": deep_dict}], None),
        ([{"name": "build_part", "arguments": {"spec": deep_brackets, "reason": "x"}}], None),
        ([], f"```json\n{deep_brackets}\n```"),
        ([], f"Plan: {deep_braces}"),
    ]
    for tool_calls, content in cases:
        parsed = parse_reply(tool_calls, content)
        assert parsed.spec is None
        out = evaluate_reply(parsed, [], 1, grade=_must_not_grade)
        assert out["failure_class"] == F1 and out["passed"] is False and out["partial"] == 0.0


def _provider_args(spec, location):
    if location == "envelope":
        return {"spec": spec, "reason": "proxy explanation"}
    root = dict(spec, reason="proxy explanation")
    if location == "direct":
        return root
    return {"spec": json.dumps(root) if location == "stringified" else root}


def _must_not_grade(*args):
    pytest.fail("pre-build failure must never invoke grade")


@pytest.mark.parametrize("location", ["envelope", "root", "direct", "stringified"])
@pytest.mark.parametrize("encoded", [False, True], ids=["object", "json"])
def test_provider_arguments_known_reason_is_unscored(location, encoded):
    # Removing the guard must turn these into scored failures or call grade.
    args = _provider_args(SPEC, location)
    original = deepcopy(args)
    parsed = parse_reply([{"name": "build_part", "arguments": json.dumps(args) if encoded else args}], None)
    spec_before = deepcopy(parsed.spec)
    out = evaluate_reply(parsed, [], 1, grade=_must_not_grade)
    assert out["failure_class"] == "infra_error", out
    assert out["error_type"] == "provider_arguments" and out["error"]
    assert out["passed"] is None and out["partial"] is None
    assert args == original and parsed.spec == spec_before


@pytest.mark.parametrize("args", [
    {"spec": {"reason": "replaced steps"}},
    {"spec": json.dumps({"reason": "replaced steps"})},
    {"reason": "replaced steps"},
    {"spec": {"reason": "replaced steps"}, "reason": "envelope too"},
])
def test_provider_arguments_reason_replacing_steps_is_unscored(args):
    parsed = parse_reply([{"name": "build_part", "arguments": args}], None)
    out = evaluate_reply(parsed, [], 1, grade=_must_not_grade)
    assert out["failure_class"] == "infra_error", out
    assert out["error_type"] == "provider_arguments" and out["error"]
    assert out["passed"] is None and out["partial"] is None


@pytest.mark.parametrize("location", ["envelope", "root", "direct", "stringified"])
@pytest.mark.parametrize("spec, expected", [
    ({"steps": [{"op": "box", "dx": -1, "dy": 30, "dz": 5}]}, F2),
    ({"steps": [{"op": "box", "dx": 1}]}, F2),
    (dict(SPEC, typo="extra root key"), F2),
    ({"steps": [{"op": "fillet"}]}, F9),
    ({"steps": [SPEC["steps"][0], SPEC["steps"][0]]}, F3),
    ({"steps": [SPEC["steps"][0], {"op": "cut", "a": 0, "b": 4}]}, F3),
    ({"steps": [dict(SPEC["steps"][0], reason="nested op is not provider signature")]}, F2),
    ({"unrelated": "missing steps too"}, F2),
])
def test_provider_arguments_independent_defects_keep_model_class(spec, expected, location):
    args = _provider_args(spec, location)
    original = deepcopy(args)
    parsed = parse_reply([{"name": "build_part", "arguments": args}], None)
    out = evaluate_reply(parsed, [], 1, grade=_must_not_grade)
    assert out["failure_class"] == expected, out
    assert out["passed"] is False and out["partial"] == 0 and out["schema_errors"]
    assert args == original


@pytest.mark.parametrize("args, expected", [
    (None, F1), ("{not json", F1), ("", F1),
    ({"spec": "{not json", "reason": "x"}, F1),
    ({"spec": None, "reason": "x"}, F1),
    ({"spec": {}, "reason": "x"}, F2),
    ({"spec": SPEC, "typo": "x"}, F2),
    ({"spec": SPEC, "typo": "x", "reason": "x"}, F2),
    ({"spec": dict(SPEC, reason="x"), "typo": "x"}, F2),
    ({"spec": {"reason": "x"}, "typo": "x"}, F2),
    ({"spec": {"reason": "x", "typo": "x"}}, F2),
    ({"spec": {"spec": SPEC, "reason": "unrelated wrapper"}}, F2),
    ({"spec": {"steps": [dict(SPEC["steps"][0], reason="nested only")]}}, F2),
])
def test_provider_arguments_negative_and_mixed_controls(args, expected):
    parsed = parse_reply([{"name": "build_part", "arguments": args}], json.dumps(SPEC))
    out = evaluate_reply(parsed, [], 1, grade=_must_not_grade)
    assert out["failure_class"] == expected, out
    assert out["passed"] is False and out["partial"] == 0


@pytest.mark.parametrize("args", [{"spec": SPEC}, SPEC, {"spec": json.dumps(SPEC)}])
def test_provider_arguments_clean_controls_still_grade(args):
    def grade(spec, checks, solids):
        assert spec == SPEC and checks == [] and solids == 1
        return {"stage": "graded", "fingerprint": {},
                "report": {"passed": True, "partial": 1.0, "failure_class": None}}
    out = evaluate_reply(parse_reply([{"name": "build_part", "arguments": args}], None), [], 1, grade=grade)
    assert out["passed"] is True and out["partial"] == 1.0


@pytest.mark.parametrize("tool_calls", [[], [{"name": "other_tool", "arguments": "{}"}]])
def test_provider_arguments_text_reason_remains_model_error(tool_calls):
    out = evaluate_reply(parse_reply(tool_calls, json.dumps(dict(SPEC, reason="text"))),
                         [], 1, grade=_must_not_grade)
    assert out["via"] == "text" and out["failure_class"] == F2 and out["partial"] == 0


def test_provider_arguments_direct_classification_and_positional_reply_unchanged():
    spec = dict(SPEC, reason="direct callers are not provider replies")
    assert classify_spec(spec)[0] == F2
    parsed = ParsedReply(spec, "tool", 1, "original fourth positional argument")
    out = evaluate_reply(parsed, [], 1, grade=_must_not_grade)
    assert parsed.error == "original fourth positional argument"
    assert out["failure_class"] == F2 and out["partial"] == 0


def _fake_grade(stage, **extra):
    def grade(spec, checks, solids):
        return {"stage": stage, **extra}
    return grade


def test_evaluate_reply_maps_stages_to_classes():
    p = ParsedReply(SPEC, "tool", 1)
    assert evaluate_reply(ParsedReply(None, None, 0, "x"), [], 1)["failure_class"] == F1
    assert evaluate_reply(p, [], 1, grade=_fake_grade("timeout", error="t"))["failure_class"] == F8
    assert evaluate_reply(p, [], 1, grade=_fake_grade("build_error", error="b"))["failure_class"] == F4
    assert evaluate_reply(p, [], 1, grade=_fake_grade("checker_error", error="c"))["failure_class"] == CHECKER_ERROR
    report = {"partial": 1.0, "passed": True, "failure_class": None}
    out = evaluate_reply(p, [], 1, grade=_fake_grade("graded", fingerprint={"v": 1}, report=report))
    assert out["passed"] is True and out["failure_class"] is None and out["fingerprint"] == {"v": 1}


@needs_occ
def test_grade_spec_in_subprocess_end_to_end():
    spec = {"steps": [{"op": "box", "dx": 40, "dy": 30, "dz": 5},
                      {"op": "cyl", "r": 3, "h": 5, "at": [20, 15, 0]},
                      {"op": "cut", "a": 0, "b": 1}]}
    checks = [{"type": "hole_set", "diameter": [5.9, 6.1], "count": [1, 1], "through": True}]
    out = grade_spec(spec, checks, 1)
    assert out["stage"] == "graded", out
    assert out["report"]["passed"] is True and out["fingerprint"]["solids"] == 1


@needs_occ
def test_grade_spec_startup_budget_is_not_a_model_timeout():
    out = grade_spec(SPEC, [], 1, timeout_s=0.01)
    assert out["stage"] == "infra_error"


# Spawn-safe fault injection: exercise the real worker/supervisor rather than
# substituting grade_spec's result. Patches are made inside the fresh child.
def _missing_backend(spec, checks, solids, out):
    import simready.occ_compat as compat
    compat.OCC_AVAILABLE = False
    compat.BRepPrimAPI_MakeBox = None
    attempt._grade_worker(spec, checks, solids, out)


def _broken_import(spec, checks, solids, out):
    import builtins
    original = builtins.__import__

    def blocked(name, *args, **kwargs):
        if name == "simready.gen.build":
            raise ImportError("broken native library")
        return original(name, *args, **kwargs)

    builtins.__import__ = blocked
    attempt._grade_worker(spec, checks, solids, out)


def _exit_zero(*args):
    os._exit(0)


def _exit_crashed(*args):
    os._exit(17)


def _running_hang(spec, checks, solids, out):
    out.put({"stage": "ready"})
    time.sleep(60)


@pytest.mark.parametrize("worker", [_missing_backend, _broken_import, _exit_zero, _exit_crashed])
def test_worker_infrastructure_fault_is_unscored_and_reaped(monkeypatch, worker):
    monkeypatch.setattr(attempt, "_grade_worker", worker)
    before = {p.pid for p in mp.active_children()}
    started = time.monotonic()
    result = grade_spec(SPEC, [], timeout_s=10)
    assert result["stage"] == "infra_error", result
    assert result["error"] and result["error_type"]
    assert time.monotonic() - started < 8  # exited children fail before budget
    assert {p.pid for p in mp.active_children()} == before
    outcome = evaluate_reply(ParsedReply(SPEC, "tool", 1), [], 1, grade=lambda *a: result)
    assert outcome["failure_class"] == "infra_error"
    assert outcome["partial"] is None and outcome["passed"] is None
    assert outcome["error"] and outcome["error_type"]


def test_running_timeout_is_model_failure_and_reaped(monkeypatch):
    monkeypatch.setattr(attempt, "_grade_worker", _running_hang)
    before = {p.pid for p in mp.active_children()}
    result = grade_spec(SPEC, [], timeout_s=8)
    assert result["stage"] == "timeout", result
    outcome = evaluate_reply(ParsedReply(SPEC, "tool", 1), [], 1, grade=lambda *a: result)
    assert outcome["failure_class"] == F8 and outcome["partial"] == 0.0
    assert {p.pid for p in mp.active_children()} == before


@needs_occ
def test_model_kernel_build_failure_remains_f4():
    # Schema-valid positive length below OCCT's construction tolerance.
    spec = {"steps": [{"op": "box", "dx": 1e-12, "dy": 30, "dz": 5}]}
    result = evaluate_reply(ParsedReply(spec, "tool", 1), [], 1)
    assert result["failure_class"] == F4, result
    assert result["partial"] == 0.0 and result["passed"] is False


@needs_occ
def test_checker_exception_is_unscored():
    # Invalid checker configuration reaches the real checker after a good build.
    result = evaluate_reply(ParsedReply(SPEC, "tool", 1), [{"type": "broken_check"}], 1)
    assert result["failure_class"] == CHECKER_ERROR
    assert result["partial"] is None and result["passed"] is None
    assert result["error"]


def test_grader_exception_is_unscored():
    def broken(*args):
        raise RuntimeError("checker bug")
    result = evaluate_reply(ParsedReply(SPEC, "tool", 1), [], 1, grade=broken)
    assert result["failure_class"] == CHECKER_ERROR
    assert result["partial"] is None and result["error"]


def test_process_start_exception_is_infrastructure(monkeypatch):
    from multiprocessing.process import BaseProcess

    def broken_start(self):
        raise OSError("cannot spawn")

    monkeypatch.setattr(BaseProcess, "start", broken_start)
    result = grade_spec(SPEC, [])
    assert result["stage"] == "infra_error" and "cannot spawn" in result["error"]


def _ignore_terminate(spec, checks, solids, out):
    import signal
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    _running_hang(spec, checks, solids, out)


@pytest.mark.skipif(os.name == "nt", reason="POSIX SIGTERM escalation")
def test_timeout_kill_escalation_reaps_child(monkeypatch):
    monkeypatch.setattr(attempt, "_grade_worker", _ignore_terminate)
    before = {p.pid for p in mp.active_children()}
    result = grade_spec(SPEC, [], timeout_s=8)
    assert result["stage"] == "timeout"
    assert {p.pid for p in mp.active_children()} == before


def _exit_after_ready(spec, checks, solids, out):
    out.put({"stage": "ready"})


def test_exit_after_ready_is_infrastructure(monkeypatch):
    monkeypatch.setattr(attempt, "_grade_worker", _exit_after_ready)
    result = grade_spec(SPEC, [], timeout_s=10)
    assert result["stage"] == "infra_error" and result["exitcode"] == 0


def _builder_bug(spec, checks, solids, out):
    import simready.gen.build as build
    def broken(spec):
        raise NameError("builder bug")
    build.build_shape = broken
    attempt._grade_worker(spec, checks, solids, out)


def test_unexpected_builder_exception_is_unscored(monkeypatch):
    monkeypatch.setattr(attempt, "_grade_worker", _builder_bug)
    result = evaluate_reply(ParsedReply(SPEC, "tool", 1), [], 1)
    assert result["failure_class"] == CHECKER_ERROR
    assert result["partial"] is None and "builder bug" in result["error"]


@pytest.mark.parametrize("envelope", [{}, {"stage": "unknown"}, {"stage": "graded"},
                                      {"stage": "graded", "report": {}, "fingerprint": {}},
                                      {"stage": "infra_error"}])
def test_invalid_grader_envelope_is_unscored(envelope):
    result = evaluate_reply(ParsedReply(SPEC, "tool", 1), [], 1, grade=lambda *a: envelope)
    assert result["failure_class"] == CHECKER_ERROR and result["partial"] is None
    assert result["error_type"] == "grader_protocol"


def _slow_checker_import(spec, checks, solids, out):
    import builtins
    original = builtins.__import__
    def delayed(name, *args, **kwargs):
        if name == "simready.bench.checker":
            time.sleep(60)
        return original(name, *args, **kwargs)
    builtins.__import__ = delayed
    attempt._grade_worker(spec, checks, solids, out)


def test_checker_setup_timeout_is_unscored(monkeypatch):
    monkeypatch.setattr(attempt, "_grade_worker", _slow_checker_import)
    result = grade_spec(SPEC, [], timeout_s=8)
    assert result["stage"] == "infra_error", result


def _large_error_then_exit(spec, checks, solids, out):
    out.put({"stage": "checker_error", "error": "x" * 2_000_000})
    os._exit(17)


def test_crash_during_result_delivery_does_not_timeout(monkeypatch):
    monkeypatch.setattr(attempt, "_grade_worker", _large_error_then_exit)
    result = grade_spec(SPEC, [], timeout_s=10)
    assert result["stage"] in ("checker_error", "infra_error"), result


def _partial_result_exit(spec, checks, solids, out):
    import pickle
    def interrupted_dump(value, stream):
        stream.write(b"partial pickle")
        stream.flush()
        os._exit(17)
    pickle.dump = interrupted_dump
    out.put({"stage": "graded", "report": {}})


def test_partial_message_child_crash_is_bounded_and_reaped(monkeypatch):
    monkeypatch.setattr(attempt, "_grade_worker", _partial_result_exit)
    before = {p.pid for p in mp.active_children()}
    started = time.monotonic()
    result = grade_spec(SPEC, [], timeout_s=10)
    assert result["stage"] == "infra_error" and result["exitcode"] == 17
    assert time.monotonic() - started < 8
    assert {p.pid for p in mp.active_children()} == before
