"""Thin script entry point for prompt-to-STEP generation."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from simready.gen.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
