"""Terminal entry point for the SimReady Copilot.

Example:
    python -m simready.copilot.cli tests/data/grabcad/bracket_simple.STEP \\
        "What manufacturing issues does this part have?"
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # pragma: no cover
    pass

from simready.copilot.agent import AgentResponse, CopilotAgent
from simready.copilot.renderer import PlainRenderer, RichRenderer


DEFAULT_SESSION_DIR = Path("data/copilot_sessions")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="SimReady Copilot — ask questions about a CAD file.",
    )
    parser.add_argument(
        "step_path",
        type=str,
        help="Path to a STEP / STP file. The copilot will pass this to analyze_geometry.",
    )
    parser.add_argument(
        "question",
        type=str,
        nargs="?",
        default="What manufacturing issues does this part have? Give me your top fix suggestions.",
        help="Natural-language question. Defaults to a generic issue scan.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Override the model name. Defaults to env OPENAI_MODEL or gpt-4o-mini.",
    )
    parser.add_argument(
        "--no-rich",
        action="store_true",
        help="Disable rich-formatted output (plain text fallback).",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Do not persist session JSON to data/copilot_sessions/.",
    )
    parser.add_argument(
        "--session-dir",
        type=Path,
        default=DEFAULT_SESSION_DIR,
        help=f"Where to persist session JSON (default: {DEFAULT_SESSION_DIR}).",
    )
    return parser


def _save_session(
    session_dir: Path,
    *,
    model: str,
    step_path: str,
    question: str,
    response: AgentResponse,
) -> Path:
    session_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_part = Path(step_path).stem.replace(" ", "_")
    out = session_dir / f"{timestamp}_{safe_part}.json"
    payload: dict[str, Any] = {
        "timestamp": timestamp,
        "model": model,
        "step_path": str(step_path),
        "question": question,
        "iterations": response.iterations,
        "stop_reason": response.stop_reason,
        "tool_calls": response.tool_calls,
        "tool_results": response.tool_results,
        "final_text": response.final_text,
        "usage": response.usage,
    }
    out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    step_path = Path(args.step_path).expanduser().resolve()
    if not step_path.exists():
        print(f"ERROR: file not found: {step_path}", file=sys.stderr)
        return 2

    user_message = f"Analyze the CAD file at `{step_path}`. {args.question}"

    try:
        agent = CopilotAgent(model=args.model)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3

    renderer = PlainRenderer() if args.no_rich else RichRenderer()
    renderer.header(agent.model, str(step_path), args.question)

    response = agent.run(user_message, on_event=renderer)

    if not args.no_save:
        try:
            saved = _save_session(
                args.session_dir,
                model=agent.model,
                step_path=str(step_path),
                question=args.question,
                response=response,
            )
            if args.no_rich:
                print(f"\n[session saved] {saved}")
            else:
                from rich import print as rprint
                rprint(f"\n[dim][session saved] {saved}[/dim]")
        except OSError as exc:
            print(f"WARN: could not save session: {exc}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
