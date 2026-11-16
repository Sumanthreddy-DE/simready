"""regrade: re-run the current checker on logged specs (no API calls).
replay: rebuild one attempt and verify its geometric fingerprint.

Logged specs are never edited. regrade writes a new log whose header names
the source run and the new checker version; the report cites that version.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Callable

from simready.bench import CHECKER_VERSION, runlog
from simready.bench.attempt import ParsedReply, evaluate_reply, grade_spec
from simready.bench.concepts import CONCEPTS_V1, file_sha256, load_concepts


def regrade(
    run_path: str | Path,
    out_path: str | Path,
    concepts_path: str | Path = CONCEPTS_V1,
    grade: Callable[[dict, list, int], dict] = grade_spec,
) -> int:
    out_path = Path(out_path)
    if out_path.exists():
        raise FileExistsError(f"{out_path} exists; regrade never overwrites a log")
    concepts = {c.concept_id: c for c in load_concepts(concepts_path)}
    header = runlog.read_header(run_path)
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
        if att.get("spec") is not None:
            concept = concepts[att["concept_id"]]
            if getattr(concept.prompts, att["phrasing"]) != att["prompt"]:
                raise ValueError(f"{att['attempt_id']}: prompt text changed since the run; regrade re-checks, never re-asks")
            parsed = ParsedReply(att["spec"], att.get("via"), att.get("n_tool_calls", 0))
            record.update(evaluate_reply(parsed, getattr(concept.checks, att["phrasing"]), concept.solids, grade=grade))
            record["checker_version"] = CHECKER_VERSION
            record["in_vocab"] = concept.in_vocab
            regraded += 1
        runlog.append(out_path, record)
    return regraded


def replay(
    run_path: str | Path,
    attempt_id: str,
    concepts_path: str | Path = CONCEPTS_V1,
    grade: Callable[[dict, list, int], dict] = grade_spec,
) -> tuple[bool, dict, dict | None]:
    by_id = {a["attempt_id"]: a for a in runlog.attempts(run_path)}
    if attempt_id not in by_id:
        raise KeyError(f"{attempt_id} not in {run_path}")
    att = by_id[attempt_id]
    if att.get("fingerprint") is None:
        raise ValueError(f"{attempt_id} never built a shape ({att.get('failure_class')}); nothing to replay")
    concept = {c.concept_id: c for c in load_concepts(concepts_path)}[att["concept_id"]]
    result = grade(att["spec"], getattr(concept.checks, att["phrasing"]), concept.solids)
    rebuilt = result.get("fingerprint")
    return rebuilt == att["fingerprint"], att["fingerprint"], rebuilt
