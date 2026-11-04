# Brief — `occ` test marker + the "255 passed" test count

**Status:** done
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

## Task 2 investigation

- Used existing local remote-tracking ref `origin/fix/audit-remediation` at
  `5f0bed01981b4fb9947ff08ce18a32c4e5a4ef68`; integrated main was
  `1433900`. Both were inspected in the temporary detached worktree
  `~/projects/Mech/SimReady-count`, which was removed afterward.
- Exact collection summaries with the specified Python and
  `-m pytest --collect-only -q -p no:cacheprovider`:
  - remediation: `249 tests collected in 8.84s`
  - integrated main: `238 tests collected in 7.29s`
- Sorted node-ID diff: exactly 11 tests only on remediation (8 in
  `tests/test_bench_concepts.py`, 3 in `tests/test_bench_concepts_file.py`);
  no tests only on integrated main. The test-tree diff between refs contains
  only those two additional files.
- Finding: the branch difference is confirmed, but these collection counts
  do not reproduce 255 passed or establish the historical passed count on main.
  Collection is not execution. Per Task 2's evidence gate, neither `STATE.md`
  nor `BACKLOG.md` was changed; the origin of the exact 255 claim remains unresolved.
- Ruling: omitted `git fetch origin` because the Environment section forbids
  network calls. Evidence therefore describes the existing local tracking ref,
  not a freshly fetched remote. Used subprocess `cwd` in one shell call instead
  of shell `cd`, and read/diffed the full collection outputs without truncation.
  Removed the clean temporary worktree without `--force`.

## Run report

### Environment and baseline

- Executed the specified absolute-path Python environment check first:
  `env OK`.
- Baseline command: `$PY -m pytest -q -p no:cacheprovider`.
  First invocation exceeded the tool's 120-second timeout; reran unchanged with
  a 600-second limit before editing anything. Exact completed summary:
  `239 passed, 10 skipped, 5 deselected, 3 warnings in 140.91s (0:02:20)`.

### Task 1 acceptance

All commands used `~/simready-fresh/mamba/root/envs/simready-fix/bin/python`.

1. `$PY -m pytest -q -p no:cacheprovider`:
   `239 passed, 10 skipped, 5 deselected, 3 warnings in 135.26s (0:02:15)`.
   Passed/skipped/deselected counts match the baseline exactly.
2. Split commands:
   - `$PY -m pytest -m "occ and not live_llm" -q`:
     `104 passed, 9 skipped, 141 deselected, 3 warnings in 82.48s (0:01:22)`.
   - `$PY -m pytest -m "not occ and not live_llm" -q`:
     `135 passed, 1 skipped, 118 deselected, 3 warnings in 39.10s`.
   - Passed-count reconciliation: **104 + 135 = 239**.
3. `$PY -m pytest -m "not occ and not live_llm" -q -rs`:
   `135 passed, 1 skipped, 118 deselected, 3 warnings in 39.76s`.
   Only remaining skip (no OCC/pythonocc skip reason):
   ```text
   SKIPPED [1] tests/test_copilot_ui.py:135: data/parametric_degraded is gitignored local data (regenerate via scripts/generate_degraded_steps.py)
   ```
4. `$PY -m pytest --markers | grep occ`:
   ```text
   @pytest.mark.occ: needs pythonocc-core (the sr / simready env)
   ```

Searched all Python tests for OCC imports, fixture dependencies, and direct
geometry calls. Added module markers to modules with module-level OCC gates,
the requested fixture-name collection hook, and individual markers to direct
geometry tests (including CLI tests using the `built` fixture). Test bodies and
assertions were retained; `addopts` was unchanged. `test_gen_spec.py` and
`test_copilot_png_render.py` were not marked or edited.

Ruling: README selectors include `and not live_llm`, rather than the bare
selectors proposed in step 3, because the acceptance section correctly notes
that command-line `-m` overrides the offline default. Bare selectors could run
live tests; this preserves the intended offline split.

During implementation, an initial acceptance attempt hit three collection
errors (`pytest` imports missing or placed after decorators in `test_brepnet.py`,
`test_defect_head.py`, and `test_splitter.py`). Corrected the imports, then ran
all acceptance commands successfully as recorded above. The three warnings
are the existing anyio pytest deprecation and two torch JIT deprecations.

### Task 2 finding and commits

- Collection counts: remediation **249**, integrated main **238**; the full
  sorted node-ID diff is exactly the **11 SP1 tests** described in the Task 2
  investigation above. No evidence establishes the exact 255 passed claim.
- **Not done:** count corrections in `STATE.md` and `BACKLOG.md`, as explicitly
  required when evidence does not explain 255. Those files and Doing items
  remain untouched. No fresh fetch (no-network ruling above).
- Task 1: `79c5dcb` — `test: add occ marker for pythonocc-dependent tests`.
- Task 2: `7750e8a` — `docs: record unresolved 2026-10-25 test count investigation`.
  The proposed correction commit title would assert an unproven finding, so
  this commit records the investigation in the brief instead.
- This Run report is committed separately as
  `docs: append test-marker run report`; its SHA is available in branch history.

Final review: self-reviewed the complete diff against the brief and ran
`git diff --check`. No production-source edits. The no-pythonocc environment
check remains for laptop review as specified; these results are from
`simready-fix` with OCC installed. All implementation/report commits are on
`chore/test-markers`. No push, network call, installation, credential edit,
or `/save-session` was performed.

## Laptop review (2026-11-04)

Merged as `00de34d`. Laptop sr env (`C:/mm/sr`), clean worktree of the branch: full 238 passed / 12 skipped (gitignored data absent); `-m "occ and not live_llm"` 104 passed / 10 skipped; `-m "not occ and not live_llm"` 134 passed / 3 skipped; with every `OCC` import blocked by a meta-path finder, the not-occ run is 134 passed, 0 failed. Plain base Python 3.12 cannot run it (no `torch_geometric`), so the README says "need no pythonocc (the other requirements still apply)" instead of "any Python".

255 resolved on review: the laptop working copy of `main` collects 255/260 vs 249 in a clean worktree; the 6 extra are `test_grabcad.py` cases parametrized over 3 gitignored STEPs in `tests/data/grabcad/`. `fix/audit-remediation` clean = 249 (238 + 11 bench), + 6 = 255. STATE.md and the S1 line corrected.
