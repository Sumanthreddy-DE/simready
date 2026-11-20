from __future__ import annotations

import re

from simready.bench.concepts import CONCEPTS_V1, load_concepts
from simready.bench.repair import feedback_text

# The SP1 failure c027/explicit/0 (gpt-6.1-sol, bench_v1.md 7.1): fingerprint as logged; the check
# details follow the checker's format for that attempt.
C027 = {c.concept_id: c for c in load_concepts(CONCEPTS_V1)}["c027"]
DIM_MISS = {
    "failure_class": "F6_dimension_miss",
    "fingerprint": {"volume": 19762.42, "area": 9377.75, "extents": [40.0, 45.0, 50.0], "faces": 13, "edges": 58, "solids": 1},
    "check_report": {"gate": {"passed": True, "reason": ""}, "checks": [
        {"type": "bbox_sorted", "status": "fail", "detail": "extents [40.0, 45.0, 50.0] vs [(39.9, 40.1), (39.9, 40.1), (49.9, 50.1)]"},
        {"type": "hole_set", "status": "pass", "detail": "pairwise distances [25.0] vs [(24.9, 25.1)]"}]},
    "schema_errors": [], "build_error": None,
}
FEATURES = [{"diameter": 5.5, "kind": "hole", "through": True, "length": 5.0}]


def _bounds(checks) -> set[str]:
    """Every numeric bound in the concept's checks, as the strings a leak would print."""
    out: set[str] = set()

    def walk(x):
        if isinstance(x, (int, float)) and not isinstance(x, bool):
            out.update({f"{x:g}", f"{float(x):.1f}", f"{float(x):.3f}"})
        elif isinstance(x, (list, tuple)):
            for y in x:
                walk(y)
        elif isinstance(x, dict):
            for k, y in x.items():
                if k not in ("type", "what", "through"):
                    walk(y)
    for ch in checks:
        walk(ch.model_dump())
    return out


def test_feedback_reports_measurements():
    text = feedback_text(DIM_MISS, FEATURES)
    assert "F6_dimension_miss" in text and "40.0 x 45.0 x 50.0" in text and "5.5" in text and "19762" in text


def test_feedback_never_leaks_target_ranges_or_details():
    text = feedback_text(DIM_MISS, FEATURES)
    numbers = set(re.findall(r"\d+(?:\.\d+)?", text))
    measured = {"40.0", "45.0", "50.0", "5.5", "5.0", "19762", "1", "6"}  # the part's own values and the class id
    leaked = (numbers - measured) & _bounds(C027.checks.explicit)
    assert not leaked, leaked
    assert " vs " not in text and "bbox_sorted" not in text and "hole_set" not in text


def test_schema_and_build_errors_are_passed_through():
    rec = {"failure_class": "F4_build_error", "build_error": "Standard_ConstructionError: fillet failed",
           "schema_errors": [], "fingerprint": None, "check_report": None}
    assert "fillet failed" in feedback_text(rec, None)


# ---------------------------------------------------------------- repair_run

import json  # noqa: E402

import pytest  # noqa: E402

from simready.bench import repair as repair_mod  # noqa: E402
from simready.bench import runlog  # noqa: E402
from simready.bench.repair import repair_run  # noqa: E402

LOGGED_SPEC = {"steps": [
    {"op": "box", "dx": 50, "dy": 40, "dz": 5, "at": [0, 0, 0]},
    {"op": "box", "dx": 50, "dy": 5, "dz": 40, "at": [0, 0, 5]},
    {"op": "fuse", "a": 0, "b": 1},
    {"op": "cyl", "r": 2.75, "h": 5, "at": [12.5, 25, 0]},
    {"op": "cut", "a": 2, "b": 3},
    {"op": "cyl", "r": 2.75, "h": 5, "at": [37.5, 25, 0]},
    {"op": "cut", "a": 4, "b": 5}]}


class RecordingClient:
    def __init__(self, replies):
        self.replies, self.messages = list(replies), []

    def complete(self, messages, tools, temperature, seed=None):
        self.messages.append(messages)
        return self.replies.pop(0)


def _reply(spec, model="m"):
    return {"tool_calls": [{"name": "build_part", "arguments": json.dumps({"spec": spec})}], "content": None,
            "finish_reason": "tool_calls", "model_returned": model, "usage": {}, "latency_s": 0.1}


def _fake_grade(spec, checks, solids, dsl="v1"):
    report = {"passed": True, "partial": 1.0, "failure_class": None, "checks": [], "gate": {"passed": True}}
    return {"stage": "graded", "fingerprint": {"volume": 1.0}, "report": report, "features": FEATURES}


@pytest.fixture
def source(tmp_path, monkeypatch):
    monkeypatch.setattr(repair_mod, "grade_spec", _fake_grade)
    run = tmp_path / "run.jsonl"
    runlog.append(run, {"record": "header", "model": "m", "prompt_file": "concepts_v1.jsonl",
                        "system_prompt_sha256": "s", "prompt_sha256": "p", "checker_version": "1.0.0"})
    runlog.append(run, {**DIM_MISS, "record": "attempt", "attempt_id": "c027/explicit/0", "concept_id": "c027",
                        "phrasing": "explicit", "attempt_idx": 0, "prompt": C027.prompts.explicit,
                        "in_vocab": True, "passed": False, "spec": LOGGED_SPEC,
                        "response": {"content": None, "tool_calls": [{"name": "build_part"}]}})
    return run


def test_repair_round_one_passes_and_resume_appends_nothing(tmp_path, source):
    out = tmp_path / "rep.jsonl"
    client = RecordingClient([_reply(LOGGED_SPEC)])
    summary = repair_run(source, out, client, model_id="m")
    assert summary.stopped_reason is None and summary.repaired == 1
    recs = runlog.attempts(out)
    assert [(r["attempt_id"], r["round"], r["passed"]) for r in recs] == [("c027/explicit/0/repair1", 1, True)]
    sent = client.messages[0][-1]["content"]
    numbers = set(re.findall(r"\d+(?:\.\d+)?", sent))
    measured = {"40.0", "45.0", "50.0", "5.5", "5.0", "19762", "1", "6"}
    assert not (numbers - measured) & _bounds(C027.checks.explicit), sent
    lines = out.read_text(encoding="utf-8").splitlines()
    again = repair_run(source, out, RecordingClient([]), model_id="m")
    assert again.repaired == 0 and out.read_text(encoding="utf-8").splitlines() == lines


def test_repair_refuses_another_model(tmp_path, source):
    with pytest.raises(RuntimeError, match="repair model"):
        repair_run(source, tmp_path / "rep.jsonl", RecordingClient([]), model_id="other")


def test_repair_stops_on_model_substitution(tmp_path, source):
    summary = repair_run(source, tmp_path / "rep.jsonl", RecordingClient([_reply(LOGGED_SPEC, model="x")]),
                         model_id="m")
    assert summary.stopped_reason.startswith("model substituted")
    assert runlog.attempts(tmp_path / "rep.jsonl") == []


def test_graded_results_carry_measured_features():
    from simready.occ_compat import OCC_AVAILABLE
    if not OCC_AVAILABLE:
        pytest.skip("OCC bindings not available")
    from simready.bench.attempt import grade_spec

    result = grade_spec(LOGGED_SPEC, [], 1)
    assert result["stage"] == "graded"
    holes = [f for f in result["features"] if f["kind"] == "hole"]
    assert len(holes) == 2 and all(f["diameter"] == 5.5 and f["through"] for f in holes)
