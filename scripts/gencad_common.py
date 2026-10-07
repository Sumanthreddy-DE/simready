"""Shared paths for the GenCAD-Code eval scripts (scripts/gencad_*.py).

Results (committed):  docs/validation/gencad/
Caches (gitignored):  data/gencad/  -- test split, reference programs, MecAgent metric file,
                      scaled STEPs, reference STEPs.

Generation, training and the Colab-side scoring live in notebooks/gencad_baseline.ipynb and
notebooks/gencad_train_qwen.ipynb. These scripts do the local analysis on their outputs.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "docs" / "validation" / "gencad"
CACHE = REPO / "data" / "gencad"
MODEL_TAG = "qwen25vl3b_qlora"

GENERATIONS = RESULTS / f"gen_{MODEL_TAG}.jsonl"          # from Colab, cell 4
SCORES = RESULTS / f"scores_{MODEL_TAG}.json"              # from Colab, cell 5 (MecAgent metric)
SCORES_BASE = RESULTS / "scores_qwen25vl3b_base.json"
GENERATED_STEPS = RESULTS / "steps"                        # from Colab, cell 5 (one per valid program)
REFERENCE = CACHE / "gt_hundred.json"                      # gencad_reference.py
MECAGENT_METRIC = CACHE / "mecagent_metrics" / "best_iou.py"

TEST_PARQUET_URL = (
    "https://huggingface.co/datasets/CADCODER/GenCAD-Code/resolve/main/data/test-00000-of-00001.parquet"
)
MECAGENT_METRIC_URL = (
    "https://raw.githubusercontent.com/MecAgent/mecagent-technical-test/HEAD/metrics/best_iou.py"
)


def load_generations() -> dict[int, dict]:
    rows = (json.loads(l) for l in GENERATIONS.read_text(encoding="utf-8").splitlines() if l.strip())
    return {r["idx"]: r for r in rows}


def load_reference() -> dict[int, dict]:
    return {int(k): v for k, v in json.loads(REFERENCE.read_text(encoding="utf-8")).items()}


def load_scores(path: Path = SCORES) -> dict[int, dict]:
    return {r["idx"]: r for r in json.loads(path.read_text(encoding="utf-8"))}
