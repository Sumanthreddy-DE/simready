"""Sandboxed build123d execution. Skips without the dedicated venv."""

from __future__ import annotations

import pytest

from simready.bench.code_exec import B123D_PYTHON, run_code

if not B123D_PYTHON.exists():
    pytest.skip(f"build123d venv missing: {B123D_PYTHON}", allow_module_level=True)

PLATE = "from build123d import *\nwith BuildPart() as p:\n    Box(40, 30, 5)\npart = p.part\n"


def test_builds_a_step():
    r = run_code(PLATE)
    try:
        assert r["stage"] == "built", r
        assert r["step_path"].endswith("part.step")
    finally:
        r.get("workdir") and r["workdir"].cleanup()


def test_missing_part_is_build_error():
    r = run_code("from build123d import *\nx = Box(1, 1, 1)\n")
    assert r["stage"] == "build_error" and "part" in r["error"]


def test_exception_is_build_error():
    r = run_code("import math\npart = 1 / 0\n")
    assert r["stage"] == "build_error" and "ZeroDivisionError" in r["error"]


def test_child_gets_only_the_scrubbed_env(monkeypatch):
    import subprocess
    from simready.bench import code_exec
    monkeypatch.setenv("DLAB_API_KEY", "sentinel")
    seen = {}

    def fake_run(cmd, **kw):
        seen.update(kw)
        raise subprocess.TimeoutExpired(cmd, 0)

    monkeypatch.setattr(code_exec.subprocess, "run", fake_run)
    code_exec.run_code("import math\npart = None\n")
    assert set(seen["env"]) == {"PATH", "HOME", "PYTHONNOUSERSITE"}
    assert "sentinel" not in seen["env"].values()
    assert "preexec_fn" not in seen  # limits are set inside the child, never via preexec_fn (thread-unsafe)


def test_cpu_limit_is_set_inside_the_child():
    r = run_code("import math\nwhile True:\n    math.sqrt(2)\n", timeout_s=120)
    assert r["stage"] == "timeout"  # RLIMIT_CPU 60 s fires (SIGXCPU) before the 120 s wall clock


def test_timeout_kills():
    r = run_code("import math\nwhile True:\n    math.sqrt(2)\n", timeout_s=3)
    assert r["stage"] == "timeout"
