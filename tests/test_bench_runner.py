"""Runner with a fake model client and fake grader: no network, no OCC."""

from __future__ import annotations

import json

import pytest

from simready.bench import runlog
from simready.bench.providers import InfraError, QuotaExhausted
from simready.bench.runner import run_benchmark

SPEC = {"steps": [{"op": "box", "dx": 40, "dy": 30, "dz": 5}]}


def _concept_line(cid):
    return json.dumps({
        "concept_id": cid, "name": cid, "in_vocab": True,
        "prompts": {"explicit": f"{cid} explicit prompt", "engineer": f"{cid} engineer prompt",
                    "intent": f"{cid} intent prompt"},
        "checks": {p: [{"type": "bbox_min_dim", "min": 1.0}] for p in ("explicit", "engineer", "intent")},
        "reference_spec": SPEC,
    })


@pytest.fixture
def concepts(tmp_path):
    p = tmp_path / "concepts.jsonl"
    p.write_text(_concept_line("c001") + "\n" + _concept_line("c002") + "\n", encoding="utf-8")
    return p


class FakeClient:
    def __init__(self, script=None):
        self.script = script or {}
        self.calls = []

    def complete(self, messages, tools, temperature, seed=None):
        prompt = messages[-1]["content"]
        self.calls.append((prompt, seed))
        action = self.script.get((prompt, seed))
        if isinstance(action, Exception):
            raise action
        return {"tool_calls": [{"name": "build_part", "arguments": json.dumps({"spec": SPEC})}],
                "content": None, "finish_reason": "tool_calls", "model_returned": "m",
                "usage": {"prompt_tokens": 1, "completion_tokens": 1}, "latency_s": 0.01}


def fake_grade(spec, checks, solids):
    report = {"checker_version": "t", "gate": {"passed": True}, "checks": [], "n_pass": 1, "n_fail": 0,
              "n_not_checked": 0, "partial": 1.0, "passed": True, "failure_class": None}
    return {"stage": "graded", "fingerprint": {"volume": 6000.0}, "report": report}


def _run(client, out, concepts, **kw):
    kw.setdefault("workers", 2)
    return run_benchmark(client=client, model_alias="fake", model_id="m", base_url="http://x",
                         k=2, out_path=out, concepts_path=concepts, grade=fake_grade, **kw)


def test_full_run_writes_header_and_all_attempts(tmp_path, concepts):
    out = tmp_path / "run.jsonl"
    summary = _run(FakeClient(), out, concepts)
    assert summary.written == 12 and summary.stopped_reason is None  # 2 concepts x 3 phrasings x k=2
    header = runlog.read_header(out)
    assert header["k"] == 2 and header["model"] == "m" and len(header["prompt_sha256"]) == 64
    atts = runlog.attempts(out)
    assert {a["attempt_id"] for a in atts} >= {"c001/explicit/0", "c002/intent/1"}
    a = atts[0]
    assert a["passed"] is True and a["via"] == "tool" and a["prompt"].endswith("prompt")
    assert "api_key" not in json.dumps(a).lower()


def test_resume_skips_done_and_retries_infra(tmp_path, concepts):
    out = tmp_path / "run.jsonl"
    flaky = FakeClient({("c001 explicit prompt", 0): InfraError("HTTP 503")})
    first = _run(flaky, out, concepts)
    assert first.infra_errors == 1 and first.written == 11
    second_client = FakeClient()
    second = _run(second_client, out, concepts)
    assert second_client.calls == [("c001 explicit prompt", 0)] and second.written == 1
    assert {a["failure_class"] for a in runlog.attempts(out)} == {None}


def test_quota_exhausted_stops_cleanly(tmp_path, concepts):
    out = tmp_path / "run.jsonl"
    client = FakeClient({("c001 explicit prompt", 0): QuotaExhausted("429")})
    summary = _run(client, out, concepts, workers=1)
    assert summary.stopped_reason.startswith("quota")
    # The quota item is first in order, so with one worker nothing else is sent.
    assert summary.written == 0 and len(client.calls) == 1


def test_substituted_model_stops_without_logging(tmp_path, concepts):
    out = tmp_path / "run.jsonl"
    summary = run_benchmark(client=FakeClient(), model_alias="fake", model_id="other", base_url="http://x",
                            k=2, out_path=out, concepts_path=concepts, workers=1, grade=fake_grade)
    assert summary.stopped_reason.startswith("model substituted")
    assert summary.written == 0 and runlog.attempts(out) == []


def test_limit_takes_first_items(tmp_path, concepts):
    out = tmp_path / "run.jsonl"
    assert _run(FakeClient(), out, concepts, limit=3).written == 3


def test_resume_refuses_changed_prompt_file(tmp_path, concepts):
    out = tmp_path / "run.jsonl"
    _run(FakeClient(), out, concepts, limit=1)
    concepts.write_text(_concept_line("c001") + "\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="prompt_sha256"):
        _run(FakeClient(), out, concepts)


def test_official_requires_frozen_hash(tmp_path, concepts):
    with pytest.raises(RuntimeError, match="frozen"):
        _run(FakeClient(), tmp_path / "run.jsonl", concepts, official=True)


def test_runlog_reads_gzip(tmp_path, concepts):
    import gzip
    import shutil

    out = tmp_path / "run.jsonl"
    _run(FakeClient(), out, concepts, limit=2)
    gz = tmp_path / "run.jsonl.gz"
    with open(out, "rb") as src, gzip.open(gz, "wb") as dst:
        shutil.copyfileobj(src, dst)
    assert len(runlog.attempts(gz)) == 2
