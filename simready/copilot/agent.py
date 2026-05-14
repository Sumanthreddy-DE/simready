"""SimReady Copilot agent — OpenAI-compatible tool-use loop.

Day 1: single-turn execution (one tool call, one summary). Multi-turn comes day 2.
The client is OpenAI-compatible so any provider (OpenAI, OpenRouter, Anthropic-via-proxy,
local Ollama with OpenAI shim) works by swapping OPENAI_BASE_URL.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from simready.copilot.tools import TOOL_SCHEMAS, dispatch_tool


DEFAULT_SYSTEM_PROMPT = """\
You are SimReady Copilot, an AI assistant for FEA (finite element analysis) pre-processing.
You help mechanical engineers analyze CAD geometry, find manufacturability issues, and suggest
text-only fixes (no part modification — that comes later).

You have three tools:
- analyze_geometry(step_path): run SimReady's pipeline on a CAD file. Use this first
  whenever the user references or uploads a CAD file.
- suggest_fixes(findings): get ranked text-only fix suggestions from a findings list.
- lookup_standard(query): search FEA / mechanical-engineering standards (stubbed in day 1).

Rules:
- ALWAYS call analyze_geometry first when the user mentions a CAD file path.
- Cite numbers (face count, score, severity counts) from tool output — never invent.
- Keep responses concise. Engineers prefer signal over filler.
- If a tool returns an error, surface it to the user with a recovery suggestion.
"""


@dataclass
class AgentResponse:
    """Result of a single agent run."""

    final_text: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    model: str = ""
    usage: dict[str, Any] = field(default_factory=dict)


class CopilotAgent:
    """Single-turn copilot agent (day 1). Multi-turn loop in day 2."""

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        system_prompt: str | None = None,
    ) -> None:
        # Lazy import: openai is optional dependency, only required when running the agent.
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

    def run(self, user_message: str) -> AgentResponse:
        """One round: model picks a tool, we execute it, model summarizes."""
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_message},
        ]

        first = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
        )
        first_msg = first.choices[0].message
        usage = first.usage.model_dump() if first.usage else {}

        if not first_msg.tool_calls:
            return AgentResponse(
                final_text=first_msg.content or "",
                model=self.model,
                usage=usage,
            )

        tool_calls_record: list[dict[str, Any]] = []
        tool_results_record: list[dict[str, Any]] = []
        messages.append({
            "role": "assistant",
            "content": first_msg.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in first_msg.tool_calls
            ],
        })

        for tc in first_msg.tool_calls:
            name = tc.function.name
            args = tc.function.arguments
            result = dispatch_tool(name, args)
            tool_calls_record.append({"name": name, "arguments": args})
            tool_results_record.append({"name": name, "result_preview": _preview(result)})
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(_truncate_for_llm(result)),
            })

        second = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="none",
        )
        second_msg = second.choices[0].message
        if second.usage:
            for k, v in second.usage.model_dump().items():
                usage[k] = (usage.get(k, 0) or 0) + (v or 0)

        return AgentResponse(
            final_text=second_msg.content or "",
            tool_calls=tool_calls_record,
            tool_results=tool_results_record,
            model=self.model,
            usage=usage,
        )


def _preview(result: dict[str, Any], char_limit: int = 200) -> str:
    """Short string preview of a tool result, for logging."""
    text = json.dumps(result, default=str)
    return text if len(text) <= char_limit else text[:char_limit] + "...[truncated]"


def _truncate_for_llm(result: dict[str, Any], max_chars: int = 8000) -> dict[str, Any]:
    """Pass tool result back to LLM, truncating large fields. Naive day-1 strategy."""
    serialized = json.dumps(result, default=str)
    if len(serialized) <= max_chars:
        return result

    trimmed = dict(result)
    # Largest blobs in the analyze_geometry report: per_face_scores, combined_per_face_scores
    for key in ("per_face_scores", "combined_per_face_scores"):
        if key in trimmed:
            trimmed[key] = "<omitted-for-context: scored per-face dict trimmed>"
    if "ml" in trimmed and isinstance(trimmed["ml"], dict):
        ml = dict(trimmed["ml"])
        ml["per_face_scores"] = "<omitted-for-context>"
        trimmed["ml"] = ml

    # If still too large, truncate findings list to top 20
    serialized = json.dumps(trimmed, default=str)
    if len(serialized) > max_chars and isinstance(trimmed.get("findings"), list):
        if len(trimmed["findings"]) > 20:
            trimmed["findings"] = trimmed["findings"][:20] + [
                {"check": "TRUNCATED", "severity": "Info", "detail": f"{len(trimmed['findings']) - 20} more findings omitted."}
            ]
    return trimmed
