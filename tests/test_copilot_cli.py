"""Tests for simready/copilot/cli.py.

The OpenAI client and the agent loop are mocked. We exercise the CLI argv
parsing, renderer dispatch, missing-file path, missing-key path, and the
session-persistence side effect.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from simready.copilot import cli as cli_module
from simready.copilot.agent import AgentResponse


@pytest.fixture
def fake_step(tmp_path: Path) -> Path:
    p = tmp_path / "fake.STEP"
    p.write_text("not a real STEP file", encoding="utf-8")
    return p


class _FakeAgent:
    """Stand-in for CopilotAgent. Captures init args + run args."""

    init_args: dict[str, Any] = {}
    last_user_message: str = ""
    last_callback: Any = None
    response: AgentResponse = AgentResponse(
        final_text="ok",
        tool_calls=[{"name": "suggest_fixes", "arguments": "{}"}],
        tool_results=[{"name": "suggest_fixes", "result_preview": "..."}],
        model="fake-model",
        usage={"prompt_tokens": 10, "completion_tokens": 5},
        iterations=1,
        stop_reason="stop",
    )

    def __init__(self, model: str | None = None, **kwargs: Any) -> None:
        type(self).init_args = {"model": model, **kwargs}
        self.model = model or "fake-model"

    def run(self, user_message: str, on_event: Any = None) -> AgentResponse:
        type(self).last_user_message = user_message
        type(self).last_callback = on_event
        # Drive a couple of events so the renderer code paths execute.
        if on_event:
            on_event({"type": "iteration_start", "iteration": 1})
            on_event({
                "type": "tool_call",
                "iteration": 1,
                "name": "suggest_fixes",
                "arguments": "{}",
            })
            on_event({
                "type": "tool_result",
                "iteration": 1,
                "name": "suggest_fixes",
                "result": {"suggestions": [], "severity_counts": {"Critical": 0}},
            })
            on_event({
                "type": "final_text",
                "text": "ok",
                "iterations": 1,
                "usage": {"prompt_tokens": 10},
            })
        return type(self).response


@pytest.fixture
def patched_agent(monkeypatch: pytest.MonkeyPatch) -> type[_FakeAgent]:
    monkeypatch.setattr(cli_module, "CopilotAgent", _FakeAgent)
    return _FakeAgent


def test_cli_returns_2_when_step_missing(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli_module.main(["/nope/missing.STEP", "what?"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "file not found" in err.lower()


def test_cli_returns_3_when_agent_init_raises(
    monkeypatch: pytest.MonkeyPatch, fake_step: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    class _Boom:
        def __init__(self, *_: Any, **__: Any) -> None:
            raise RuntimeError("OPENAI_API_KEY not set.")

    monkeypatch.setattr(cli_module, "CopilotAgent", _Boom)
    rc = cli_module.main([str(fake_step), "?"])
    assert rc == 3
    assert "OPENAI_API_KEY" in capsys.readouterr().err


def test_cli_runs_agent_and_persists_session(
    patched_agent: type[_FakeAgent], fake_step: Path, tmp_path: Path
) -> None:
    session_dir = tmp_path / "sessions"
    rc = cli_module.main([
        str(fake_step), "What's wrong?",
        "--no-rich",
        "--session-dir", str(session_dir),
    ])
    assert rc == 0
    assert "What's wrong?" in patched_agent.last_user_message
    assert str(fake_step.resolve()) in patched_agent.last_user_message

    saved = list(session_dir.glob("*.json"))
    assert len(saved) == 1
    payload = json.loads(saved[0].read_text(encoding="utf-8"))
    assert payload["model"] == "fake-model"
    assert payload["question"] == "What's wrong?"
    assert payload["final_text"] == "ok"
    assert payload["iterations"] == 1
    assert payload["tool_calls"] == [{"name": "suggest_fixes", "arguments": "{}"}]


def test_cli_no_save_skips_session_file(
    patched_agent: type[_FakeAgent], fake_step: Path, tmp_path: Path
) -> None:
    session_dir = tmp_path / "sessions"
    rc = cli_module.main([
        str(fake_step), "?",
        "--no-rich", "--no-save",
        "--session-dir", str(session_dir),
    ])
    assert rc == 0
    assert not session_dir.exists() or list(session_dir.glob("*.json")) == []


def test_cli_default_question_used_when_omitted(
    patched_agent: type[_FakeAgent], fake_step: Path, tmp_path: Path
) -> None:
    rc = cli_module.main([
        str(fake_step),
        "--no-rich", "--no-save",
        "--session-dir", str(tmp_path / "s"),
    ])
    assert rc == 0
    assert "manufacturing issues" in patched_agent.last_user_message.lower()


def test_cli_passes_callback_to_agent(
    patched_agent: type[_FakeAgent], fake_step: Path, tmp_path: Path
) -> None:
    rc = cli_module.main([
        str(fake_step),
        "--no-rich", "--no-save",
        "--session-dir", str(tmp_path / "s"),
    ])
    assert rc == 0
    assert callable(patched_agent.last_callback)
