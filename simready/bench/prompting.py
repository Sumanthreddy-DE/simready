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


def build_messages(prompt: str) -> list[dict]:
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}]


def system_prompt_sha256() -> str:
    blob = json.dumps({"system": SYSTEM_PROMPT, "tool": BUILD_PART_TOOL}, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
