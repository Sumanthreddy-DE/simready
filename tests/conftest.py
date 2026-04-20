from __future__ import annotations

import pytest


@pytest.fixture
def missing_step_file() -> str:
    return "/nonexistent/path/missing.step"


@pytest.fixture
def invalid_step_file(tmp_path) -> str:
    path = tmp_path / "invalid.step"
    path.write_text("not a real step file", encoding="utf-8")
    return str(path)
