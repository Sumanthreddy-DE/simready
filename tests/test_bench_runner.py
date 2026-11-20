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


@pytest.mark.parametrize(
    "override,match_key",
    [
        ({"base_url": "http://other"}, "base_url"),
        ({"max_tokens": 999}, "max_tokens"),
        ({"supports_seed": False}, "supports_seed"),
        ({"extra_body": {"thinking": False}}, "extra_body"),
    ],
)
def test_resume_refuses_changed_request_conditions(tmp_path, concepts, override, match_key):
    out = tmp_path / "run.jsonl"
    base_kw = dict(
        client=FakeClient(),
        model_alias="fake",
        model_id="m",
        base_url="http://x",
        k=2,
        out_path=out,
        concepts_path=concepts,
        workers=1,
        grade=fake_grade,
        limit=1,
        max_tokens=512,
        supports_seed=True,
        extra_body={},
    )
    run_benchmark(**base_kw)
    assert runlog.read_header(out)["expected_prompts"] == 6
    with pytest.raises(RuntimeError, match=match_key):
        run_benchmark(**{**base_kw, **override})


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


@pytest.mark.parametrize("stage", ["infra_error", "checker_error"])
def test_checker_infrastructure_is_excluded_retryable_and_counted(tmp_path, concepts, stage):
    from simready.bench.report import load_run, failure_distribution

    out = tmp_path / "run.jsonl"
    def broken_grade(*args):
        return {"stage": stage, "error": "grader unavailable", "error_type": "test_fault"}

    summary = run_benchmark(client=FakeClient(), model_alias="fake", model_id="m", base_url="http://x",
                            k=2, out_path=out, concepts_path=concepts, workers=1, grade=broken_grade, limit=1)
    assert summary.written == 0 and summary.infra_errors == 1
    record = runlog.attempts(out)[0]
    assert record["partial"] is None and record["passed"] is None
    assert not runlog.done_attempt_ids(out)
    report = load_run(out)
    assert report.excluded == 1 and report.attempts == []
    assert all(not counts for counts in failure_distribution(report).values())
    assert _run(FakeClient(), out, concepts, limit=1).written == 1
    assert runlog.attempts(out)[0]["passed"] is True


def test_repeated_checker_errors_stop_the_runner(monkeypatch, tmp_path, concepts):
    monkeypatch.setattr("simready.bench.runner.MAX_CONSECUTIVE_INFRA", 2)
    client = FakeClient()
    def broken_grade(*args):
        return {"stage": "checker_error", "error": "bug"}

    summary = run_benchmark(client=client, model_alias="fake", model_id="m", base_url="http://x",
                            k=2, out_path=tmp_path / "run.jsonl", concepts_path=concepts,
                            workers=1, grade=broken_grade)
    assert summary.infra_errors == 2 and summary.written == 0
    assert len(client.calls) == 2 and "consecutive infra errors" in summary.stopped_reason


def test_header_pins_arm(tmp_path, concepts):
    out = tmp_path / "r.jsonl"
    _run(FakeClient(), out, concepts, arm="dsl-v2")
    assert runlog.read_header(out)["arm"] == "dsl-v2"
    with pytest.raises(RuntimeError, match="resume mismatch on arm"):
        _run(FakeClient(), out, concepts, arm="dsl-v1")


def test_header_without_arm_resumes_as_dsl_v1(tmp_path, concepts):
    out = tmp_path / "r.jsonl"
    _run(FakeClient(), out, concepts, limit=1)
    lines = out.read_text(encoding="utf-8").splitlines()
    header = json.loads(lines[0])
    header.pop("arm")
    out.write_text("\n".join([json.dumps(header)] + lines[1:]) + "\n", encoding="utf-8")
    summary = _run(FakeClient(), out, concepts, arm="dsl-v1")  # an SP1-style header resumes as dsl-v1
    assert summary.written == 11
