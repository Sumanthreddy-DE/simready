# VPS run: split the OCC tests out of test_copilot_tools.py

**Status:** done
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

## Result

Test split commit: `dcf524215c5541ca44725012f3f5ca3ab00cb988`.
Branch: `chore/copilot-tools-occ-split`; worktree: `/tmp/simready-occ-split`.
Steps 1–7 completed; ready for Claude's review and merge.

Moved the OCC importorskip block and happy-box test byte-for-byte into
`tests/test_copilot_tools_occ.py`. All 24 function bodies (tests, fixture and helper)
retain their original text and order. Removed the pure module's OCC marker and
unused `Path` import. No additional pure tests needed moving.

### Baseline (step 1)

- Normal: `22 passed, 1 warning in 4.48s`
- `PYTHONPATH=/tmp/noocc`: `1 skipped, 1 warning in 2.78s`

### Focused checks (step 4)

All commands used `/home/sumanth/simready-fresh/mamba/root/envs/simready-fix/bin/python`
as `$PY`, with working directory `/tmp/simready-occ-split`.

- `$PY -m pytest tests/test_copilot_tools.py tests/test_copilot_tools_occ.py -q`:
  `22 passed, 1 warning in 5.07s`
- Same command with `PYTHONPATH=/tmp/noocc`:
  `21 passed, 1 skipped, 1 warning in 3.19s`
- `$PY -m pytest tests/test_copilot_tools.py -q -m "not occ"`:
  `21 passed, 1 warning in 3.84s`

### Negative control (step 5)

- Temporarily restored the pure module's OCC marker, then ran the same `not occ`
  command: `21 deselected, 1 warning in 3.10s` (expected no-tests-selected exit).
- Removed the marker again and reran: `21 passed, 1 warning in 3.19s`.

### Full suite comparison (step 6)

Initial `$PY -m pytest -q -p no:cacheprovider` runs (20-minute timeout each):

- Before, main checkout at `d032337`:
  `239 passed, 10 skipped, 5 deselected, 3 warnings in 168.82s (0:02:48)`
- After, worktree:
  `239 passed, 11 skipped, 3 warnings in 168.74s (0:02:48)`

Ruling: normalize provider environment for the comparison. Collect-only probes
showed `tests/test_gen_e2e.py:53` skipping the whole module in the worktree because
provider configuration was absent, while main collected and deselected its five
live tests. Comparing those raw skip counts would conflate local configuration
with the split. Cost if wrong: a collection regression could be misattributed to
configuration; the equalized runs below verify identical counts.

Reran the same full-suite command in both checkouts with this identical prefix:
`OPENAI_BASE_URL=https://example.invalid/v1 OPENAI_MODEL=offline-control OPENAI_API_KEY=offline-control`.
These dummy values satisfy collection guards; pytest.ini's default `not live_llm`
filter keeps all five live tests deselected. No credentials were copied.

- Before, main checkout:
  `239 passed, 10 skipped, 5 deselected, 3 warnings in 150.60s (0:02:30)`
- After, worktree:
  `239 passed, 10 skipped, 5 deselected, 3 warnings in 149.81s (0:02:29)`

Pass/skip/fail/deselection counts match. Existing warnings are one anyio pytest
deprecation and two torch JIT deprecations. `git diff --check` passed.

Execution used the shell tool's explicit working directory rather than `cd`;
the environment Python was spelled out in every pytest command. Only the two
test files and this plan were changed. No push or merge was performed.
