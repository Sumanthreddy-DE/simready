"""E_grammar live-LLM runner — geometry-gen v2 ship gate.

Runs the full CopilotAgent (all four tools) against the 5 hand-written prompts
in ``tests/data/gen_prompts.jsonl`` and asserts, per prompt, that:

- the LLM produced a successful ``build_part`` call (schema_valid + occ_valid),
- the final STEP file exists on disk,
- the face count falls inside the prompt's ``expect.faces`` range.

Marked ``live_llm`` (excluded from CI). Additionally the whole module skips
unless BOTH ``OPENAI_BASE_URL`` and ``OPENAI_MODEL`` are set in the process
environment, so a plain local ``pytest`` never hits a network endpoint.

Provider selection is pure env swap (see ``docs/session-prompts.md`` Stream C):

    $env:OPENAI_BASE_URL = "https://integrate.api.nvidia.com/v1"
    $env:OPENAI_MODEL    = "meta/llama-3.3-70b-instruct"
    & C:\\mm\\sr\\python.exe -m pytest tests/test_gen_e2e.py -m live_llm -v

The API key is resolved indirectly: ``OPENAI_API_KEY_VAR`` names the ``.env``
entry to use (default ``OPENAI_API_KEY``), so the Kimi leg runs with
``OPENAI_API_KEY_VAR=KIMI_API_KEY`` and the secret is never echoed or exported.

Each prompt appends one JSON record to ``data/gen_eval/<model-slug>.jsonl``
(gitignored) — raw material for ``docs/validation/geometry_gen_eval.md``.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.live_llm

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PROMPTS_PATH = _REPO_ROOT / "tests" / "data" / "gen_prompts.jsonl"
_EVAL_OUT_DIR = _REPO_ROOT / "data" / "gen_eval"

_BASE_URL = os.environ.get("OPENAI_BASE_URL", "")
_MODEL = os.environ.get("OPENAI_MODEL", "")

if not (_BASE_URL and _MODEL):
    pytest.skip(
        "live-LLM eval needs OPENAI_BASE_URL and OPENAI_MODEL in the environment",
        allow_module_level=True,
    )

# Wall-clock threshold above which a prompt is flagged (not failed) as slow —
# per the exec plan, a single prompt over 60 s is a latency regression to
# report in the eval doc, not a gate.
SLOW_PROMPT_SECONDS = 60.0


def _resolve_api_key() -> str | None:
    """Resolve the API key without ever echoing it.

    ``OPENAI_API_KEY_VAR`` names which ``.env`` / environment entry to use
    (default ``OPENAI_API_KEY``). Environment wins over ``.env``.
    """
    var_name = os.environ.get("OPENAI_API_KEY_VAR", "OPENAI_API_KEY")
    if os.environ.get(var_name):
        return os.environ[var_name]
    try:
        from dotenv import dotenv_values
    except ImportError:
        return None
    return dotenv_values(_REPO_ROOT / ".env").get(var_name)


_API_KEY = _resolve_api_key()

if not _API_KEY:
    pytest.skip(
        "no API key resolved (set OPENAI_API_KEY, or OPENAI_API_KEY_VAR + .env entry)",
        allow_module_level=True,
    )


def _load_prompts() -> list[dict[str, Any]]:
    rows = []
    with _PROMPTS_PATH.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


_PROMPTS = _load_prompts()


def _model_slug(model: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in model)


def _append_record(record: dict[str, Any]) -> None:
    _EVAL_OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = _EVAL_OUT_DIR / f"{_model_slug(_MODEL)}.jsonl"
    with out.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, default=str) + "\n")


@pytest.fixture(scope="module")
def agent():
    from simready.copilot.agent import CopilotAgent

    return CopilotAgent(model=_MODEL, api_key=_API_KEY, base_url=_BASE_URL)


@pytest.mark.parametrize("case", _PROMPTS, ids=[c["id"] for c in _PROMPTS])
def test_gen_e2e(agent, case):
    events: list[dict[str, Any]] = []
    start = time.monotonic()
    response = agent.run(case["prompt"], on_event=events.append)
    wall_s = time.monotonic() - start

    build_results = [
        e["result"] for e in events
        if e["type"] == "tool_result" and e["name"] == "build_part"
    ]
    analyze_calls = [
        e for e in events
        if e["type"] == "tool_call" and e["name"] == "analyze_geometry"
    ]
    # Last successful build wins (the LLM may retry after a schema error).
    final_build = next(
        (r for r in reversed(build_results) if r.get("occ_valid")),
        build_results[-1] if build_results else None,
    )
    final_spec = None
    for tc in reversed(response.tool_calls):
        if tc["name"] == "build_part":
            try:
                final_spec = json.loads(tc["arguments"]).get("spec")
            except (json.JSONDecodeError, AttributeError):
                final_spec = tc["arguments"]
            break

    lo, hi = case["expect"]["faces"]
    faces = final_build.get("faces") if final_build else None
    step_path = final_build.get("step_path") if final_build else None
    step_exists = bool(step_path) and Path(step_path).exists()
    occ_valid = bool(final_build and final_build.get("occ_valid"))
    passed = step_exists and occ_valid and faces is not None and lo <= faces <= hi

    _append_record({
        "ts": datetime.now(timezone.utc).isoformat(),
        "provider": _BASE_URL,
        "model": _MODEL,
        "prompt_id": case["id"],
        "turns": response.iterations,
        "stop_reason": response.stop_reason,
        "build_part_calls": len(build_results),
        "analyze_geometry_calls": len(analyze_calls),
        "final_spec": final_spec,
        "occ_valid": occ_valid,
        "faces": faces,
        "expect_faces": [lo, hi],
        "step_path": step_path,
        "step_exists": step_exists,
        "wall_seconds": round(wall_s, 2),
        "slow_flag": wall_s > SLOW_PROMPT_SECONDS,
        "passed": passed,
        "final_text_preview": (response.final_text or "")[:400],
    })

    assert build_results, (
        f"{case['id']}: agent never called build_part "
        f"(stop_reason={response.stop_reason}, final_text={response.final_text[:200]!r})"
    )
    assert occ_valid, f"{case['id']}: no OCC-valid build result: {final_build}"
    assert step_exists, f"{case['id']}: STEP missing on disk: {step_path}"
    assert lo <= faces <= hi, (
        f"{case['id']}: face count {faces} outside expected [{lo}, {hi}] "
        f"(spec={final_spec})"
    )
