"""Prompt-to-STEP CLI using the copilot and exact final-artifact analysis."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
from contextlib import contextmanager, redirect_stdout
from pathlib import Path
from typing import Any, Callable, Iterator

from dotenv import load_dotenv

from simready.copilot.agent import CopilotAgent
from simready.gen.verify import analyze_generated_part, select_final_build

DEFAULT_TIMEOUT = 120
_REPO_ROOT = Path(__file__).resolve().parents[2]


@contextmanager
def _tool_output_to_stderr() -> Iterator[None]:
    """Redirect Python, OCC and inherited subprocess stdout; restore even on error."""
    sys.stdout.flush()
    saved_stdout = os.dup(1)
    try:
        os.dup2(sys.stderr.fileno(), 1)
        with redirect_stdout(sys.stderr):
            yield
    finally:
        sys.stderr.flush()
        # OCC uses buffered C stdio, which otherwise flushes at process exit
        # after fd 1 has been restored and the JSON has already been emitted.
        ctypes.CDLL("msvcrt" if os.name == "nt" else None).fflush(None)
        os.dup2(saved_stdout, 1)
        os.close(saved_stdout)


def _empty_result(prompt: str, model: str | None) -> dict[str, Any]:
    return {
        "prompt": prompt,
        "model": model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        "ok": False,
        "step_path": None,
        "spec": None,
        "occ_valid": None,
        "faces": None,
        "analysis_status": None,
        "score": None,
        "iterations": None,
        "error": None,
    }


def generate(
    prompt: str, *, model: str | None = None, timeout: int = DEFAULT_TIMEOUT
) -> dict[str, Any]:
    """Generate and analyze the terminal STEP; diagnostics/prose go to stderr.

    ``timeout`` bounds the final independent analysis, in seconds. The copilot's
    existing provider retries and tool-specific timeouts remain in effect.
    """
    return _generate(prompt, model, timeout, lambda text: print(text, file=sys.stderr))


def _generate(
    prompt: str, model: str | None, timeout: int, on_text: Callable[[str], None]
) -> dict[str, Any]:
    load_dotenv(dotenv_path=_REPO_ROOT / ".env")
    result = _empty_result(prompt, model)
    if not os.environ.get("OPENAI_API_KEY"):
        result["error"] = "OPENAI_API_KEY not set. Create .env from .env.example."
        return result
    if timeout <= 0:
        result["error"] = "timeout must be a positive number of seconds"
        return result

    build_calls: list[dict[str, Any]] = []

    def on_event(event: dict[str, Any]) -> None:
        if event.get("name") != "build_part":
            return
        if event["type"] == "tool_call":
            build_calls.append({"arguments": event["arguments"],
                                "iteration": event["iteration"], "result": None})
        elif event["type"] == "tool_result":
            for call in reversed(build_calls):
                if call["iteration"] == event["iteration"] and call["result"] is None:
                    call["result"] = event["result"]
                    break
        print(f"build_part: {event['type']}", file=sys.stderr)

    try:
        with _tool_output_to_stderr():
            agent = CopilotAgent(model=model)
            result["model"] = agent.model
            response = agent.run(prompt, on_event=on_event)
            result["iterations"] = response.iterations
            on_text(response.final_text)
            final = select_final_build(build_calls)
            if final is None:
                failed = (build_calls[-1].get("result") or {}) if build_calls else {}
                result["error"] = failed.get("error") or "No final OCC-valid build_part result."
                return result
            built = final["result"]
            result.update(step_path=final["step_path"], spec=final["spec"],
                          occ_valid=built.get("occ_valid"), faces=built.get("faces"))
            if not result["step_path"] or not Path(result["step_path"]).is_file():
                result["error"] = "Final STEP file is missing."
                return result
            analysis = analyze_generated_part(result["step_path"], timeout_seconds=timeout)
            result["analysis_status"] = analysis.get("status")
            result["score"] = ((analysis.get("analysis") or {}).get("score") or {}).get("overall")
            result["ok"] = bool(analysis.get("ok"))
            if not result["ok"]:
                result["error"] = analysis.get("error") or "Final STEP analysis failed."
    except Exception as exc:
        result["ok"] = False
        result["error"] = str(exc)
    return result


def main(argv: list[str] | None = None) -> int:
    """Run prompt-to-STEP generation and return a shell exit code."""
    parser = argparse.ArgumentParser(description="Generate a STEP part and analyze it.")
    parser.add_argument("prompt")
    parser.add_argument("--model", default=None)
    parser.add_argument("--json", action="store_true", help="Emit one JSON object on stdout.")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                        help="Final independent analysis timeout in seconds (default: 120).")
    args = parser.parse_args(argv)
    final_text: list[str] = []
    result = _generate(args.prompt, args.model, args.timeout, final_text.append)
    missing_key = not os.environ.get("OPENAI_API_KEY")
    if args.json:
        if final_text:
            print(final_text[0], file=sys.stderr)
        print(json.dumps(result))
    else:
        if final_text:
            print(final_text[0])
        print(f"STEP: {result['step_path']}")
        print(f"Faces: {result['faces']} | OCC valid: {result['occ_valid']}")
        print(f"Analysis: {result['analysis_status']} | score: {result['score']}")
    if result["error"]:
        print(result["error"], file=sys.stderr)
    return 2 if missing_key else (0 if result["ok"] else 1)


if __name__ == "__main__":
    raise SystemExit(main())
