"""Tests for the SimReady Copilot agent (day 1 — single-turn loop).

These tests mock the OpenAI client entirely so they run offline. Live-API smoke
tests live in scripts/smoke_copilot.py and are NOT part of the pytest run.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest

from simready.copilot import agent as agent_module
from simready.copilot.agent import (
    DEFAULT_SYSTEM_PROMPT,
    CopilotAgent,
    _accumulate,
    _truncate_for_llm,
)


@dataclass
class _FakeUsage:
    prompt_tokens: int = 100
    completion_tokens: int = 50

    def model_dump(self) -> dict[str, Any]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
        }


@dataclass
class _FakeToolCall:
    id: str
    function: Any


@dataclass
class _FakeFunction:
    name: str
    arguments: str


@dataclass
class _FakeMessage:
    content: str | None = None
    tool_calls: list[_FakeToolCall] | None = None


@dataclass
class _FakeChoice:
    message: _FakeMessage


@dataclass
class _FakeCompletion:
    choices: list[_FakeChoice]
    usage: _FakeUsage | None = None


class _FakeCompletions:
    def __init__(self) -> None:
        self.responses: list[_FakeCompletion] = []
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> _FakeCompletion:
        self.calls.append(kwargs)
        return self.responses.pop(0)


class _FakeChat:
    def __init__(self) -> None:
        self.completions = _FakeCompletions()


class _FakeClient:
    def __init__(self, **_: Any) -> None:
        self.chat = _FakeChat()


@pytest.fixture
def fake_openai(monkeypatch: pytest.MonkeyPatch) -> type[_FakeClient]:
    """Patch openai.OpenAI to return our fake client class."""
    fake = _FakeClient

    class _FakeModule:
        OpenAI = fake

    monkeypatch.setitem(__import__("sys").modules, "openai", _FakeModule)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    return fake


def test_agent_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.setitem(
        __import__("sys").modules,
        "openai",
        type("M", (), {"OpenAI": _FakeClient})(),
    )
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        CopilotAgent()


def test_agent_no_tool_call_returns_direct_text(fake_openai: type[_FakeClient]) -> None:
    agent = CopilotAgent(model="test-model")
    agent._client.chat.completions.responses = [
        _FakeCompletion(
            choices=[_FakeChoice(message=_FakeMessage(content="Hello! I have no tools to call."))],
            usage=_FakeUsage(),
        )
    ]
    response = agent.run("Hi.")
    assert response.final_text == "Hello! I have no tools to call."
    assert response.tool_calls == []
    assert response.model == "test-model"


def test_agent_with_tool_call_executes_and_summarizes(fake_openai: type[_FakeClient]) -> None:
    agent = CopilotAgent(model="test-model")
    agent._client.chat.completions.responses = [
        _FakeCompletion(
            choices=[_FakeChoice(message=_FakeMessage(
                content=None,
                tool_calls=[_FakeToolCall(
                    id="call_1",
                    function=_FakeFunction(
                        name="suggest_fixes",
                        arguments=json.dumps({"findings": []}),
                    ),
                )],
            ))],
            usage=_FakeUsage(),
        ),
        _FakeCompletion(
            choices=[_FakeChoice(message=_FakeMessage(content="No findings — the part is clean."))],
            usage=_FakeUsage(),
        ),
    ]
    response = agent.run("Check this part.")
    assert response.final_text == "No findings — the part is clean."
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0]["name"] == "suggest_fixes"


def test_agent_propagates_tool_error_back_to_llm(fake_openai: type[_FakeClient]) -> None:
    agent = CopilotAgent(model="test-model")
    agent._client.chat.completions.responses = [
        _FakeCompletion(
            choices=[_FakeChoice(message=_FakeMessage(
                content=None,
                tool_calls=[_FakeToolCall(
                    id="call_1",
                    function=_FakeFunction(
                        name="analyze_geometry",
                        arguments=json.dumps({"step_path": "/nope/missing.step"}),
                    ),
                )],
            ))],
            usage=_FakeUsage(),
        ),
        _FakeCompletion(
            choices=[_FakeChoice(message=_FakeMessage(
                content="The file was not found at that path.",
            ))],
            usage=_FakeUsage(),
        ),
    ]
    response = agent.run("Analyze /nope/missing.step")
    second_call_messages = agent._client.chat.completions.calls[1]["messages"]
    tool_msg = next(m for m in second_call_messages if m["role"] == "tool")
    tool_payload = json.loads(tool_msg["content"])
    assert tool_payload.get("error") == "FileNotFound"


def test_agent_chains_multi_turn_tool_calls(fake_openai: type[_FakeClient]) -> None:
    """Turn 1: analyze_geometry. Turn 2: suggest_fixes. Turn 3: text-only summary."""
    agent = CopilotAgent(model="test-model")
    agent._client.chat.completions.responses = [
        _FakeCompletion(
            choices=[_FakeChoice(message=_FakeMessage(
                content=None,
                tool_calls=[_FakeToolCall(
                    id="call_1",
                    function=_FakeFunction(
                        name="suggest_fixes",
                        arguments=json.dumps({"findings": []}),
                    ),
                )],
            ))],
            usage=_FakeUsage(),
        ),
        _FakeCompletion(
            choices=[_FakeChoice(message=_FakeMessage(
                content=None,
                tool_calls=[_FakeToolCall(
                    id="call_2",
                    function=_FakeFunction(
                        name="lookup_standard",
                        arguments=json.dumps({"query": "mesh quality"}),
                    ),
                )],
            ))],
            usage=_FakeUsage(),
        ),
        _FakeCompletion(
            choices=[_FakeChoice(message=_FakeMessage(
                content="Final answer combining tool results.",
            ))],
            usage=_FakeUsage(),
        ),
    ]
    response = agent.run("Analyze and explain.")
    assert response.iterations == 3
    assert response.stop_reason == "stop"
    assert [c["name"] for c in response.tool_calls] == ["suggest_fixes", "lookup_standard"]
    assert response.final_text == "Final answer combining tool results."
    # Usage aggregates across all three completions.
    assert response.usage["prompt_tokens"] == 300
    assert response.usage["completion_tokens"] == 150


def test_agent_stops_at_max_iterations_when_model_keeps_calling_tools(
    fake_openai: type[_FakeClient],
) -> None:
    agent = CopilotAgent(model="test-model", max_iterations=2)
    # Both completions request a tool — loop should bail after 2 rounds.
    tool_call_response = _FakeCompletion(
        choices=[_FakeChoice(message=_FakeMessage(
            content=None,
            tool_calls=[_FakeToolCall(
                id="call_x",
                function=_FakeFunction(
                    name="suggest_fixes",
                    arguments=json.dumps({"findings": []}),
                ),
            )],
        ))],
        usage=_FakeUsage(),
    )
    agent._client.chat.completions.responses = [tool_call_response, tool_call_response]
    response = agent.run("Loop forever.")
    assert response.iterations == 2
    assert response.stop_reason == "max_iterations"
    assert response.final_text == ""


def test_agent_retries_on_rate_limit_then_succeeds(
    monkeypatch: pytest.MonkeyPatch, fake_openai: type[_FakeClient]
) -> None:
    class _RateLimitError(Exception):
        pass

    class _ConnError(Exception):
        pass

    class _TimeoutError(Exception):
        pass

    fake_openai_module = sys_module().modules["openai"]
    fake_openai_module.RateLimitError = _RateLimitError  # type: ignore[attr-defined]
    fake_openai_module.APIConnectionError = _ConnError  # type: ignore[attr-defined]
    fake_openai_module.APITimeoutError = _TimeoutError  # type: ignore[attr-defined]

    agent = CopilotAgent(model="test-model", max_retries=3, initial_backoff=0.0)

    success_completion = _FakeCompletion(
        choices=[_FakeChoice(message=_FakeMessage(content="Done."))],
        usage=_FakeUsage(),
    )

    calls = {"n": 0}

    def flaky_create(**_: Any) -> _FakeCompletion:
        calls["n"] += 1
        if calls["n"] == 1:
            raise _RateLimitError("rate limit hit")
        return success_completion

    monkeypatch.setattr(agent._client.chat.completions, "create", flaky_create)
    monkeypatch.setattr(agent_module.time, "sleep", lambda _t: None)

    response = agent.run("Hi.")
    assert response.final_text == "Done."
    assert calls["n"] == 2


def test_agent_raises_after_exhausting_retries(
    monkeypatch: pytest.MonkeyPatch, fake_openai: type[_FakeClient]
) -> None:
    class _RateLimitError(Exception):
        pass

    fake_openai_module = sys_module().modules["openai"]
    fake_openai_module.RateLimitError = _RateLimitError  # type: ignore[attr-defined]
    fake_openai_module.APIConnectionError = type("E1", (Exception,), {})  # type: ignore[attr-defined]
    fake_openai_module.APITimeoutError = type("E2", (Exception,), {})  # type: ignore[attr-defined]

    agent = CopilotAgent(model="test-model", max_retries=2, initial_backoff=0.0)

    def always_fail(**_: Any) -> _FakeCompletion:
        raise _RateLimitError("nope")

    monkeypatch.setattr(agent._client.chat.completions, "create", always_fail)
    monkeypatch.setattr(agent_module.time, "sleep", lambda _t: None)

    with pytest.raises(_RateLimitError):
        agent.run("Hi.")


def sys_module() -> Any:
    """Re-imported each call so monkey-patches on `sys.modules` are picked up."""
    import sys as _sys
    return _sys


def test_accumulate_sums_numeric_usage_fields_and_keeps_strings_first_seen() -> None:
    total: dict[str, Any] = {}
    _accumulate(total, {"prompt_tokens": 10, "completion_tokens": 5, "model": "m1"})
    _accumulate(total, {"prompt_tokens": 20, "completion_tokens": 0, "model": "m2"})
    assert total["prompt_tokens"] == 30
    assert total["completion_tokens"] == 5
    assert total["model"] == "m1"  # first-seen wins for non-numeric


def test_default_system_prompt_advertises_three_tools_and_few_shot_examples() -> None:
    prompt = DEFAULT_SYSTEM_PROMPT
    for tool_name in ("analyze_geometry", "suggest_fixes", "lookup_standard"):
        assert tool_name in prompt
    assert "Reference dialogues" in prompt
    assert "Example 1" in prompt
    assert "Example 2" in prompt
    assert "Example 3" in prompt
    # Final-answer schema must be spelled out so the model copies it.
    assert "Verdict" in prompt
    assert "severity_counts" in prompt


def test_truncate_for_llm_strips_large_per_face_dicts() -> None:
    big_report = {
        "findings": [{"check": "X", "severity": "Minor"}],
        "per_face_scores": {i: 0.5 for i in range(500)},
        "combined_per_face_scores": {i: 0.7 for i in range(500)},
        "ml": {"per_face_scores": {i: 0.3 for i in range(500)}, "model_name": "test"},
    }
    trimmed = _truncate_for_llm(big_report, max_chars=2000)
    assert isinstance(trimmed["per_face_scores"], str)
    assert isinstance(trimmed["combined_per_face_scores"], str)
    assert isinstance(trimmed["ml"]["per_face_scores"], str)
    # findings preserved when small
    assert trimmed["findings"][0]["check"] == "X"
