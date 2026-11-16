"""Read/append benchmark JSONL logs (.jsonl or .jsonl.gz). Stdlib only.

Line 1 is a ``record: header``; every other line is a ``record: attempt``.
Append-only: a resumed attempt that previously hit infra_error gets a new
line, and readers keep the latest line per attempt_id.
"""

from __future__ import annotations

import gzip
import json
import threading
from pathlib import Path
from typing import IO

EXCLUDED_CLASSES = frozenset({"infra_error", "checker_error"})
_WRITE_LOCK = threading.Lock()


def _open_text(path: str | Path, mode: str) -> IO[str]:
    if str(path).endswith(".gz"):
        return gzip.open(path, mode + "t", encoding="utf-8")
    return open(path, mode, encoding="utf-8")


def read_records(path: str | Path) -> list[dict]:
    with _open_text(path, "r") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def read_header(path: str | Path) -> dict:
    for rec in read_records(path):
        if rec.get("record") == "header":
            return rec
    raise ValueError(f"{path}: no header record")


def attempts(path: str | Path) -> list[dict]:
    latest: dict[str, dict] = {}
    for rec in read_records(path):
        if rec.get("record") == "attempt":
            latest[rec["attempt_id"]] = rec
    return list(latest.values())


def done_attempt_ids(path: str | Path) -> set[str]:
    return {a["attempt_id"] for a in attempts(path) if a.get("failure_class") not in EXCLUDED_CLASSES}


def append(path: str | Path, record: dict) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False) + "\n"
    with _WRITE_LOCK, open(path, "a", encoding="utf-8") as fh:
        fh.write(line)
