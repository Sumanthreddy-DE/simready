#!/usr/bin/env python3
"""Placeholder notes for assembling a SimJEB validation set."""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a local SimJEB validation set folder")
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    readme = args.output_dir / "README.txt"
    readme.write_text(
        "Place downloaded SimJEB bracket STEP models in this directory.\n"
        "Suggested validation workflow:\n"
        "1. Collect 5-10 representative bracket models.\n"
        "2. Run SimReady with --json and --html for each model.\n"
        "3. Save results under docs/validation_results/.\n"
        "4. Record false positives, false negatives, and mesh-relevance notes.\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
