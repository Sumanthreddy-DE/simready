from __future__ import annotations

import pytest

try:
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.STEPControl import STEPControl_AsIs, STEPControl_Writer
except ImportError:  # pragma: no cover
    BRepPrimAPI_MakeBox = None
    IFSelect_RetDone = None
    STEPControl_AsIs = None
    STEPControl_Writer = None


@pytest.fixture
def missing_step_file() -> str:
    return "/nonexistent/path/missing.step"


@pytest.fixture
def invalid_step_file(tmp_path) -> str:
    path = tmp_path / "invalid.step"
    path.write_text("not a real step file", encoding="utf-8")
    return str(path)


@pytest.fixture
def valid_step_file(tmp_path) -> str:
    if BRepPrimAPI_MakeBox is None:
        pytest.skip("pythonocc-core not available")

    box = BRepPrimAPI_MakeBox(10.0, 20.0, 30.0).Shape()
    path = tmp_path / "valid_box.step"
    writer = STEPControl_Writer()
    writer.Transfer(box, STEPControl_AsIs)
    status = writer.Write(str(path))
    assert status == IFSelect_RetDone
    return str(path)
