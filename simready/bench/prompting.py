"""System prompt and tool schema shared by every benchmarked model.

The tool schema is the product's own ``build_part`` schema (single source of
truth), minus the agent-only sentence about calling analyze_geometry and the
timeout parameter. Their combined hash goes in every run header, so a prompt
change can never be mixed into an existing run.
"""

from __future__ import annotations

import copy
import hashlib
import json

from simready.gen.spec import BUILD_PART_TOOL_SCHEMA

_AGENT_ONLY_MARKER = "After calling this, ALWAYS call analyze_geometry"

SYSTEM_PROMPT = (
    "You design mechanical parts as solid models. Answer each request with exactly one "
    "build_part call whose spec builds the requested part; dimensions are in millimetres. "
    "Make sensible engineering choices for anything the request leaves open. If your "
    "client cannot call tools, reply with only the JSON object {\"steps\": [...]}. "
    "If the part cannot be built with these operations, say so instead of calling the tool."
)


def _bench_tool() -> dict:
    tool = copy.deepcopy(BUILD_PART_TOOL_SCHEMA)
    description = tool["function"]["description"]
    if _AGENT_ONLY_MARKER not in description:
        raise RuntimeError("build_part description changed; update _AGENT_ONLY_MARKER in prompting.py")
    tool["function"]["description"] = description.split(_AGENT_ONLY_MARKER)[0].strip()
    tool["function"]["parameters"]["properties"].pop("timeout_seconds", None)
    return tool


BUILD_PART_TOOL = _bench_tool()


ARMS = ("dsl-v1", "dsl-v2", "build123d")


def dsl_of(arm: str) -> str | None:
    if arm not in ARMS:
        raise ValueError(f"unknown arm {arm!r}; one of {ARMS}")
    return None if arm == "build123d" else arm.removeprefix("dsl-")


def bench_tool(arm: str = "dsl-v1") -> dict | None:
    dsl = dsl_of(arm)
    if dsl is None:
        return None
    if dsl == "v1":
        return BUILD_PART_TOOL
    from simready.gen.dsl import tool_schema
    return copy.deepcopy(tool_schema(dsl))  # v2 schema carries no agent-only sentence and no timeout


def system_prompt(arm: str = "dsl-v1") -> str:
    if dsl_of(arm) is None:
        from simready.bench.code_arm import CODE_SYSTEM_PROMPT
        return CODE_SYSTEM_PROMPT
    return SYSTEM_PROMPT


def build_messages(prompt: str, arm: str = "dsl-v1") -> list[dict]:
    return [{"role": "system", "content": system_prompt(arm)}, {"role": "user", "content": prompt}]


def system_prompt_sha256(arm: str = "dsl-v1") -> str:
    tool = bench_tool(arm)
    payload = {"system": system_prompt(arm), "tool": tool} if tool is not None else {"system": system_prompt(arm), "arm": arm}
    blob = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
