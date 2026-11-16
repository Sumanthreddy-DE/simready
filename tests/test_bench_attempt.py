"""Attempt pipeline: reply parsing, pre-build classes, subprocess grading."""

from __future__ import annotations

import json

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
def test_grade_spec_timeout_is_reported_not_raised():
    out = grade_spec(SPEC, [], 1, timeout_s=0.01)
    assert out["stage"] == "timeout"
