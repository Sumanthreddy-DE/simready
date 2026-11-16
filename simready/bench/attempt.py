"""One benchmark attempt: parse a model reply, classify pre-build failures,
then build + grade in a killable spawn subprocess.

Failure classes (spec §3) — one primary class per failed attempt, first
failing stage wins: F1 no_parse, F2 schema, F3 reference, F9 out_of_vocab
(checked before schema, because the DSL's discriminator would otherwise
report an unknown op as F2), F4 build_error, F8 timeout, then the checker's
F5/F6/F7. ``infra_error`` and ``checker_error`` are excluded from scoring.
"""

from __future__ import annotations

import json
import multiprocessing as mp
import queue as queue_mod
import re
from dataclasses import dataclass
from typing import Any, Callable

from pydantic import ValidationError

from simready.gen.spec import PartSpec

KNOWN_OPS = frozenset({"box", "cyl", "fuse", "cut"})
GRADE_TIMEOUT_S = 60.0

F1 = "F1_no_parse"
F2 = "F2_schema"
F3 = "F3_reference"
F4 = "F4_build_error"
F8 = "F8_timeout"
F9 = "F9_out_of_vocab"
INFRA = "infra_error"
CHECKER_ERROR = "checker_error"


@dataclass
class ParsedReply:
    spec: dict | None
    via: str | None  # "tool" | "text" | None
    n_tool_calls: int
    error: str = ""


_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```")


def _as_spec(obj: Any) -> dict | None:
    if isinstance(obj, str):
        try:
            obj = json.loads(obj)
        except json.JSONDecodeError:
            return None
    if not isinstance(obj, dict):
        return None
    if "steps" in obj:
        return obj
    if "spec" in obj:
        return _as_spec(obj["spec"])
    return None


def _spec_in_text(text: str) -> dict | None:
    for match in _FENCE.finditer(text):
        spec = _as_spec(match.group(1).strip())
        if spec is not None:
            return spec
    decoder = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(text, i)
        except json.JSONDecodeError:
            continue
        spec = _as_spec(obj)
        if spec is not None:
            return spec
    return None


def parse_reply(tool_calls: list[dict], content: str | None) -> ParsedReply:
    """Accept a ``build_part`` tool call or a JSON spec in text (logged as ``via``)."""
    for call in tool_calls:
        if call.get("name") == "build_part":
            spec = _as_spec(call.get("arguments") or "")
            if spec is not None:
                return ParsedReply(spec, "tool", len(tool_calls))
            return ParsedReply(None, "tool", len(tool_calls), "build_part arguments are not a spec")
    if content:
        spec = _spec_in_text(content)
        if spec is not None:
            return ParsedReply(spec, "text", len(tool_calls))
    return ParsedReply(None, None, len(tool_calls), "no tool call and no JSON spec in text")


def classify_spec(spec: dict) -> tuple[str | None, list[str]]:
    """Pre-build classification: (failure_class or None, error messages)."""
    steps = spec.get("steps")
    if isinstance(steps, list):
        unknown = sorted(
            {str(s["op"]) for s in steps if isinstance(s, dict) and "op" in s and s["op"] not in KNOWN_OPS}
        )
        if unknown:
            return F9, [f"unknown ops: {unknown}"]
    try:
        PartSpec.model_validate(spec)
    except ValidationError as exc:
        errors = exc.errors()
        messages = [f"{'.'.join(map(str, e['loc'])) or '<root>'}: {e['msg']}" for e in errors]
        # Reference/orphan rules are PartSpec model validators: root loc, value_error.
        if all(not e["loc"] and e["type"] == "value_error" for e in errors):
            return F3, messages
        return F2, messages
    return None, []


def _grade_worker(spec_dict: dict, checks_json: list, expected_solids: int, out_queue) -> None:
    """Spawn-child entry point. Build errors and checker errors are kept apart:
    the first is the model's failure, the second is ours."""
    from simready.gen.build import build_shape

    try:
        shape = build_shape(PartSpec.model_validate(spec_dict))
        if shape is None or shape.IsNull():
            raise RuntimeError("build produced a null shape")
    except Exception as exc:  # noqa: BLE001 — any kernel failure is F4
        out_queue.put({"stage": "build_error", "error": f"{type(exc).__name__}: {exc}"})
        return
    try:
        from simready.bench.checker import grade_shape
        from simready.bench.concepts import CHECK_LIST
        from simready.bench.geometry import fingerprint

        report = grade_shape(shape, CHECK_LIST.validate_python(checks_json), expected_solids)
        out_queue.put({"stage": "graded", "fingerprint": fingerprint(shape), "report": report})
    except Exception as exc:  # noqa: BLE001 — our bug, excluded from scoring
        out_queue.put({"stage": "checker_error", "error": f"{type(exc).__name__}: {exc}"})


def grade_spec(
    spec_dict: dict,
    checks: list,
    expected_solids: int = 1,
    timeout_s: float = GRADE_TIMEOUT_S,
) -> dict:
    """Build + gate + check in a spawn child; killed after ``timeout_s``."""
    checks_json = [c.model_dump() if hasattr(c, "model_dump") else c for c in checks]
    ctx = mp.get_context("spawn")
    out_queue = ctx.Queue()
    proc = ctx.Process(target=_grade_worker, args=(spec_dict, checks_json, expected_solids, out_queue))
    proc.start()
    try:
        result = out_queue.get(timeout=timeout_s)  # read before join: large payloads block the child
    except queue_mod.Empty:
        result = {"stage": "timeout", "error": f"build/check over {timeout_s:g}s"}
    finally:
        proc.join(1)
        if proc.is_alive():
            proc.terminate()
            proc.join(5)
            if proc.is_alive():
                proc.kill()
    return result


def evaluate_reply(
    parsed: ParsedReply,
    checks: list,
    expected_solids: int,
    grade: Callable[[dict, list, int], dict] = grade_spec,
) -> dict:
    out: dict[str, Any] = {
        "via": parsed.via,
        "n_tool_calls": parsed.n_tool_calls,
        "spec": parsed.spec,
        "schema_errors": [],
        "build_error": None,
        "fingerprint": None,
        "check_report": None,
        "partial": 0.0,
        "passed": False,
        "failure_class": None,
    }
    if parsed.spec is None:
        out.update(failure_class=F1, schema_errors=[parsed.error])
        return out
    cls, errors = classify_spec(parsed.spec)
    if cls is not None:
        out.update(failure_class=cls, schema_errors=errors)
        return out
    result = grade(parsed.spec, checks, expected_solids)
    stage_class = {"timeout": F8, "build_error": F4, "checker_error": CHECKER_ERROR}
    if result["stage"] in stage_class:
        out.update(failure_class=stage_class[result["stage"]], build_error=result["error"])
        return out
    report = result["report"]
    out.update(
        fingerprint=result["fingerprint"],
        check_report=report,
        partial=report["partial"],
        passed=report["passed"],
        failure_class=report["failure_class"],
    )
    return out
