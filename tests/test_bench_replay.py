"""regrade re-checks logged specs without API calls; replay verifies fingerprints."""

from __future__ import annotations

import json

import pytest

from simready.bench import runlog
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
