"""Report metrics on a synthetic log with hand-computed expected values."""

from __future__ import annotations

import pytest

from simready.bench import runlog
from simready.bench.report import (
    by_phrasing,
    failure_distribution,
    headline,
    incomplete_prompts,
    load_run,
    out_of_vocab,
    render_markdown,
)

# k=2. In-vocab c001: explicit TT, engineer TF, intent FF. c002: explicit TF, engineer FF, intent FF.
OUTCOMES = {
    ("c001", "explicit"): [True, True], ("c001", "engineer"): [True, False], ("c001", "intent"): [False, False],
    ("c002", "explicit"): [True, False], ("c002", "engineer"): [False, False], ("c002", "intent"): [False, False],
}


def _write(tmp_path):
    out = tmp_path / "run.jsonl"
    runlog.append(out, {"record": "header", "model": "m", "model_alias": "fake", "k": 2, "base_url": "http://x",
                        "temperature": 0.7, "prompt_sha256": "a" * 64, "checker_version": "1.0.0",
                        "official": True, "started": "2026-10-10T00:00:00+00:00"})
    for (cid, ph), results in OUTCOMES.items():
        for i, ok in enumerate(results):
            runlog.append(out, {"record": "attempt", "attempt_id": f"{cid}/{ph}/{i}", "concept_id": cid,
                                "phrasing": ph, "in_vocab": True, "passed": ok,
                                "failure_class": None if ok else "F6_dimension_miss",
                                "usage": {"prompt_tokens": 100, "completion_tokens": 50}, "latency_s": 2.0,
                                "check_report": {"n_not_checked": 1}, "ts": "2026-10-10T01:00:00+00:00"})
    for i, cls in enumerate(["F9_out_of_vocab", "F1_no_parse"]):  # out-of-vocab concept: excluded from headline
        runlog.append(out, {"record": "attempt", "attempt_id": f"c003/explicit/{i}", "concept_id": "c003",
                            "phrasing": "explicit", "in_vocab": False, "passed": False, "failure_class": cls,
                            "spec": None, "usage": None, "latency_s": 1.0})
    runlog.append(out, {"record": "attempt", "attempt_id": "c003/engineer/0", "concept_id": "c003",
                        "phrasing": "engineer", "in_vocab": False, "passed": False, "failure_class": "infra_error"})
    return out


def test_headline_pass_at_1_and_k(tmp_path):
    h = headline(load_run(_write(tmp_path)))
    assert h["p1"] == pytest.approx(2 / 6)  # mean of per-prompt p1: (1 + .5 + 0 + .5 + 0 + 0) / 6
    assert h["pk"] == pytest.approx(3 / 6)  # prompts with at least one pass
    assert h["n_concepts"] == 2 and h["n_prompts"] == 6
    assert h["p1_ci"][0] <= h["p1"] <= h["p1_ci"][1]


def test_by_phrasing_and_reasoning_gap(tmp_path):
    b = by_phrasing(load_run(_write(tmp_path)))
    assert b["p1"]["explicit"] == pytest.approx(0.75)
    assert b["p1"]["engineer"] == pytest.approx(0.25)
    assert b["gap"] == pytest.approx(0.5)


def test_failure_distribution_and_out_of_vocab(tmp_path):
    run = load_run(_write(tmp_path))
    assert failure_distribution(run)["engineer"]["F6_dimension_miss"] == 3
    oov = out_of_vocab(run)
    assert oov["used_missing_op (F9)"] == 1 and oov["declined / no spec (F1)"] == 1
    assert sum(oov.values()) == 2  # the infra_error line is not scored as a "faked" outcome
    assert run.excluded == 1  # the infra_error line


def test_incomplete_prompts_counts_short_prompts(tmp_path):
    run = load_run(_write(tmp_path))
    assert incomplete_prompts(run) == 1  # c003/explicit has 2 of k=2; c003/engineer has 0 scored of 2


def test_incomplete_prompts_counts_never_attempted_prompts(tmp_path):
    out = tmp_path / "partial.jsonl"
    runlog.append(
        out,
        {
            "record": "header",
            "model": "m",
            "model_alias": "fake",
            "k": 2,
            "expected_prompts": 6,
            "prompt_file": "concepts_v1.jsonl",
        },
    )
    for i in range(2):
        runlog.append(
            out,
            {
                "record": "attempt",
                "attempt_id": f"c001/explicit/{i}",
                "concept_id": "c001",
                "phrasing": "explicit",
                "in_vocab": True,
                "passed": True,
                "failure_class": None,
            },
        )
    assert incomplete_prompts(load_run(out)) == 5


def test_render_markdown_has_all_generated_tables(tmp_path):
    md = render_markdown([load_run(_write(tmp_path))])
    for heading in ("## 1. Setup", "## 2. Headline", "## 3. By phrasing", "## 4. Failure classes",
                    "## 5. Out-of-vocab concepts", "## 6. Cost", "## 8. Known limits (generated counts)"):
        assert heading in md
    assert "not comparable" in md


# ---------------------------------------------------------------- SP2: arms and repair

from simready.bench.report import ModelRun, paired_diff, repair_summary, subset_p1  # noqa: E402


def _run(passes: dict[str, list[bool]]) -> ModelRun:
    attempts = [{"concept_id": cid, "phrasing": "explicit", "in_vocab": True, "passed": p,
                 "failure_class": None if p else "F6_dimension_miss"}
                for cid, ps in passes.items() for p in ps]
    return ModelRun({"model": "m"}, attempts, 0)


def test_paired_diff_is_per_concept_mean_difference():
    a = _run({"c1": [True, True], "c2": [True, False]})
    b = _run({"c1": [True, False], "c2": [False, False]})
    out = paired_diff(a, b, {"c1", "c2"})
    assert out["diff"] == 0.5 and out["n_concepts"] == 2
    lo, hi = out["diff_ci"]
    assert lo <= 0.5 <= hi


def test_subset_ignores_other_concepts():
    r = _run({"c1": [True], "c2": [False]})
    assert subset_p1(r, {"c1"})["p1"] == 1.0


def test_repair_summary_uses_last_round(tmp_path):
    single = _run({"c1": [False, True]})
    single.attempts[0]["attempt_id"], single.attempts[1]["attempt_id"] = "c1/explicit/0", "c1/explicit/1"
    log = tmp_path / "rep.jsonl"
    runlog.append(log, {"record": "header"})
    for rnd, ok in ((1, False), (2, True)):
        runlog.append(log, {"record": "attempt", "attempt_id": f"c1/explicit/0/repair{rnd}",
                            "repair_of_attempt": "c1/explicit/0", "round": rnd, "passed": ok,
                            "failure_class": None if ok else "F6_dimension_miss"})
    out = repair_summary(single, log, {"c1"})
    assert out["p1_single"] == 0.5 and out["p1_after"] == 1.0 and out["fixed_in_round"] == {2: 1}
