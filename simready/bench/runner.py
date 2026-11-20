"""Batch runner: concepts x phrasings x k attempts -> append-only JSONL log.

Resumable: (concept, phrasing, attempt_idx) already logged with a scored
outcome is skipped; infra/checker errors are retried. The header pins model,
prompt-file hash, checker version, system-prompt hash and k, and a resume
that disagrees with it is refused.
"""

from __future__ import annotations

import datetime as dt
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from simready.bench import CHECKER_VERSION, runlog
from simready.bench.attempt import INFRA, evaluate_code_reply, evaluate_reply, grade_spec, parse_reply
from simready.bench.concepts import (
    CONCEPTS_V1, PHRASINGS, Concept, file_sha256, frozen_path, frozen_sha256, in_vocab_for, load_concepts,
    v2_reference_ids,
)
from simready.bench.providers import InfraError, QuotaExhausted

TEMPERATURE = 0.7
MAX_CONSECUTIVE_INFRA = 20
_PINNED = (
    "model",
    "base_url",
    "temperature",
    "max_tokens",
    "official",
    "prompt_sha256",
    "checker_version",
    "arm",
    "system_prompt_sha256",
    "k",
)
_OPTIONAL_PINNED = ("supports_seed", "extra_body")


@dataclass
class WorkItem:
    concept: Concept
    phrasing: str
    idx: int

    @property
    def attempt_id(self) -> str:
        return f"{self.concept.concept_id}/{self.phrasing}/{self.idx}"


@dataclass
class RunSummary:
    path: Path
    written: int
    infra_errors: int
    stopped_reason: str | None


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def plan_items(concepts: list[Concept], k: int, done: set[str], limit: int | None = None) -> list[WorkItem]:
    items = [
        WorkItem(c, p, i)
        for c in concepts
        for p in PHRASINGS
        for i in range(k)
        if f"{c.concept_id}/{p}/{i}" not in done
    ]
    return items[:limit] if limit is not None else items


def run_benchmark(
    *,
    client: Any,
    model_alias: str,
    model_id: str,
    base_url: str,
    k: int,
    out_path: Path,
    concepts_path: Path = CONCEPTS_V1,
    limit: int | None = None,
    workers: int = 4,
    official: bool = False,
    grade: Callable[[dict, list, int], dict] = grade_spec,
    max_tokens: int | None = None,
    supports_seed: bool | None = None,
    extra_body: dict | None = None,
    arm: str = "dsl-v1",
) -> RunSummary:
    from functools import partial

    from simready.bench.prompting import bench_tool, build_messages, dsl_of, system_prompt_sha256

    dsl = dsl_of(arm)  # None for the build123d arm
    if grade is grade_spec and dsl is not None:
        grade = partial(grade_spec, dsl=dsl)
    tools = [bench_tool(arm)] if dsl is not None else []
    in_vocab_v2 = v2_reference_ids()

    out_path = Path(out_path)
    prompt_sha = file_sha256(concepts_path)
    if official:
        if frozen_sha256(frozen_path(concepts_path)) != prompt_sha:
            raise RuntimeError(
                f"official run needs the frozen prompt file ({frozen_path(concepts_path).name} must match)"
            )
        if CHECKER_VERSION.endswith("-dev"):
            raise RuntimeError("official run needs a tagged CHECKER_VERSION (no -dev suffix)")

    concepts = load_concepts(concepts_path)
    header: dict[str, Any] = {
        "record": "header",
        "run_id": out_path.name.removesuffix(".gz").removesuffix(".jsonl"),
        "model_alias": model_alias,
        "model": model_id,
        "base_url": base_url,
        "k": k,
        "temperature": TEMPERATURE,
        "max_tokens": max_tokens,
        "expected_prompts": len(concepts) * len(PHRASINGS),
        "prompt_file": Path(concepts_path).name,
        "prompt_sha256": prompt_sha,
        "checker_version": CHECKER_VERSION,
        "arm": arm,
        "system_prompt_sha256": system_prompt_sha256(arm),
        "official": official,
        "started": _now(),
    }
    if supports_seed is not None:
        header["supports_seed"] = supports_seed
    if extra_body is not None:
        header["extra_body"] = extra_body
    if out_path.exists():
        existing = runlog.read_header(out_path)
        for key in _PINNED:
            had = existing.get(key, "dsl-v1" if key == "arm" else None)  # SP1 headers carry no arm
            if had != header[key]:
                raise RuntimeError(f"resume mismatch on {key}: log has {had!r}, now {header[key]!r}")
        for key in _OPTIONAL_PINNED:
            if key in existing and key in header and existing[key] != header[key]:
                raise RuntimeError(f"resume mismatch on {key}: log has {existing.get(key)!r}, now {header[key]!r}")
    else:
        runlog.append(out_path, header)

    items = plan_items(concepts, k, runlog.done_attempt_ids(out_path), limit)
    stop = threading.Event()
    lock = threading.Lock()
    state: dict[str, Any] = {"written": 0, "infra": 0, "consecutive_infra": 0, "stopped": None}

    def count_infra() -> None:
        with lock:
            state["infra"] += 1
            state["consecutive_infra"] += 1
            if state["consecutive_infra"] >= MAX_CONSECUTIVE_INFRA:
                stop.set()
                state["stopped"] = state["stopped"] or f"{MAX_CONSECUTIVE_INFRA} consecutive infra errors"

    def work(item: WorkItem) -> None:
        if stop.is_set():
            return
        prompt = getattr(item.concept.prompts, item.phrasing)
        base = {
            "record": "attempt",
            "attempt_id": item.attempt_id,
            "concept_id": item.concept.concept_id,
            "name": item.concept.name,
            "in_vocab": in_vocab_for(arm, item.concept, in_vocab_v2),
            "phrasing": item.phrasing,
            "attempt_idx": item.idx,
            "prompt": prompt,
            "model": model_id,
            "prompt_sha256": prompt_sha,
            "checker_version": CHECKER_VERSION,
            "seed": item.idx,
            "ts": _now(),
        }
        try:
            reply = client.complete(build_messages(prompt, arm), tools, TEMPERATURE, seed=item.idx)
        except QuotaExhausted as exc:
            stop.set()
            with lock:
                state["stopped"] = state["stopped"] or f"quota exhausted: {exc}"
            return
        except InfraError as exc:
            runlog.append(out_path, {**base, "failure_class": INFRA, "passed": None, "partial": None,
                                    "error": str(exc), "error_type": "provider_exception"})
            count_infra()
            return
        if reply["model_returned"] != model_id:
            # Vultr answers an unknown or retired id with its default model; never score that.
            stop.set()
            with lock:
                state["stopped"] = state["stopped"] or (
                    f"model substituted: asked {model_id!r}, got {reply['model_returned']!r}"
                )
            return
        checks = getattr(item.concept.checks, item.phrasing)
        if dsl is None:
            outcome = evaluate_code_reply(reply["content"], checks, item.concept.solids)
        else:
            parsed = parse_reply(reply["tool_calls"], reply["content"])
            outcome = evaluate_reply(parsed, checks, item.concept.solids, grade=grade, dsl=dsl)
        record = {
            **base,
            "response": {
                "content": reply["content"],
                "tool_calls": reply["tool_calls"],
                "finish_reason": reply["finish_reason"],
                "model_returned": reply["model_returned"],
            },
            "usage": reply["usage"],
            "latency_s": reply["latency_s"],
            **outcome,
        }
        runlog.append(out_path, record)
        if outcome["failure_class"] in runlog.EXCLUDED_CLASSES:
            count_infra()
            return
        with lock:
            state["consecutive_infra"] = 0
            state["written"] += 1

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(work, items))
    return RunSummary(out_path, state["written"], state["infra"], state["stopped"])
