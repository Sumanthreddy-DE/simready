# Brief — `occ` test marker + the "255 passed" test count

**Status:** active
**Last verified:** 2026-11-04
**Branch:** `chore/test-markers` (cut from `main` at `8f22a51` + this brief's commit)
**BACKLOG items:** S3 `base-vs-env-marker-split`, S3 `test-count-claim-255` (both in **Doing**)

Written for an agent on the VPS in opencode; reviewed and merged on the laptop.
Repo: `~/projects/Mech/SimReady`. Two tasks, one branch, one commit per task.

## Environment (VPS)

Your shell tool does **not** keep `export`s or activations between calls (first
attempt 2026-11-04 failed on exactly this: `micromamba: command not found`, then
`/usr/bin/python: No module named pytest`). So never activate anything. Call the env's
Python by its full path in **every** command:

```
PY=~/simready-fresh/mamba/root/envs/simready-fix/bin/python
```

Put `PY=… ;` at the start of each shell call (or write the full path out). Every
`python` below means `$PY`. First call, as a check:

```
PY=~/simready-fresh/mamba/root/envs/simready-fix/bin/python; $PY -c "import OCC, pytest; print('env OK')"
```

Not `env OK` → stop and report the output; do not look for another Python.
Env `simready-fix` has pythonocc. Install nothing into it, create no env, never
`micromamba shell init`, never edit dotfiles. No network calls, no `.env` changes,
no `-m live_llm`.

## Baseline (before any edit)

```
python -m pytest -q -p no:cacheprovider
```

Record the summary line exactly. Expect roughly 230–254 passed, some skipped,
**5 deselected** (the `live_llm` tests). The laptop's Windows env printed
`254 passed, 1 skipped, 5 deselected` on 2026-11-04. Any failure in the baseline:
stop and report it, do not fix it.

## Task 1 — `occ` marker (`base-vs-env-marker-split`)

Problem: the repo has two kinds of tests, ones that need pythonocc (`OCC`) and pure
ones, but there is no way to select them. `pytest.ini` registers only `live_llm`.
Today OCC tests get skipped in three different ways:

- module-level `pytest.importorskip("OCC.Core.…")` — `tests/test_checks_guards.py`,
  `test_copilot_tools.py`, `test_gen_build.py`, `test_generate_features.py`,
  `test_pipeline_safe.py`, `test_real_eval_regression.py`;
- a module flag — `tests/test_generate_degraded_steps.py` (`gd.OCC_AVAILABLE`);
- the `valid_step_file` fixture in `tests/conftest.py`, which calls `pytest.skip`
  when OCC is missing; and function-level `from OCC…` imports, e.g.
  `tests/test_graph_extractor.py:121`.

Grep `tests/` yourself for `OCC` and `valid_step_file`; the list above is a lead,
not complete.

Do:

1. Register `occ` in `pytest.ini` under `markers =` (one line: "needs pythonocc-core
   (the sr / simready env)"). Do not change `addopts`.
2. Mark every OCC-needing test `occ`:
   - module-level skip or flag → `pytestmark = pytest.mark.occ` in that module
     (combine with an existing `pytestmark` as a list if there is one);
   - tests using `valid_step_file` (directly or through another fixture) → mark
     them in `tests/conftest.py` with a `pytest_collection_modifyitems` hook that
     adds `occ` when `"valid_step_file" in item.fixturenames`;
   - function-level OCC imports → `@pytest.mark.occ` on that test.
   Do not change any test's body or assertion. Do not mark a test that does not
   need OCC (`tests/test_gen_spec.py` and `tests/test_copilot_png_render.py` say
   in their docstrings they run without it).
3. README: in the section that mentions `python -m pytest -q` (around line 348),
   add two lines: `python -m pytest -m "not occ" -q` (pure tests, any Python) and
   `python -m pytest -m occ -q` (needs the sr env). No Makefile or `.ps1` shortcut
   — the README lines replace the item's "Makefile/PS shortcut".

Acceptance (all in `simready-fix`):

- `python -m pytest -q -p no:cacheprovider` → same passed/skipped/deselected as the
  baseline.
- `python -m pytest -m "occ and not live_llm" -q` passed + `python -m pytest -m
  "not occ and not live_llm" -q` passed = full-run passed (record all three lines).
  Write `and not live_llm` every time: a command-line `-m` replaces the one in
  `addopts`, so a bare `-m occ` would also run live LLM tests.
- `python -m pytest -m "not occ and not live_llm" -q -rs` → **no** skip whose
  reason mentions OCC / pythonocc. Paste the skip reasons that remain.
- `python -m pytest --markers | grep occ` prints the new marker.

Commit: `test: add occ marker for pythonocc-dependent tests`.

The laptop review also runs `-m "not occ and not live_llm"` in a Python without
pythonocc; you do not need such an env.

## Task 2 — where did "255 passed" come from (`test-count-claim-255`)

`STATE.md:27` and the S1 `audit-reports-followup` item in `BACKLOG.md` (line ~91)
say "Full suite 255 passed / 5 deselected" for 2026-10-25. `main` collected 250
(245 + 5 deselected) on 2026-11-03. Lead (unconfirmed): `tests/test_bench_concepts.py`
(8 tests) and `tests/test_bench_concepts_file.py` (3 tests) exist on
`origin/fix/audit-remediation` and `origin/sp1-bench` but not on `main`, so 255 may
have been counted on the remediation branch, not on `main`.

Do, read-only on other refs — run it as **one** shell call (the `cd` must not be
split from the commands after it):

```
PY=~/simready-fresh/mamba/root/envs/simready-fix/bin/python
R=~/projects/Mech/SimReady; W=~/projects/Mech/SimReady-count
git -C $R fetch origin
git -C $R worktree add --detach $W origin/fix/audit-remediation
(cd $W && $PY -m pytest --collect-only -q -p no:cacheprovider > /tmp/ids-branch.txt); tail -2 /tmp/ids-branch.txt
git -C $W checkout --detach 1433900
(cd $W && $PY -m pytest --collect-only -q -p no:cacheprovider > /tmp/ids-main.txt); tail -2 /tmp/ids-main.txt
git -C $R worktree remove --force $W
diff <(grep :: /tmp/ids-branch.txt | sort) <(grep :: /tmp/ids-main.txt | sort) | head -60
```

(`1433900` is the main commit that integrated the remediation.) From the two counts
and the diff, decide which ref produced 255. Then edit **only** these two places:

- `STATE.md:27` — replace "Full suite 255 passed / 5 deselected" with the count that
  `main` had, plus a short parenthesis naming where 255 came from, e.g.
  "(255 was counted on `fix/audit-remediation`, which also carried the 11 SP1 bench
  tests)". Use the real numbers you found, not this example.
- `BACKLOG.md` S1 `audit-reports-followup` — same correction, same wording.

Do not edit `test-count-claim-255` itself or move BACKLOG items — the laptop does that
on merge. If the evidence does not explain 255, write down what you found and change
neither file.

Commit: `docs: correct 2026-10-25 test count (255 was counted on <ref>)`.

## Off limits

Everything outside `pytest.ini`, `tests/`, `README.md`, `STATE.md`, `BACKLOG.md` (the
one S1 line) and this brief. No source file under `simready/`, `copilot/`, `ui/`,
`scripts/`. No push, no `/save-session`, no branch other than `chore/test-markers`.

## Report (append to this brief, under `## Run report`, and commit it)

Baseline line; the four acceptance outputs; the 255 finding with both collect counts
and the diff summary; commit SHAs; anything not done and why.
