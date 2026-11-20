"""Run gated model code in the dedicated build123d venv (ADR 0005)."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

B123D_PYTHON = Path(os.environ.get("SIMREADY_B123D_PYTHON", str(Path.home() / ".venvs/simready-b123d/bin/python")))
CHILD = Path(__file__).resolve().parent / "_b123d_child.py"  # sets its own rlimits (thread-safe)


def _child_env(home: str) -> dict[str, str]:
    return {"PATH": "/usr/bin:/bin", "HOME": home, "PYTHONNOUSERSITE": "1"}


def run_code(code: str, timeout_s: float = 90.0, python: Path | None = None) -> dict:
    python = python or B123D_PYTHON
    if not python.exists():
        return {"stage": "infra_error", "error": f"build123d venv missing: {python}"}
    workdir = tempfile.TemporaryDirectory(prefix="simready-b123d-")
    code_path = Path(workdir.name) / "answer.py"
    code_path.write_text(code, encoding="utf-8")
    step = Path(workdir.name) / "part.step"
    try:
        proc = subprocess.run(
            [str(python), "-I", str(CHILD), str(code_path), str(step)],
            cwd=workdir.name, env=_child_env(workdir.name),
            capture_output=True, text=True, timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        workdir.cleanup()
        return {"stage": "timeout", "error": f"code ran longer than {timeout_s:g} s"}
    except OSError as exc:
        workdir.cleanup()
        return {"stage": "infra_error", "error": f"{type(exc).__name__}: {exc}"}
    if proc.returncode == 0 and step.exists() and step.stat().st_size > 0:
        return {"stage": "built", "step_path": str(step), "workdir": workdir}
    workdir.cleanup()
    tail = (proc.stderr or "").strip().splitlines()[-1:] or [f"exit code {proc.returncode}"]
    if proc.returncode < 0:  # killed by a signal: rlimit CPU (SIGXCPU) counts as timeout
        return {"stage": "timeout", "error": f"child killed by signal {-proc.returncode}"}
    return {"stage": "build_error", "error": tail[0][:500]}
