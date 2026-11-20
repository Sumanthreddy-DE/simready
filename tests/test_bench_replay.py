"""regrade re-checks logged specs without API calls; replay verifies fingerprints."""

from __future__ import annotations

import json

import pytest

from simready.bench import runlog
from simready.bench.attempt import evaluate_reply, parse_reply
from simready.bench.replay import regrade, replay

SPEC = {"steps": [{"op": "box", "dx": 40, "dy": 30, "dz": 5}]}


def _concepts(tmp_path, prompt="c001 explicit prompt"):
    p = tmp_path / "concepts.jsonl"
    p.write_text(json.dumps({
        "concept_id": "c001", "name": "plate", "in_vocab": True,
        "prompts": {"explicit": prompt, "engineer": "c001 engineer prompt", "intent": "c001 intent prompt"},
        "checks": {ph: [{"type": "bbox_min_dim", "min": 1.0}] for ph in ("explicit", "engineer", "intent")},
        "reference_spec": SPEC,
    }) + "\n", encoding="utf-8")
    return p


def _log(tmp_path, records):
    out = tmp_path / "run.jsonl"
    runlog.append(out, {"record": "header", "model": "m", "checker_version": "0.9", "prompt_sha256": "x"})
    for r in records:
        runlog.append(out, r)
    return out


def _attempt(idx, **over):
    base = {"record": "attempt", "attempt_id": f"c001/explicit/{idx}", "concept_id": "c001",
            "phrasing": "explicit", "attempt_idx": idx, "prompt": "c001 explicit prompt", "in_vocab": True,
            "spec": SPEC, "via": "tool", "n_tool_calls": 1, "passed": False,
            "failure_class": "F6_dimension_miss", "fingerprint": {"volume": 6000.0}}
    base.update(over)
    return base


def grade_pass(spec, checks, solids):
    report = {"partial": 1.0, "passed": True, "failure_class": None}
    return {"stage": "graded", "fingerprint": {"volume": 6000.0}, "report": report}


def test_regrade_updates_specs_and_carries_no_parse(tmp_path):
    run = _log(tmp_path, [_attempt(0), _attempt(1, spec=None, failure_class="F1_no_parse", fingerprint=None)])
    out = tmp_path / "regraded.jsonl"
    n = regrade(run, out, concepts_path=_concepts(tmp_path), grade=grade_pass)
    assert n == 1
    by_id = {a["attempt_id"]: a for a in runlog.attempts(out)}
    assert by_id["c001/explicit/0"]["passed"] is True
    assert by_id["c001/explicit/1"]["failure_class"] == "F1_no_parse"
    assert runlog.read_header(out)["regrade_of"].endswith("run.jsonl")


def test_regrade_refuses_changed_prompt_text(tmp_path):
    run = _log(tmp_path, [_attempt(0)])
    with pytest.raises(ValueError, match="prompt text changed"):
        regrade(run, tmp_path / "o.jsonl", concepts_path=_concepts(tmp_path, prompt="a different prompt"),
                grade=grade_pass)


def test_regrade_refuses_existing_output(tmp_path):
    run = _log(tmp_path, [_attempt(0)])
    with pytest.raises(FileExistsError):
        regrade(run, run, concepts_path=_concepts(tmp_path), grade=grade_pass)


def test_replay_match_and_mismatch(tmp_path):
    run = _log(tmp_path, [_attempt(0), _attempt(1, fingerprint={"volume": 1.0})])
    concepts = _concepts(tmp_path)
    assert replay(run, "c001/explicit/0", concepts_path=concepts, grade=grade_pass)[0] is True
    assert replay(run, "c001/explicit/1", concepts_path=concepts, grade=grade_pass)[0] is False


def test_replay_unbuilt_attempt_is_an_error(tmp_path):
    run = _log(tmp_path, [_attempt(0, spec=None, fingerprint=None, failure_class="F1_no_parse")])
    with pytest.raises(ValueError, match="never built"):
        replay(run, "c001/explicit/0", concepts_path=_concepts(tmp_path), grade=grade_pass)


@pytest.mark.parametrize("stage", ["infra_error", "checker_error"])
def test_replay_infrastructure_is_an_error_not_fingerprint_mismatch(tmp_path, stage):
    run = _log(tmp_path, [_attempt(0)])
    def unavailable(*args):
        return {"stage": stage, "error": "backend unavailable"}

    with pytest.raises(RuntimeError, match="backend unavailable"):
        replay(run, "c001/explicit/0", concepts_path=_concepts(tmp_path), grade=unavailable)


def test_regrade_infrastructure_remains_excluded(tmp_path):
    from simready.bench.report import load_run
    run = _log(tmp_path, [_attempt(0)])
    def unavailable(*args):
        return {"stage": "infra_error", "error": "backend unavailable"}
    out = tmp_path / "regraded.jsonl"
    regrade(run, out, concepts_path=_concepts(tmp_path), grade=unavailable)
    assert load_run(out).attempts == []
    assert runlog.attempts(out)[0]["partial"] is None


@pytest.mark.parametrize("arguments", [
    {"spec": SPEC, "reason": "provider envelope"},
    {"spec": dict(SPEC, reason="provider root")},
    {"spec": {"reason": "provider replaced steps"}},
], ids=["valid-spec", "contaminated-spec", "no-spec"])
def test_regrade_preserves_provider_arguments_evidence(tmp_path, arguments):
    from simready.bench.report import load_run

    def must_not_grade(*args):
        pytest.fail("provider contamination must not reach the grader, including during regrade")

    parsed = parse_reply([{"name": "build_part", "arguments": json.dumps(arguments)}], None)
    outcome = evaluate_reply(parsed, [], 1, grade=must_not_grade)
    original = _attempt(0, **outcome, checker_version="original-checker")
    assert original["failure_class"] == "infra_error"
    assert original["error_type"] == "provider_arguments"
    run = _log(tmp_path, [original])
    source_bytes = run.read_bytes()
    out = tmp_path / "regraded.jsonl"

    n = regrade(run, out, concepts_path=_concepts(tmp_path), grade=must_not_grade)

    assert n == 0
    assert runlog.attempts(out) == [original]
    assert run.read_bytes() == source_bytes
    assert load_run(out).attempts == []
    assert runlog.done_attempt_ids(out) == set()


@pytest.mark.parametrize("error_type", ["backend_setup", "backend_runtime", None])
def test_regrade_backend_infrastructure_can_recover(tmp_path, error_type):
    from simready.bench.report import load_run

    original = _attempt(0, failure_class="infra_error", error_type=error_type,
                        error="backend temporarily unavailable", partial=None,
                        passed=None, fingerprint=None)
    run = _log(tmp_path, [original])
    out = tmp_path / "regraded.jsonl"
    n = regrade(run, out, concepts_path=_concepts(tmp_path), grade=grade_pass)
    assert n == 1
    recovered = runlog.attempts(out)[0]
    assert recovered["failure_class"] is None and recovered["passed"] is True
    assert recovered["partial"] == 1.0 and recovered["error_type"] is None
    assert recovered["error"] is None
    assert len(load_run(out).attempts) == 1
    assert runlog.done_attempt_ids(out) == {"c001/explicit/0"}


def test_regrade_preserves_unexpected_envelope_key_as_f2(tmp_path):
    tool_calls = [{"name": "build_part", "arguments": json.dumps({"spec": SPEC, "unexpected": True})}]
    parsed = parse_reply(tool_calls, None)
    outcome = evaluate_reply(parsed, [], 1, grade=grade_pass)
    assert outcome["failure_class"] == "F2_schema"
    original = _attempt(
        0,
        **outcome,
        response={"content": None, "tool_calls": tool_calls, "finish_reason": "tool_calls", "model_returned": "m"},
    )
    run = _log(tmp_path, [original])
    out = tmp_path / "regraded.jsonl"
    regrade(run, out, concepts_path=_concepts(tmp_path), grade=grade_pass)
    regraded = runlog.attempts(out)[0]
    assert regraded["failure_class"] == "F2_schema"
    assert regraded["passed"] is False and regraded["partial"] == 0.0


def test_regrade_of_a_dsl_v2_log_uses_v2_in_vocab(tmp_path, monkeypatch):
    from simready.bench import replay as replay_mod

    concepts = tmp_path / "concepts_x.jsonl"
    line = json.loads(_concepts(tmp_path).read_text(encoding="utf-8"))
    line.update(concept_id="c041", in_vocab=False)
    line.pop("reference_spec")
    concepts.write_text(json.dumps(line) + "\n", encoding="utf-8")
    run = tmp_path / "run.jsonl"
    runlog.append(run, {"record": "header", "model": "m", "checker_version": "0.9", "prompt_sha256": "x",
                        "arm": "dsl-v2", "prompt_file": concepts.name})
    for i in range(2):
        runlog.append(run, _attempt(i, attempt_id=f"c041/explicit/{i}", concept_id="c041", in_vocab=False))
    monkeypatch.setattr(replay_mod, "BENCH_DIR", tmp_path.parent)
    monkeypatch.setattr(replay_mod, "v2_reference_ids", lambda: {"c041"})
    (tmp_path.parent / "prompts").mkdir(exist_ok=True)
    (tmp_path.parent / "prompts" / concepts.name).write_bytes(concepts.read_bytes())
    regrade(run, tmp_path / "o.jsonl", grade=grade_pass)
    assert all(a["in_vocab"] is True for a in runlog.attempts(tmp_path / "o.jsonl"))


def test_regrade_resolves_concepts_v2_from_the_header(tmp_path):
    run = tmp_path / "run.jsonl"
    runlog.append(run, {"record": "header", "model": "m", "checker_version": "0.9", "prompt_sha256": "x",
                        "arm": "dsl-v2", "prompt_file": "concepts_v2.jsonl"})
    assert regrade(run, tmp_path / "o.jsonl", grade=grade_pass) == 0  # no KeyError, no attempts


def test_regrade_of_a_build123d_log_reruns_the_logged_code(tmp_path):
    from simready.bench.code_exec import B123D_PYTHON

    if not B123D_PYTHON.exists():
        pytest.skip(f"build123d venv missing: {B123D_PYTHON}")
    code = "from build123d import *\npart = Box(40, 30, 5)\n"
    run = tmp_path / "run.jsonl"
    runlog.append(run, {"record": "header", "model": "m", "checker_version": "0.9", "prompt_sha256": "x",
                        "arm": "build123d", "prompt_file": "concepts.jsonl"})
    runlog.append(run, _attempt(0, spec=None, code=code, in_vocab=False,
                                response={"content": f"```python\n{code}```", "tool_calls": []}))
    out = tmp_path / "o.jsonl"
    assert regrade(run, out, concepts_path=_concepts(tmp_path), grade=grade_pass) == 1
    rec = runlog.attempts(out)[0]
    assert rec["passed"] is True and rec["in_vocab"] is True and rec["code"] == code
