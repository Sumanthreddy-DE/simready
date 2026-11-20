"""Repair pass (design E5): feed back only what was measured on the model's own
part, up to two rounds, logged apart from single-shot.

Never sent: target ranges, the check list, check ``detail`` strings.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from simready.bench import runlog
from simready.bench.attempt import INFRA, evaluate_code_reply, evaluate_reply, grade_spec, parse_reply
from simready.bench.concepts import CONCEPTS_V1, CONCEPTS_V2, load_concepts
from simready.bench.providers import InfraError, QuotaExhausted
from simready.bench.prompting import bench_tool, build_messages, dsl_of
from simready.bench.runner import MAX_CONSECUTIVE_INFRA, TEMPERATURE

PRE_BUILD = {"F1_no_parse", "F2_schema", "F3_reference", "F9_out_of_vocab"}


def _fmt(x: float) -> str:
    return f"{x:.1f}"


def feedback_text(record: dict, features: list[dict] | None) -> str:
    cls = record.get("failure_class")
    lines = [f"Your part was rejected: {cls}."]
    if cls in PRE_BUILD:
        lines += [f"- {e}" for e in record.get("schema_errors") or []]
    elif cls in ("F4_build_error", "F8_timeout"):
        lines.append(f"- {record.get('build_error') or record.get('error')}")
    else:
        gate = (record.get("check_report") or {}).get("gate") or {}
        if gate.get("reason"):
            lines.append(f"- solid check: {gate['reason']}")
        fp = record.get("fingerprint") or {}
        if fp.get("extents"):
            lines.append("- bounding box: " + " x ".join(_fmt(e) for e in fp["extents"]) + " mm")
        if fp.get("volume") is not None:
            lines.append(f"- volume: {fp['volume']:.0f} mm^3, solids: {fp.get('solids')}")
        for f in features or []:
            through = "" if f["kind"] == "boss" else (" through" if f["through"] else " blind")
            lines.append(f"- {f['kind']}{through}: diameter {_fmt(f['diameter'])} mm, length {_fmt(f['length'])} mm")
    lines.append("Compare these measurements with the request and answer again with a corrected part.")
    return "\n".join(lines)


def _previous_turn(record: dict) -> dict:
    resp = record.get("response") or {}
    if record.get("spec") is not None and resp.get("tool_calls"):
        return {"role": "assistant", "content": "build_part(" + json.dumps({"spec": record["spec"]}) + ")"}
    return {"role": "assistant", "content": resp.get("content") or ""}


@dataclass
class RepairSummary:
    path: Path
    repaired: int
    infra_errors: int
    stopped_reason: str | None


def _done_rounds(out_path: Path) -> dict[str, list[dict]]:
    """Scored repair records already in the log, by source attempt (resume)."""
    done: dict[str, list[dict]] = {}
    for rec in runlog.attempts(out_path):
        if rec.get("failure_class") not in runlog.EXCLUDED_CLASSES:
            done.setdefault(rec["repair_of_attempt"], []).append(rec)
    return done


def repair_run(run_path, out_path, client, model_id: str, max_rounds: int = 2,
               concepts_paths=(CONCEPTS_V1, CONCEPTS_V2)) -> RepairSummary:
    run_path, out_path = Path(run_path), Path(out_path)
    header = runlog.read_header(run_path)
    if model_id != header["model"]:
        raise RuntimeError(f"repair model {model_id!r} differs from the run's model {header['model']!r}")
    arm = header.get("arm", "dsl-v1")
    dsl = dsl_of(arm)
    concepts = {c.concept_id: c for p in concepts_paths for c in load_concepts(p)}
    new_header = {**header, "repair_of": str(run_path), "max_rounds": max_rounds}
    if out_path.exists():
        existing = runlog.read_header(out_path)
        for key in ("repair_of", "max_rounds", "model", "system_prompt_sha256", "prompt_sha256", "checker_version"):
            if existing.get(key) != new_header.get(key):
                raise RuntimeError(f"resume mismatch on {key}: log has {existing.get(key)!r}, now {new_header.get(key)!r}")
    else:
        runlog.append(out_path, new_header)
    done = _done_rounds(out_path)
    tools = [bench_tool(arm)] if bench_tool(arm) is not None else []
    grade = partial(grade_spec, dsl=dsl) if dsl else None
    repaired = infra = consecutive = 0
    for att in runlog.attempts(run_path):
        if att.get("passed") is not False or not att.get("in_vocab"):
            continue  # passed, excluded (None), or out of vocab for this arm: never repaired
        prior = sorted(done.get(att["attempt_id"], []), key=lambda r: r["round"])
        if prior and (prior[-1].get("passed") or prior[-1]["round"] >= max_rounds):
            continue  # finished in an earlier invocation
        concept = concepts[att["concept_id"]]
        checks = getattr(concept.checks, att["phrasing"])
        messages = build_messages(att["prompt"], arm)
        current = att
        for rec in prior:  # rebuild the conversation so far
            messages += [_previous_turn(current), {"role": "user", "content": feedback_text(current, current.get("features"))}]
            current = rec
        for rnd in range(len(prior) + 1, max_rounds + 1):
            features = current.get("features")
            if features is None and current.get("spec") is not None and dsl:
                measured = grade(current["spec"], [], concept.solids)
                features = measured.get("features") if measured.get("stage") == "graded" else None
            turn = messages + [_previous_turn(current), {"role": "user", "content": feedback_text(current, features)}]
            try:
                reply = client.complete(turn, tools, TEMPERATURE, seed=att["attempt_idx"] * 10 + rnd)
            except QuotaExhausted as exc:
                return RepairSummary(out_path, repaired, infra, f"quota exhausted: {exc}")
            except InfraError as exc:
                runlog.append(out_path, {**att, "attempt_id": f"{att['attempt_id']}/repair{rnd}",
                                         "repair_of_attempt": att["attempt_id"], "round": rnd,
                                         "failure_class": INFRA, "passed": None, "partial": None,
                                         "error": str(exc), "error_type": "provider_exception"})
                infra += 1
                consecutive += 1
                if consecutive >= MAX_CONSECUTIVE_INFRA:
                    return RepairSummary(out_path, repaired, infra, f"{MAX_CONSECUTIVE_INFRA} consecutive infra errors")
                break  # retried on resume
            if reply["model_returned"] != model_id:
                return RepairSummary(out_path, repaired, infra,
                                     f"model substituted: asked {model_id!r}, got {reply['model_returned']!r}")
            consecutive = 0
            messages = turn
            if dsl:
                outcome = evaluate_reply(parse_reply(reply["tool_calls"], reply["content"]), checks, concept.solids,
                                         grade=grade, dsl=dsl)
            else:
                outcome = evaluate_code_reply(reply["content"], checks, concept.solids)
            current = {**att, "response": {"content": reply["content"], "tool_calls": reply["tool_calls"]},
                       "usage": reply["usage"], "latency_s": reply["latency_s"], **outcome,
                       "attempt_id": f"{att['attempt_id']}/repair{rnd}",
                       "repair_of_attempt": att["attempt_id"], "round": rnd}
            runlog.append(out_path, current)
            if current.get("passed") or current.get("failure_class") in runlog.EXCLUDED_CLASSES:
                break
        repaired += 1
    return RepairSummary(out_path, repaired, infra, None)
