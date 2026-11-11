# VPS run: split the OCC tests out of test_copilot_tools.py

**Status:** active
**Last verified:** 2026-11-11

BACKLOG S3 `copilot-tools-midfile-importorskip`. Branch `chore/copilot-tools-occ-split`.

## Problem (checked 2026-11-11 on the VPS)

`tests/test_copilot_tools.py` has 22 tests. Line 16 sets `pytestmark = pytest.mark.occ`
for the whole module, and line 247 calls `pytest.importorskip("OCC.Core.BRepPrimAPI")`
at module level. 21 tests sit above line 247 and need no pythonocc; 1 test
(`test_build_part_dispatch_happy_box`) sits below it and does. Without pythonocc the
whole module is skipped, so the 21 pure tests never run. `simready.copilot.tools` itself
imports fine without OCC.

Measured, env `simready-fix`:
- normal: `22 passed`
- OCC blocked: `1 skipped` (the bug)

## Rules

- Your shell keeps no `cd`, `export` or activation between calls. Use the env binary by
  full path: `PY=/home/sumanth/simready-fresh/mamba/root/envs/simready-fix/bin/python`
  (write it out in full in every command), and run pytest from the repo with
  `$PY -m pytest` after `cd /home/sumanth/projects/Mech/SimReady &&` on the same line.
- Work in a worktree outside the repo (SimReady has no git-ignored worktree folder):
  `git -C /home/sumanth/projects/Mech/SimReady worktree add /tmp/simready-occ-split -b chore/copilot-tools-occ-split main`.
  All edits and test runs happen in `/tmp/simready-occ-split`.
- Commit on the branch only; stage and commit in the same command. Never push, merge,
  rebase or stash. Touch only the two test files and this plan file.
- No test may change its body. A move is a move: same function text, same order.

## OCC-block control

Blocks pythonocc without uninstalling it. Create once:

```
mkdir -p /tmp/noocc/OCC && echo 'raise ModuleNotFoundError("No module named OCC (blocked for test)", name="OCC")' > /tmp/noocc/OCC/__init__.py
```

Run any pytest command with `PYTHONPATH=/tmp/noocc` in front to simulate a machine
without pythonocc. (It must raise `ModuleNotFoundError`, not plain `ImportError`, or
`importorskip` errors instead of skipping.)

## Steps

1. Baseline in the worktree, both ways. Expected `22 passed`, then `1 skipped`:
   `$PY -m pytest tests/test_copilot_tools.py -q` and the same with `PYTHONPATH=/tmp/noocc`.
2. Create `tests/test_copilot_tools_occ.py`: a short module docstring (why it is separate),
   `from __future__ import annotations`, `import pytest`, `pytestmark = pytest.mark.occ`,
   the `importorskip` block from line 247, then every test and helper below line 247,
   moved unchanged. Add only the imports those moved tests need.
3. In `tests/test_copilot_tools.py`: delete the moved block and the `importorskip`, and
   remove `pytestmark = pytest.mark.occ` (line 16), because the module no longer needs
   OCC. Remove imports that only the moved code used.
4. Check, and paste each summary line into the report:
   - `$PY -m pytest tests/test_copilot_tools.py tests/test_copilot_tools_occ.py -q` → `22 passed`
   - same with `PYTHONPATH=/tmp/noocc` → `21 passed, 1 skipped`
   - `$PY -m pytest tests/test_copilot_tools.py -q -m "not occ"` → `21 passed` (before the fix this deselected all 22)
   If any "pure" test fails under the OCC block, it needs OCC: move it to the occ module
   too and say so in the report.
5. Negative control: put `pytestmark = pytest.mark.occ` back into the pure module, run the
   `-m "not occ"` command, show it deselects all, remove it again, rerun to `21 passed`.
6. Full suite, before (on `main` in the main checkout) and after (in the worktree):
   `$PY -m pytest -q -p no:cacheprovider` with a 20-minute timeout (`cd /home/sumanth/projects/Mech/SimReady &&` for before, `cd /tmp/simready-occ-split &&` for after). Report both summary
   lines; the only allowed difference is none (same pass/skip/fail counts).
7. Commit: `test: split OCC tests out of test_copilot_tools.py so the pure tests run without pythonocc`.
   In this plan file set `**Status:** done` and add a `## Result` section: commit SHA, the
   check lines from steps 4–6. Commit that too. Stop. Claude reviews and merges.
