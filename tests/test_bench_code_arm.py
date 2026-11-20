from __future__ import annotations

import pytest

from simready.bench.code_arm import CODE_SYSTEM_PROMPT, extract_code, gate_code

OK = """from build123d import *
import math
with BuildPart() as p:
    Box(42, 42, 5)
    Hole(radius=11.25)
part = p.part
"""


def test_extract_last_python_block():
    text = f"Plan first.\n```python\nx = 1\n```\nFinal:\n```python\n{OK}```\n"
    assert extract_code(text) == OK
    assert extract_code("no code here") is None
    assert extract_code(None) is None


def test_allowed_code_passes_gate():
    assert gate_code(OK) == []


@pytest.mark.parametrize("bad", [
    "import os\npart = None",
    "from subprocess import run\npart = None",
    "open('x', 'w')\npart = None",
    "exec('1')\npart = None",
    "__import__('os')\npart = None",
    "x = (1).__class__\npart = None",
    "getattr(math, 'pi')\npart = None",
    "async def f():\n    pass\npart = None",
    "import build123d.exporters as e\npart = None",
    "x = '{0.__class__}'.format(1)\npart = None",
    "x = '{a}'.format_map({'a': 1})\npart = None",
    "from build123d import import_step\npart = import_step('/home/u/.env')",
    "import build123d\npart = build123d.export_stl(None, '/tmp/x')",
    "from build123d import *\npart = import_svg('/etc/passwd')",
])
def test_gate_rejects(bad):
    assert gate_code(bad)


def test_syntax_error_is_rejected_not_raised():
    assert gate_code("def (:")


def test_prompt_states_contract():
    assert "part" in CODE_SYSTEM_PROMPT and "build123d" in CODE_SYSTEM_PROMPT and "millimetres" in CODE_SYSTEM_PROMPT
