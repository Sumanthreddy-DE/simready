"""regrade: re-run the current checker on logged specs (no API calls).
replay: rebuild one attempt and verify its geometric fingerprint.

Logged specs are never edited. regrade writes a new log whose header names
the source run and the new checker version; the report cites that version.
Provider-argument errors are carried unchanged: a logged spec alone cannot
recover their original tool envelope. Backend infrastructure can be retried.
"""

from __future__ import annotations

import datetime as dt
from functools import partial
from pathlib import Path
from typing import Callable

from simready.bench import CHECKER_VERSION, runlog
from simready.bench.attempt import ParsedReply, evaluate_reply, grade_spec, parse_reply, validate_grade_result
from simready.bench.concepts import BENCH_DIR, file_sha256, in_vocab_for, load_concepts, v2_reference_ids
from simready.bench.prompting import dsl_of


def _setup(header: dict, concepts_path, grade) -> tuple[str, str, Path, Callable]:
    """Arm, DSL version, concept file and grade function for a logged run.

    A header without ``arm`` is an SP1 run (dsl-v1); the concept file comes
    from the header's ``prompt_file`` unless one is passed.
    """
    arm = header.get("arm", "dsl-v1")
    dsl = dsl_of(arm)
    if dsl is None:
        raise NotImplementedError("build123d arm: Task 7")
    path = Path(concepts_path) if concepts_path is not None else BENCH_DIR / "prompts" / header["prompt_file"]
    return arm, dsl, path, grade or partial(grade_spec, dsl=dsl)


def regrade(
    run_path: str | Path,
    out_path: str | Path,
    concepts_path: str | Path | None = None,
    grade: Callable[[dict, list, int], dict] | None = None,
) -> int:
    out_path = Path(out_path)
    if out_path.exists():
        raise FileExistsError(f"{out_path} exists; regrade never overwrites a log")
    header = runlog.read_header(run_path)
    arm, dsl, concepts_path, grade = _setup(header, concepts_path, grade)
    concepts = {c.concept_id: c for c in load_concepts(concepts_path)}
    v2_ids = v2_reference_ids()
    runlog.append(out_path, {
        **header,
        "checker_version": CHECKER_VERSION,
        "regrade_of": str(run_path),
        "regrade_prompt_sha256": file_sha256(concepts_path),
        "regraded": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    })
    regraded = 0
    for att in runlog.attempts(run_path):
        record = dict(att)
        provider_error = (att.get("failure_class") == "infra_error"
                          and att.get("error_type") == "provider_arguments")
        if att.get("spec") is not None and not provider_error:
            concept = concepts[att["concept_id"]]
            if getattr(concept.prompts, att["phrasing"]) != att["prompt"]:
                raise ValueError(f"{att['attempt_id']}: prompt text changed since the run; regrade re-checks, never re-asks")
            resp = att.get("response")
            if isinstance(resp, dict):
                parsed = parse_reply(resp.get("tool_calls") or [], resp.get("content"))
            else:
                parsed = ParsedReply(att["spec"], att.get("via"), att.get("n_tool_calls", 0))
            record.update(evaluate_reply(parsed, getattr(concept.checks, att["phrasing"]), concept.solids,
                                         grade=grade, dsl=dsl))
            record["checker_version"] = CHECKER_VERSION
            record["in_vocab"] = in_vocab_for(arm, concept, v2_ids)
            regraded += 1
        runlog.append(out_path, record)
    return regraded


def replay(
    run_path: str | Path,
    attempt_id: str,
    concepts_path: str | Path | None = None,
    grade: Callable[[dict, list, int], dict] | None = None,
) -> tuple[bool, dict, dict | None]:
    _, _, concepts_path, grade = _setup(runlog.read_header(run_path), concepts_path, grade)
    by_id = {a["attempt_id"]: a for a in runlog.attempts(run_path)}
    if attempt_id not in by_id:
        raise KeyError(f"{attempt_id} not in {run_path}")
    att = by_id[attempt_id]
    if att.get("fingerprint") is None:
        raise ValueError(f"{attempt_id} never built a shape ({att.get('failure_class')}); nothing to replay")
    concept = {c.concept_id: c for c in load_concepts(concepts_path)}[att["concept_id"]]
    result = validate_grade_result(grade(att["spec"], getattr(concept.checks, att["phrasing"]), concept.solids))
    if result["stage"] in runlog.EXCLUDED_CLASSES:
        raise RuntimeError(f"replay {result['stage']}: {result['error']}")
    rebuilt = result.get("fingerprint")
    return rebuilt == att["fingerprint"], att["fingerprint"], rebuilt
