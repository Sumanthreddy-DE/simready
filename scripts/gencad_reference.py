"""Download the GenCAD-Code test split and cache the 100 `hundred_subset` reference programs.

Run in the sr env (needs pandas + pyarrow):
    C:/mm/sr/python.exe scripts/gencad_reference.py
Writes data/gencad/gt_hundred.json  {test-row index: {"id": deepcad_id, "code": cadquery}}.
"""
from __future__ import annotations

import json
import urllib.request

import pandas as pd

from gencad_common import CACHE, REFERENCE, TEST_PARQUET_URL


def main() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    parquet = CACHE / "test-00000-of-00001.parquet"
    if not parquet.exists():
        urllib.request.urlretrieve(TEST_PARQUET_URL, parquet)
    df = pd.read_parquet(parquet, columns=["deepcad_id", "cadquery", "hundred_subset"])
    idx = df.index[df["hundred_subset"]].tolist()
    assert len(idx) == 100, f"expected 100 hundred_subset rows, got {len(idx)}"
    REFERENCE.write_text(
        json.dumps({str(i): {"id": df.deepcad_id[i], "code": df.cadquery[i]} for i in idx}),
        encoding="utf-8",
    )
    print(f"test rows {len(df)}, cached {len(idx)} references -> {REFERENCE} (first ids {idx[:5]})")


if __name__ == "__main__":
    main()
