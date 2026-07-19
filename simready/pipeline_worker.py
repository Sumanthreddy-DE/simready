"""Subprocess worker behind ``simready.pipeline.analyze_file_safe``.

Runs the full analysis and writes the report as JSON to the given output
path. Invoked as ``python -m simready.pipeline_worker <step> <out.json>
[<export_healed>]`` — a plain subprocess (not ``multiprocessing``) so the
parent's ``__main__`` module is never re-executed in the child; Streamlit
runs its app script as ``__main__``, which makes ``multiprocessing.spawn``
unusable from UI code paths on Windows.

JSON goes to a file, not stdout: OCC's STEP transfer chatter owns stdout.
"""

from __future__ import annotations

import json
import sys
import time


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: pipeline_worker <step_path> <out_json> [export_healed]", file=sys.stderr)
        return 2
    step_path, out_json = argv[0], argv[1]
    export_healed = argv[2] if len(argv) > 2 else None

    from simready.pipeline import _analyze_file_inner

    report = _analyze_file_inner(step_path, export_healed, time.perf_counter())
    with open(out_json, "w", encoding="utf-8") as handle:
        json.dump(report, handle, default=str)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
