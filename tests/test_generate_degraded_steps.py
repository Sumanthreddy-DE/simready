"""Tests for scripts/generate_degraded_steps.py.

OCC-dependent. The valid_step_file fixture skips automatically when
pythonocc-core is unavailable.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.generate_degraded_steps as gd


occ_required = pytest.mark.skipif(
    not gd.OCC_AVAILABLE, reason="pythonocc-core not installed"
)


@occ_required
def test_each_defect_function_returns_non_null_shape(valid_step_file: str) -> None:
    shape = gd.read_step(Path(valid_step_file))
    for name, fn in gd.DEFECT_GENERATORS.items():
        out = fn(shape)
        assert out is not None, f"{name} produced None"
        assert not out.IsNull(), f"{name} produced a null shape"


@occ_required
def test_generate_for_input_writes_step_and_tags_for_each_defect(
    valid_step_file: str, tmp_path: Path
) -> None:
    rows = gd.generate_for_input(Path(valid_step_file), tmp_path, list(gd.DEFECT_NAMES))
    assert len(rows) == len(gd.DEFECT_NAMES)
    ok_rows = [r for r in rows if r["status"] == "ok"]
    assert len(ok_rows) == len(gd.DEFECT_NAMES), [r for r in rows if r["status"] != "ok"]
    for row in ok_rows:
        out_step = Path(row["output_step"])
        out_tags = Path(row["output_tags"])
        assert out_step.exists()
        assert out_step.stat().st_size > 0
        assert out_tags.exists()
        tags = json.loads(out_tags.read_text(encoding="utf-8"))
        assert tags["defect_tags"] == [row["defect"]]
        assert tags["source_step"] == str(Path(valid_step_file))


@occ_required
def test_generate_for_input_handles_unreadable_input(tmp_path: Path) -> None:
    bogus = tmp_path / "garbage.step"
    bogus.write_text("not a real STEP", encoding="utf-8")
    rows = gd.generate_for_input(bogus, tmp_path, ["zero_length_edge"])
    assert len(rows) == 1
    assert rows[0]["status"] == "error"
    assert "read_step" in rows[0]["reason"]


@occ_required
def test_main_smoke_writes_outputs_and_manifest(
    valid_step_file: str, tmp_path: Path
) -> None:
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    target = in_dir / Path(valid_step_file).name
    target.write_bytes(Path(valid_step_file).read_bytes())

    rc = gd.main([
        "--input", str(in_dir),
        "--output", str(out_dir),
        "--max-inputs", "1",
    ])
    assert rc == 0
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest) == len(gd.DEFECT_NAMES)
    ok_count = sum(1 for r in manifest if r["status"] == "ok")
    assert ok_count == len(gd.DEFECT_NAMES)
    step_outputs = list(out_dir.glob("*.step"))
    tag_outputs = list(out_dir.glob("*.tags.json"))
    assert len(step_outputs) == len(gd.DEFECT_NAMES)
    assert len(tag_outputs) == len(gd.DEFECT_NAMES)


def test_main_rejects_unknown_defect(tmp_path: Path) -> None:
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    rc = gd.main([
        "--input", str(in_dir),
        "--output", str(tmp_path / "out"),
        "--defects", "not_a_real_defect",
    ])
    assert rc == 1


def test_main_returns_1_when_input_dir_missing(tmp_path: Path) -> None:
    rc = gd.main([
        "--input", str(tmp_path / "nope"),
        "--output", str(tmp_path / "out"),
    ])
    assert rc == 1
