#!/usr/bin/env python3
"""Placeholder helper for Fusion360 Gallery dataset setup."""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Document Fusion360 Gallery download expectations")
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    readme = args.output_dir / "README.txt"
    readme.write_text(
        "SimReady Phase 2 expects a local subset of Fusion360 Gallery STEP files here.\n"
        "Suggested workflow:\n"
        "1. Download a 100-500 model subset focused on bracket/mounting categories.\n"
        "2. Place raw STEP files under this directory.\n"
        "3. Run scripts/auto_label.py <input_dir> <output_dir> to generate graph + label pairs.\n"
        "4. Do not commit dataset artifacts to git.\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
