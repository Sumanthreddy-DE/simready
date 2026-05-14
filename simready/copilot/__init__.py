"""SimReady LLM Copilot — tool-orchestrated FEA pre-processing assistant.

Path C wk-1 scaffolding. See docs/exec-plans/path-c-4week.md for build plan.
"""

from simready.copilot.agent import CopilotAgent, AgentResponse
from simready.copilot.tools import TOOL_SCHEMAS, dispatch_tool

__all__ = [
    "CopilotAgent",
    "AgentResponse",
    "TOOL_SCHEMAS",
    "dispatch_tool",
]
