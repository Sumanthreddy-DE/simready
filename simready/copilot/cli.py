"""Terminal entry point for the SimReady Copilot.

Example:
    python -m simready.copilot.cli tests/data/grabcad/bracket_simple.STEP \\
        "What manufacturing issues does this part have?"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # pragma: no cover
    pass

from simready.copilot.agent import CopilotAgent


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
    return parser


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

    response = agent.run(user_message)

    print("=" * 60)
    print(f"MODEL: {response.model}")
    if response.tool_calls:
        print("\nTOOL CALLS:")
        for tc in response.tool_calls:
            print(f"  - {tc['name']}({tc['arguments']})")
    print("\nRESPONSE:")
    print(response.final_text)
    if response.usage:
        print(f"\nUSAGE: {response.usage}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
