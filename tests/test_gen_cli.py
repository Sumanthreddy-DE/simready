"""Offline generation CLI contract, with real STEP building and analysis."""

import json
import os
import ctypes

import pytest

from simready.copilot.agent import AgentResponse
from simready.gen import cli
from simready.gen.build import build_part


DEMO_SPEC = {
    "steps": [
        {"op": "box", "dx": 80, "dy": 60, "dz": 10},
        {"op": "cyl", "r": 5, "h": 12, "at": [40, 30, -1]},
        {"op": "cut", "a": 0, "b": 1},
    ]
}
PROMPT = "Create an 80 x 60 x 10 mm plate with a centered 10 mm through-hole."


@pytest.fixture
def built(tmp_path):
    result = build_part(DEMO_SPEC, output_dir=tmp_path)
    assert result["occ_valid"], result
    return result


def fake_agent(monkeypatch, results):
    class FakeAgent:
        def __init__(self, model=None):
            self.model = model or "offline-model"

        def run(self, prompt, on_event):
            # Both Python and native/subprocess output must stay off JSON stdout.
            print("Python tool progress", flush=True)
            os.write(1, b"Native tool progress\n")
            for iteration, result in enumerate(results, 1):
                on_event({"type": "tool_call", "iteration": iteration,
                          "name": "build_part", "arguments": json.dumps({"spec": DEMO_SPEC})})
                on_event({"type": "tool_result", "iteration": iteration,
                          "name": "build_part", "result": result})
            return AgentResponse(final_text="Generated plate.", model=self.model, iterations=3)

    monkeypatch.setenv("OPENAI_API_KEY", "offline-test-key")
    monkeypatch.setattr(cli, "CopilotAgent", FakeAgent)


def test_success_json_analyzes_exact_built_step(monkeypatch, built, capfd):
    fake_agent(monkeypatch, [built])
    capfd.readouterr()
    assert cli.main([PROMPT, "--model", "test-model", "--json"]) == 0
    out, err = capfd.readouterr()
    result = json.loads(out)
    assert set(result) == {"prompt", "model", "ok", "step_path", "spec", "occ_valid",
                           "faces", "analysis_status", "score", "iterations", "error"}
    assert result["ok"] is True
    assert result["faces"] == 7
    assert result["step_path"] == built["step_path"]
    assert result["spec"] == DEMO_SPEC
    assert result["model"] == "test-model"
    assert result["score"] is not None
    assert result["analysis_status"] is not None
    assert result["error"] is None
    assert "Generated plate." in err
    assert "Native tool progress" in err


def test_later_failure_does_not_fall_back(monkeypatch, built, capfd):
    fake_agent(monkeypatch, [built, {"occ_valid": False, "error": "invalid final spec"}])
    capfd.readouterr()
    assert cli.main([PROMPT, "--json"]) == 1
    result = json.loads(capfd.readouterr().out)
    assert result["ok"] is False
    assert result["step_path"] is None
    assert "invalid final spec" in result["error"]


def test_no_build_is_failure(monkeypatch, capfd):
    fake_agent(monkeypatch, [])
    assert cli.main([PROMPT, "--json"]) == 1
    result = json.loads(capfd.readouterr().out)
    assert result["ok"] is False
    assert result["error"]


def test_missing_key(monkeypatch, capfd):
    monkeypatch.setattr(cli, "load_dotenv", lambda **kwargs: None)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert cli.main([PROMPT, "--json"]) == 2
    out, err = capfd.readouterr()
    assert json.loads(out)["ok"] is False
    assert "OPENAI_API_KEY" in err and ".env.example" in err
    assert len(err.splitlines()) == 1


def test_failed_analysis_is_failure(monkeypatch, built, capfd):
    fake_agent(monkeypatch, [built])

    def failed_analysis(path, *, timeout_seconds):
        assert path == built["step_path"]
        assert timeout_seconds == 9
        return {"ok": False, "status": "InvalidInput", "error": "analysis timed out"}

    monkeypatch.setattr(cli, "analyze_generated_part", failed_analysis)
    capfd.readouterr()
    assert cli.main([PROMPT, "--timeout", "9", "--json"]) == 1
    result = json.loads(capfd.readouterr().out)
    assert result["ok"] is False
    assert result["analysis_status"] == "InvalidInput"
    assert result["error"] == "analysis timed out"


def test_human_output_ends_with_three_line_summary(monkeypatch, built, capfd):
    fake_agent(monkeypatch, [built])
    capfd.readouterr()
    assert cli.main([PROMPT]) == 0
    lines = capfd.readouterr().out.strip().splitlines()
    assert lines[0] == "Generated plate."
    assert lines[-3] == f"STEP: {built['step_path']}"
    assert "7" in lines[-2] and "True" in lines[-2]
    assert "Analysis:" in lines[-1] and "score" in lines[-1]


def test_agent_exception_is_json_failure(monkeypatch, capfd):
    fake_agent(monkeypatch, [])

    def broken_run(self, prompt, on_event):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(cli.CopilotAgent, "run", broken_run)
    assert cli.main([PROMPT, "--json"]) == 1
    result = json.loads(capfd.readouterr().out)
    assert result["ok"] is False
    assert result["error"] == "provider unavailable"


@pytest.mark.skipif(
    os.name == "nt",
    reason="simulates OCC's buffered stdio with msvcrt.printf, but Python and OCC use the "
           "UCRT on Windows, so the simulated text never reaches either captured stream; a "
           "live Windows --json run (2026-11-03) printed one clean JSON object",
)
def test_buffered_native_output_cannot_leak_after_json(monkeypatch, capfd):
    fake_agent(monkeypatch, [])
    native = ctypes.CDLL("msvcrt" if os.name == "nt" else None)

    def buffered_run(self, prompt, on_event):
        native.printf(b"Buffered native tool output\n")
        return AgentResponse(final_text="No build.", model=self.model)

    monkeypatch.setattr(cli.CopilotAgent, "run", buffered_run)
    assert cli.main([PROMPT, "--json"]) == 1
    native.fflush(None)  # Simulate native cleanup at process exit.
    out, err = capfd.readouterr()
    assert json.loads(out)["ok"] is False
    assert "Buffered native tool output" in err
