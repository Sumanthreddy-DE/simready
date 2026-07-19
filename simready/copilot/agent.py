"""SimReady Copilot agent — OpenAI-compatible tool-use loop.

Day 2: multi-turn tool loop. The model may chain tools across turns; the loop
terminates when the assistant returns a text-only message (no tool_calls) or
when max_iterations is reached.

Errors raised by tool resolvers are surfaced back to the LLM as the tool
result, so the model can recover (e.g. ask the user for a different path).
Rate-limit / transient HTTP errors retry with exponential backoff.

The client is OpenAI-compatible so any provider (OpenAI, OpenRouter, NVIDIA
NIM, local Ollama with OpenAI shim) works by swapping OPENAI_BASE_URL.
"""

from __future__ import annotations

import json
import logging
import os
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from simready.copilot.tools import TOOL_SCHEMAS, dispatch_tool


EventCallback = Callable[[dict[str, Any]], None]


logger = logging.getLogger(__name__)


DEFAULT_SYSTEM_PROMPT = """\
You are SimReady Copilot, an AI assistant for FEA (finite element analysis) pre-processing.
You help mechanical engineers analyze CAD geometry, find manufacturability issues, and suggest
text-only fixes (no part modification — that comes later).

You have four tools:
- analyze_geometry(step_path): run SimReady's pipeline on a CAD file. Returns a structured
  summary: status, complexity tier, score.overall, geometry counts, body_count,
  severity_counts, and findings (top-N by severity). Use this first whenever the user
  references a CAD file.
- suggest_fixes(findings): rank text-only fix suggestions from a findings list.
  Pass the findings array from analyze_geometry verbatim. Returns suggestions +
  severity_counts.
- lookup_standard(query, top_k=3): semantic search over FEA / mechanical-engineering
  standards (NAFEMS, ASME, vendor whitepapers). Returns paragraphs with source filename
  and page number. Status may be "ok" / "no_index" / "empty_query".
- build_part(spec): generate a NEW STEP file from a typed parametric spec. Grammar:
  box(dx, dy, dz, at), cyl(r, h, at) [+Z axis], fuse(a, b), cut(a, b); dims in mm;
  a/b are 0-based indices of earlier steps; the last step is the returned part.
  Returns step_path on success. Use ONLY when the user asks you to CREATE a part.

Workflow rules:
- ALWAYS call analyze_geometry first when the user mentions a CAD file path.
- After analyze_geometry returns findings, call suggest_fixes to rank them.
- When the user asks you to CREATE / generate a part, call build_part first; after it
  returns step_path, ALWAYS call analyze_geometry(step_path) before describing the
  result. Treat ML defect predictions on generated parts as advisory, not blocking.
- Cite numbers (face count, score, severity counts) from tool output — never invent them.
- When citing a standard, quote the source (filename + page) returned by lookup_standard.
- If a tool returns {"error": ...} or status "no_index", surface it to the user plainly.
- Final answer format (use literal blank lines BETWEEN sections so Streamlit /
  markdown renders each as its own paragraph):
    1. One-line **Verdict** containing: status, numeric score (X/100), complexity tier,
       face_count, body_count. Format: `Verdict: <status> · score X/100 · <complexity> (<faces> faces, <bodies> bodies)`.
    2. Blank line, then `Issues:` header and a bullet list of top issues with severity tag.
    3. Blank line, then `Fixes:` header and a bullet list of fixes (1:1 with issues if possible).
    4. Blank line, then optional `Citations:` block when lookup_standard returned hits.
- Be concise. No filler, no apologies, no restating the question.

# Reference dialogues

## Example 1 — full triage on a CAD file
User: What's wrong with tests/data/grabcad/bracket_simple.STEP and how do I fix it?
Assistant (calls analyze_geometry, then suggest_fixes, then writes):
  Verdict: ReviewRecommended · score 68/100 · moderate complexity (148 faces, 1 body).

  Issues:
  - [Major] OpenBoundaries: 3 free edges along the top flange.
  - [Minor] ShortEdges: 7 sub-mm edges near fillets.

  Fixes:
  - Stitch the open boundary using OCC ShapeUpgrade_UnifySameDomain.
  - Merge short edges (tolerance 0.05 mm) before meshing.

## Example 2 — standards lookup, no file
User: What aspect ratio should my mesh elements stay under for linear-elastic FEA?
Assistant (calls lookup_standard("aspect ratio limits linear elastic mesh quality")):
  NAFEMS QA01 (p.4) recommends aspect ratio < 5 for linear-elastic stress recovery.

  Citations:
  - NAFEMS_QA01.pdf, page 4.

## Example 3 — graceful failure on bad path
User: Analyze /tmp/missing.step
Assistant (calls analyze_geometry, sees error="FileNotFound"):
  No file at /tmp/missing.step. Re-check the path, or upload via the UI.
"""


# Conservative default; multi-turn loop should rarely exceed a handful of rounds.
DEFAULT_MAX_ITERATIONS = 6
DEFAULT_MAX_RETRIES = 3
DEFAULT_INITIAL_BACKOFF = 1.0
DEFAULT_TOOL_RESULT_CHAR_LIMIT = 8000


@dataclass
class AgentResponse:
    """Result of a single agent run."""

    final_text: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    model: str = ""
    usage: dict[str, Any] = field(default_factory=dict)
    iterations: int = 0
    stop_reason: str = ""
    # Full message list at end of the run (system + user + assistant + tool
    # messages). Caller can pass this back as ``history`` to ``run`` for a
    # follow-up turn that preserves conversational context.
    messages: list[dict[str, Any]] = field(default_factory=list)


class CopilotAgent:
    """Multi-turn copilot agent. Loops until the assistant emits no tool_calls."""

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        system_prompt: str | None = None,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        initial_backoff: float = DEFAULT_INITIAL_BACKOFF,
        tool_result_char_limit: int = DEFAULT_TOOL_RESULT_CHAR_LIMIT,
    ) -> None:
        # Lazy import: openai is an optional dependency, only required at runtime.
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "openai package not installed. Run: pip install openai python-dotenv"
            ) from exc

        resolved_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not resolved_key:
            raise RuntimeError(
                "OPENAI_API_KEY not set. Create .env from .env.example, or pass api_key=..."
            )

        client_kwargs: dict[str, Any] = {"api_key": resolved_key}
        resolved_base = base_url or os.environ.get("OPENAI_BASE_URL")
        if resolved_base:
            client_kwargs["base_url"] = resolved_base

        self._client = OpenAI(**client_kwargs)
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        self.max_iterations = max_iterations
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.tool_result_char_limit = tool_result_char_limit

    def run(
        self,
        user_message: str,
        on_event: EventCallback | None = None,
        history: list[dict[str, Any]] | None = None,
    ) -> AgentResponse:
        """Drive a multi-turn tool-use conversation. Returns the final assistant text.

        Pass ``history`` (the ``messages`` field from a prior ``AgentResponse``) to
        continue a previous conversation — the new ``user_message`` is appended to it.
        Omit ``history`` for a fresh chat (system prompt is added automatically).

        If `on_event` is provided, it is called as the loop progresses with dicts of
        shape `{"type": <str>, ...}`. Event types:
          - "iteration_start"  {iteration}
          - "tool_call"        {iteration, name, arguments}
          - "tool_result"      {iteration, name, result}
          - "final_text"       {text, iterations, usage}
          - "max_iterations"   {iterations}
        Callback exceptions are logged and swallowed so observers cannot break a run.
        """
        if history:
            messages: list[dict[str, Any]] = list(history)
        else:
            messages = [{"role": "system", "content": self.system_prompt}]
        messages.append({"role": "user", "content": user_message})
        return self.run_messages(messages, on_event=on_event)

    def run_messages(
        self,
        messages: list[dict[str, Any]],
        on_event: EventCallback | None = None,
    ) -> AgentResponse:
        """Drive the tool-use loop over an already-built message list.

        ``messages`` is mutated in place as the loop appends assistant + tool
        replies. The final list is returned on ``AgentResponse.messages`` so the
        caller can persist conversational history across turns.
        """
        tool_calls_record: list[dict[str, Any]] = []
        tool_results_record: list[dict[str, Any]] = []
        usage_total: dict[str, Any] = {}

        stop_reason = "max_iterations"
        final_text = ""

        for iteration in range(1, self.max_iterations + 1):
            _emit(on_event, {"type": "iteration_start", "iteration": iteration})
            completion = self._completion_with_retry(messages)
            choice = completion.choices[0]
            msg = choice.message

            if completion.usage:
                _accumulate(usage_total, completion.usage.model_dump())

            tool_calls = msg.tool_calls or []
            if not tool_calls:
                final_text = msg.content or ""
                stop_reason = "stop"
                messages.append({"role": "assistant", "content": final_text})
                _emit(on_event, {
                    "type": "final_text",
                    "text": final_text,
                    "iterations": iteration,
                    "usage": dict(usage_total),
                })
                return AgentResponse(
                    final_text=final_text,
                    tool_calls=tool_calls_record,
                    tool_results=tool_results_record,
                    model=self.model,
                    usage=usage_total,
                    iterations=iteration,
                    stop_reason=stop_reason,
                    messages=messages,
                )

            messages.append({
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in tool_calls
                ],
            })

            for tc in tool_calls:
                name = tc.function.name
                args = tc.function.arguments
                _emit(on_event, {
                    "type": "tool_call",
                    "iteration": iteration,
                    "name": name,
                    "arguments": args,
                })
                result = dispatch_tool(name, args)
                tool_calls_record.append({"name": name, "arguments": args})
                tool_results_record.append({"name": name, "result_preview": _preview(result)})
                _emit(on_event, {
                    "type": "tool_result",
                    "iteration": iteration,
                    "name": name,
                    "result": result,
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(_truncate_for_llm(result, self.tool_result_char_limit)),
                })

        logger.warning("Agent loop hit max_iterations=%s without final text.", self.max_iterations)
        _emit(on_event, {"type": "max_iterations", "iterations": self.max_iterations})
        return AgentResponse(
            final_text=final_text,
            tool_calls=tool_calls_record,
            tool_results=tool_results_record,
            model=self.model,
            usage=usage_total,
            iterations=self.max_iterations,
            stop_reason=stop_reason,
            messages=messages,
        )

    def _completion_with_retry(self, messages: list[dict[str, Any]]) -> Any:
        """One chat completion request, retried on rate-limit / transient errors."""
        try:
            from openai import APIConnectionError, APITimeoutError, RateLimitError  # type: ignore
        except ImportError:  # pragma: no cover
            APIConnectionError = APITimeoutError = RateLimitError = Exception  # type: ignore

        backoff = self.initial_backoff
        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=TOOL_SCHEMAS,
                    tool_choice="auto",
                )
            except (RateLimitError, APIConnectionError, APITimeoutError) as exc:
                last_exc = exc
                if attempt == self.max_retries:
                    raise
                jitter = random.uniform(0, backoff * 0.25)
                sleep_for = backoff + jitter
                logger.warning(
                    "LLM call failed (%s), retry %d/%d in %.2fs",
                    type(exc).__name__,
                    attempt,
                    self.max_retries,
                    sleep_for,
                )
                time.sleep(sleep_for)
                backoff *= 2
        # Unreachable, but keeps the type checker happy.
        raise RuntimeError("retry loop exited without return") from last_exc


def _emit(callback: EventCallback | None, event: dict[str, Any]) -> None:
    """Fire an event callback, swallowing any exception so the loop never breaks."""
    if callback is None:
        return
    try:
        callback(event)
    except Exception:  # pragma: no cover — observer must not break agent
        logger.exception("on_event callback raised; ignoring.")


def _accumulate(total: dict[str, Any], more: dict[str, Any]) -> None:
    """Sum numeric usage fields across multiple completions."""
    for key, value in more.items():
        if isinstance(value, (int, float)):
            total[key] = (total.get(key, 0) or 0) + (value or 0)
        elif key not in total:
            total[key] = value


def _preview(result: dict[str, Any], char_limit: int = 200) -> str:
    """Short string preview of a tool result, for logging."""
    text = json.dumps(result, default=str)
    return text if len(text) <= char_limit else text[:char_limit] + "...[truncated]"


def _truncate_for_llm(
    result: dict[str, Any],
    max_chars: int = DEFAULT_TOOL_RESULT_CHAR_LIMIT,
) -> dict[str, Any]:
    """Trim large fields before feeding a tool result back to the LLM.

    Strategy: drop per-face score dicts first (biggest blobs), then ML internals,
    then cap findings list. Returns the trimmed dict; never raises.
    """
    serialized = json.dumps(result, default=str)
    if len(serialized) <= max_chars:
        return result

    trimmed = dict(result)
    for key in ("per_face_scores", "combined_per_face_scores"):
        if key in trimmed:
            trimmed[key] = "<omitted-for-context: per-face dict trimmed>"
    if isinstance(trimmed.get("ml"), dict):
        ml = dict(trimmed["ml"])
        ml["per_face_scores"] = "<omitted-for-context>"
        trimmed["ml"] = ml

    serialized = json.dumps(trimmed, default=str)
    if len(serialized) > max_chars and isinstance(trimmed.get("findings"), list):
        if len(trimmed["findings"]) > 20:
            trimmed["findings"] = trimmed["findings"][:20] + [
                {
                    "check": "TRUNCATED",
                    "severity": "Info",
                    "detail": f"{len(trimmed['findings']) - 20} more findings omitted.",
                }
            ]

    serialized = json.dumps(trimmed, default=str)
    if len(serialized) > max_chars and isinstance(trimmed.get("bodies"), list):
        if len(trimmed["bodies"]) > 5:
            trimmed["bodies"] = trimmed["bodies"][:5] + [
                {"note": f"{len(trimmed['bodies']) - 5} more bodies omitted."}
            ]
    return trimmed
