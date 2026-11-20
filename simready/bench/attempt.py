"""One benchmark attempt: parse a model reply, classify pre-build failures,
then build + grade in a killable spawn subprocess.

Failure classes (spec §3) — one primary class per failed attempt, first
failing stage wins: F1 no_parse, F2 schema, F3 reference, F9 out_of_vocab
(checked before schema, because the DSL's discriminator would otherwise
report an unknown op as F2), F4 build_error, F8 timeout, then the checker's
F5/F6/F7. ``infra_error`` and ``checker_error`` are excluded from scoring.
Known tool-argument ``reason`` contamination is infrastructure only when
removing that key exposes no independent model defect; it is never graded.
"""

from __future__ import annotations

import json
import multiprocessing as mp
import os
import pickle
import queue as queue_mod
import re
import tempfile
import time
from collections.abc import Hashable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from pydantic import ValidationError

from simready.gen.dsl import known_ops, spec_model

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
    tool_arguments: dict | None = None  # Original envelope, before _as_spec unwraps it.


_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```")


def _as_spec(obj: Any) -> dict | None:
    if isinstance(obj, str):
        try:
            obj = json.loads(obj)
        except (json.JSONDecodeError, RecursionError):
            return None
    if not isinstance(obj, dict):
        return None
    if "steps" in obj:
        return obj
    if "spec" in obj:
        try:
            return _as_spec(obj["spec"])
        except RecursionError:
            return None
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
        except (json.JSONDecodeError, RecursionError):
            continue
        spec = _as_spec(obj)
        if spec is not None:
            return spec
    return None


def parse_reply(tool_calls: list[dict], content: str | None) -> ParsedReply:
    """Accept tool/text specs, retaining tool-envelope evidence for attribution."""
    for call in tool_calls:
        if call.get("name") == "build_part":
            arguments = call.get("arguments")
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except (json.JSONDecodeError, RecursionError):
                    arguments = None
            metadata = arguments if isinstance(arguments, dict) else None
            spec = _as_spec(arguments)
            if spec is not None:
                return ParsedReply(spec, "tool", len(tool_calls), tool_arguments=metadata)
            return ParsedReply(None, "tool", len(tool_calls), "build_part arguments are not a spec", metadata)
    if content:
        spec = _spec_in_text(content)
        if spec is not None:
            return ParsedReply(spec, "text", len(tool_calls))
    return ParsedReply(None, None, len(tool_calls), "no tool call and no JSON spec in text")


def classify_spec(spec: dict, dsl: str = "v1") -> tuple[str | None, list[str]]:
    """Pre-build classification: (failure_class or None, error messages)."""
    steps = spec.get("steps")
    if isinstance(steps, list):
        unknown = sorted(
            {
                str(s["op"])
                for s in steps
                if isinstance(s, dict)
                and "op" in s
                and isinstance(s["op"], Hashable)
                and s["op"] not in known_ops(dsl)
            }
        )
        if unknown:
            return F9, [f"unknown ops: {unknown}"]
    try:
        spec_model(dsl).model_validate(spec)
    except ValidationError as exc:
        errors = exc.errors()
        messages = [f"{'.'.join(map(str, e['loc'])) or '<root>'}: {e['msg']}" for e in errors]
        # Reference/orphan rules are PartSpec model validators: root loc, value_error.
        if all(not e["loc"] and e["type"] == "value_error" for e in errors):
            return F3, messages
        return F2, messages
    return None, []


def _tool_argument_failure(arguments: dict, dsl: str = "v1") -> tuple[str | None, list[str]]:
    """Inspect only the build_part envelope and PartSpec root, without mutation.

    Validate a copy minus known ``reason`` keys so extra-forbid validation
    cannot mask reference errors. Only a reason-only root may replace steps;
    other missing fields, extra keys and nested operation keys remain scored.
    """
    root = arguments
    extra_keys: set[str] = set()
    has_reason = "reason" in arguments
    if "steps" not in arguments and "spec" in arguments:
        extra_keys = set(arguments) - {"spec", "reason"}
        root = arguments["spec"]
        if isinstance(root, str):
            try:
                root = json.loads(root)
            except (json.JSONDecodeError, RecursionError):
                return None, []  # Malformed JSON retains F1 precedence.
    if not isinstance(root, dict):
        return None, []
    has_reason = has_reason or "reason" in root
    if not has_reason and not extra_keys:
        return None, []
    clean = {key: value for key, value in root.items() if key != "reason"}
    if set(root) != {"reason"}:
        cls, errors = classify_spec(clean, dsl)
        if cls is not None:
            return cls, errors
    if extra_keys:
        return F2, [f"build_part arguments: unexpected keys {sorted(extra_keys)}"]
    return INFRA, ["Known provider reason key in build_part arguments or PartSpec root"]


def _read_step(path: str):
    from simready.occ_compat import IFSelect_RetDone, STEPControl_Reader
    reader = STEPControl_Reader()
    if reader.ReadFile(path) != IFSelect_RetDone:
        raise ValueError(f"STEP read failed: {path}")
    reader.TransferRoots()
    return reader.OneShape()


def _grade_worker(source: dict, checks_json: list, expected_solids: int, out_queue) -> None:
    """Spawn-child entry point. Build errors and checker errors are kept apart:
    the first is the model's failure, the second is ours.

    ``source`` is ``{"kind": "spec", "spec": ..., "dsl": "v1"|"v2"}`` or
    ``{"kind": "step", "path": ...}`` (build123d arm: a STEP file the model's
    code wrote). The STEP read runs after the ready signal, so it counts toward
    the model's time budget; an unreadable file is the model's build error.
    """
    try:
        from simready.occ_compat import OCC_AVAILABLE
        from simready.gen.dsl import build as dsl_build
        from simready.bench.checker import grade_shape
        from simready.bench.concepts import CHECK_LIST
        from simready.bench.geometry import fingerprint

        if not OCC_AVAILABLE:
            raise RuntimeError("OCCT backend unavailable; install simready[bench] (OCP) or use pythonocc")
    except Exception as exc:
        out_queue.put({"stage": INFRA, "error_type": "backend_setup", "error": f"{type(exc).__name__}: {exc}"})
        return
    try:
        if source["kind"] == "spec":
            spec_model(source["dsl"]).model_validate(source["spec"])
        elif source["kind"] != "step":
            raise ValueError(f"unknown grade source {source['kind']!r}")
        validated_checks = CHECK_LIST.validate_python(checks_json)
    except Exception as exc:
        out_queue.put({"stage": CHECKER_ERROR, "error_type": "checker_setup", "error": f"{type(exc).__name__}: {exc}"})
        return
    out_queue.put({"stage": "ready"})
    try:
        if source["kind"] == "spec":
            shape = dsl_build(source["dsl"], source["spec"])
        else:
            shape = _read_step(source["path"])
        if shape is None or shape.IsNull():
            out_queue.put({"stage": "build_error", "error": "build produced a null shape"})
            return
    except (ImportError, OSError) as exc:
        out_queue.put({"stage": INFRA, "error_type": "backend_runtime", "error": f"{type(exc).__name__}: {exc}"})
        return
    except ValueError as exc:
        if source["kind"] != "step":
            out_queue.put({"stage": CHECKER_ERROR, "error_type": "builder_exception",
                           "error": f"{type(exc).__name__}: {exc}"})
            return
        out_queue.put({"stage": "build_error", "error_type": "step_read", "error": f"{type(exc).__name__}: {exc}"})
        return
    except Exception as exc:
        # Native geometry exceptions are model failures; Python executor bugs
        # must never be turned into zero rewards.
        native = (type(exc).__module__ in ("OCP.OCP.Standard", "OCP.Standard", "OCC.Core.Standard")
                  or type(exc).__name__ == "KernelBuildError")
        out_queue.put({"stage": "build_error" if native else CHECKER_ERROR,
                       "error_type": "kernel_build" if native else "builder_exception",
                       "error": f"{type(exc).__name__}: {exc}"})
        return
    try:
        report = grade_shape(shape, validated_checks, expected_solids)
        out_queue.put({"stage": "graded", "fingerprint": fingerprint(shape), "report": report})
    except Exception as exc:  # noqa: BLE001 — our bug, excluded from scoring
        out_queue.put({"stage": "checker_error", "error_type": "checker_exception", "error": f"{type(exc).__name__}: {exc}"})


@dataclass
class _GradeMailbox:
    """Private parent/child mailbox; atomic publication avoids partial pipe reads.

    Pickle is read only from our own child in a private TemporaryDirectory.
    A crashed writer leaves an unpublished .tmp file, never a partial result.
    """
    directory: str

    def put(self, result: dict) -> None:
        name = "ready" if result.get("stage") == "ready" else "result"
        target = Path(self.directory) / name
        with target.with_suffix(".tmp").open("wb") as stream:
            pickle.dump(result, stream)
        os.replace(target.with_suffix(".tmp"), target)

    def get_nowait(self) -> dict:
        target = Path(self.directory) / "result"
        if target.exists():
            with target.open("rb") as stream:
                return pickle.load(stream)
        raise queue_mod.Empty

def _wait_for_grade(proc, mailbox, timeout_s: float) -> dict:
    deadline = time.monotonic() + timeout_s
    while True:
        remaining = deadline - time.monotonic()
        try:
            return mailbox.get_nowait()
        except queue_mod.Empty:
            if not proc.is_alive():
                # Publication can race the first poll; reread after observing exit.
                try:
                    return mailbox.get_nowait()
                except queue_mod.Empty:
                    return {"stage": INFRA, "error_type": "child_exit", "exitcode": proc.exitcode,
                            "error": f"grader child exited without a result (exitcode={proc.exitcode})"}
            if remaining <= 0:
                if (Path(mailbox.directory) / "ready").exists():
                    return {"stage": "timeout", "error": f"build/check over {timeout_s:g}s"}
                return {"stage": INFRA, "error_type": "startup_timeout",
                        "error": f"grader startup did not complete within {timeout_s:g}s"}
            time.sleep(min(0.05, remaining))


def grade_spec(
    spec_dict: dict,
    checks: list,
    expected_solids: int = 1,
    timeout_s: float = GRADE_TIMEOUT_S,
    dsl: str = "v1",
) -> dict:
    """Build + check in a killable child. Setup/exit faults are unscored infra.

    The wall-clock budget includes startup; expiration before the worker's
    ready signal is infrastructure, after it is the model's F8 timeout.
    """
    with tempfile.TemporaryDirectory(prefix="simready-grade-") as directory:
        source = {"kind": "spec", "spec": spec_dict, "dsl": dsl}
        return _spawn_grade(source, checks, expected_solids, timeout_s, _GradeMailbox(directory))


def grade_step(step_path: str, checks: list, expected_solids: int = 1, timeout_s: float = GRADE_TIMEOUT_S) -> dict:
    """Read + check a STEP file in a killable child (build123d arm); same protocol as grade_spec."""
    with tempfile.TemporaryDirectory(prefix="simready-grade-") as directory:
        return _spawn_grade({"kind": "step", "path": step_path}, checks, expected_solids, timeout_s,
                            _GradeMailbox(directory))


def _spawn_grade(source, checks, expected_solids, timeout_s, mailbox) -> dict:
    proc = None
    try:
        checks_json = [c.model_dump() if hasattr(c, "model_dump") else c for c in checks]
        ctx = mp.get_context("spawn")
        proc = ctx.Process(target=_grade_worker, args=(source, checks_json, expected_solids, mailbox))
        proc.start()
        return validate_grade_result(_wait_for_grade(proc, mailbox, timeout_s))
    except Exception as exc:
        return {"stage": INFRA, "error_type": "supervisor_exception", "error": f"{type(exc).__name__}: {exc}"}
    finally:
        if proc is not None:
            if proc.pid is not None:
                proc.join(0.1)
                if proc.is_alive():
                    proc.terminate()
                    proc.join(1)
                if proc.is_alive():
                    proc.kill()
                    proc.join()
            proc.close()


def validate_grade_result(result: dict) -> dict:
    """Normalize a broken grader protocol to an explicit unscored error."""
    try:
        stage = result["stage"]
        if stage == "graded":
            report = result["report"]
            if not isinstance(result["fingerprint"], dict):
                raise ValueError("missing fingerprint")
            if type(report["passed"]) is not bool or not 0 <= report["partial"] <= 1:
                raise ValueError("invalid score fields")
            if report["failure_class"] is not None and report["failure_class"] not in {
                "F5_invalid_solid", "F6_dimension_miss", "F7_feature_miss"
            }:
                raise ValueError("invalid checker failure class")
        elif stage in ("build_error", "timeout", INFRA, CHECKER_ERROR):
            if not isinstance(result["error"], str) or not result["error"]:
                raise ValueError("missing error detail")
        else:
            raise ValueError(f"unknown stage {stage!r}")
        return result
    except (KeyError, TypeError, ValueError) as exc:
        return {"stage": CHECKER_ERROR, "error_type": "grader_protocol", "error": f"Invalid grader result: {exc}"}


def evaluate_reply(
    parsed: ParsedReply,
    checks: list,
    expected_solids: int,
    grade: Callable[[dict, list, int], dict] = grade_spec,
    dsl: str = "v1",
) -> dict:
    """Classify provider evidence and independent model defects before grading."""
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
        "error": None,
        "error_type": None,
    }
    if parsed.via == "tool" and parsed.tool_arguments is not None:
        cls, errors = _tool_argument_failure(parsed.tool_arguments, dsl)
        if cls == INFRA:
            out.update(failure_class=INFRA, error_type="provider_arguments",
                       error="; ".join(errors), passed=None, partial=None)
            return out
        if cls is not None:
            out.update(failure_class=cls, schema_errors=errors)
            return out
    if parsed.spec is None:
        out.update(failure_class=F1, schema_errors=[parsed.error])
        return out
    cls, errors = classify_spec(parsed.spec, dsl)
    if cls is not None:
        out.update(failure_class=cls, schema_errors=errors)
        return out
    try:
        result = validate_grade_result(grade(parsed.spec, checks, expected_solids))
    except Exception as exc:
        result = {"stage": CHECKER_ERROR, "error_type": "grader_exception", "error": f"{type(exc).__name__}: {exc}"}
    stage_class = {"timeout": F8, "build_error": F4, "checker_error": CHECKER_ERROR, INFRA: INFRA}
    if result["stage"] in stage_class:
        cls = stage_class[result["stage"]]
        out.update(failure_class=cls, error=result["error"], error_type=result.get("error_type"))
        if cls in (INFRA, CHECKER_ERROR):
            out.update(partial=None, passed=None)
        else:
            out["build_error"] = result["error"]
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


def evaluate_code_reply(
    content: str | None,
    checks: list,
    expected_solids: int,
    run: Callable[[str], dict] | None = None,
    grade: Callable[[str, list, int], dict] = grade_step,
) -> dict:
    """build123d arm: extract, gate, run in the sandbox venv, grade the STEP (design E4).

    No fenced block is F1, a gate rejection F2, an exception or missing part F4,
    a wall-clock or CPU kill F8; then the checker's F5/F6/F7.
    """
    from simready.bench.code_arm import extract_code, gate_code
    if run is None:
        from simready.bench.code_exec import run_code as run
    out: dict[str, Any] = {
        "via": "text", "n_tool_calls": 0, "spec": None, "code": None, "schema_errors": [], "build_error": None,
        "fingerprint": None, "check_report": None, "partial": 0.0, "passed": False, "failure_class": None,
        "error": None, "error_type": None,
    }
    code = extract_code(content)
    if code is None:
        out.update(failure_class=F1, schema_errors=["no fenced python block"])
        return out
    out["code"] = code
    errors = gate_code(code)
    if errors:
        out.update(failure_class=F2, schema_errors=errors)
        return out
    built = run(code)
    if built["stage"] != "built":
        cls = {"build_error": F4, "timeout": F8}.get(built["stage"], INFRA)
        out.update(failure_class=cls, error=built["error"], error_type=built["stage"])
        if cls == INFRA:
            out.update(partial=None, passed=None)
        else:
            out["build_error"] = built["error"]
        return out
    try:
        result = validate_grade_result(grade(built["step_path"], checks, expected_solids))
    except Exception as exc:  # same guard as evaluate_reply: a grader bug never kills the run
        result = {"stage": CHECKER_ERROR, "error_type": "grader_exception", "error": f"{type(exc).__name__}: {exc}"}
    finally:
        built["workdir"].cleanup()
    if result["stage"] != "graded":
        cls = {"build_error": F4, "timeout": F8, CHECKER_ERROR: CHECKER_ERROR}.get(result["stage"], INFRA)
        out.update(failure_class=cls, error=result["error"], error_type=result.get("error_type"))
        if cls in (INFRA, CHECKER_ERROR):
            out.update(partial=None, passed=None)
        else:
            out["build_error"] = result["error"]
        return out
    report = result["report"]
    out.update(fingerprint=result["fingerprint"], check_report=report, partial=report["partial"],
               passed=report["passed"], failure_class=report["failure_class"])
    return out
