"""Free-form build123d arm (design E4): prompt, code extraction, AST gate.

The gate is a first filter, not the sandbox: code_exec.py still runs the code
in a separate venv child with rlimits and no secrets (ADR 0005).
"""

from __future__ import annotations

import ast
import re

CODE_SYSTEM_PROMPT = (
    "You design mechanical parts as solid models with the build123d Python library. Answer each "
    "request with exactly one fenced ```python code block that builds the requested part and assigns "
    "the final solid to a variable named part; dimensions are in millimetres. Use only "
    "`from build123d import ...` / `import build123d` and `import math`; no file, network or OS access. "
    "Make sensible engineering choices for anything the request leaves open. If the part cannot be "
    "built, say so instead of writing code."
)

_BLOCK = re.compile(r"```(?:python|py)[ \t]*\n(.*?)```", re.DOTALL)
_ALLOWED_MODULES = {"build123d", "math"}
_FORBIDDEN_NAMES = {"open", "exec", "eval", "compile", "__import__", "globals", "locals", "vars",
                    "getattr", "setattr", "delattr", "input", "breakpoint", "memoryview"}
# str.format / format_map reach attributes through the format string ("{0.__class__}"),
# which no Attribute node shows; build123d's import_*/export_* read and write arbitrary paths.
_FORBIDDEN_ATTRS = {"format", "format_map"}


def _forbidden_identifier(name: str) -> bool:
    return name.startswith(("_", "import_", "export_"))


def extract_code(content: str | None) -> str | None:
    if not content:
        return None
    blocks = _BLOCK.findall(content)
    return blocks[-1] if blocks else None


def gate_code(code: str) -> list[str]:
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return [f"syntax error: {exc.msg} (line {exc.lineno})"]
    errors: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in _ALLOWED_MODULES:
                    errors.append(f"line {node.lineno}: import {alias.name} is not allowed")
        elif isinstance(node, ast.ImportFrom):
            if node.module not in _ALLOWED_MODULES or node.level:
                errors.append(f"line {node.lineno}: from {node.module} import is not allowed")
            for alias in node.names:
                if _forbidden_identifier(alias.name):
                    errors.append(f"line {node.lineno}: importing {alias.name} is not allowed")
        elif isinstance(node, ast.Name) and (node.id in _FORBIDDEN_NAMES or _forbidden_identifier(node.id)):
            errors.append(f"line {node.lineno}: name {node.id} is not allowed")
        elif isinstance(node, ast.Attribute) and (node.attr in _FORBIDDEN_ATTRS or _forbidden_identifier(node.attr)):
            errors.append(f"line {node.lineno}: attribute {node.attr} is not allowed")
        elif isinstance(node, (ast.AsyncFunctionDef, ast.Await, ast.AsyncFor, ast.AsyncWith)):
            errors.append(f"line {node.lineno}: async code is not allowed")
    return errors
