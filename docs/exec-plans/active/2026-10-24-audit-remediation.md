# Audit Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop false-success CLI reporting, preserve approved GenCAD assets in the canonical workspace with hash evidence, and make current documentation match the verified workspace.

**Architecture:** Work on `fix/audit-remediation` from `c8b2cec`, preserving `sp1-bench` and `gencad` branch pointers. Make the CLI/report change test-first, then copy only approved non-archive assets and verify every destination against its source. Reconcile current docs in place; fresh-clone remediation and worktree retirement are later gated phases.

**Tech Stack:** Python 3.10 (`C:\mm\sr\python.exe`), Click, Rich, pytest; Python stdlib SHA-256 and file-copy operations on Windows.

**Status:** active  
**Last verified:** 2026-10-24

---

## Constraints

- No deletion, archive moves, worktree retirement, commit, or push without explicit approval for that operation.
- Retain every source asset after destination hashes match.
- Do not read `.env` or expose credential values.
- Do not alter SP1 implementation code or mix this work into the `sp1-bench` pointer.
- The approved asset destinations are `weights/gencad_qwen25vl3b_qlora/`, `data/gencad/`, and `.local/` under the main workspace. The adapter ZIP and all Archive changes remain unapproved.

### Task 1: CLI false-success regression

**Files:**
- Modify: `tests/test_report.py`
- Modify: `tests/test_cli.py`
- Modify: `simready/report.py`
- Modify: `simready/cli.py`

- [x] **Step 1: Reproduce the original failure**

Run with base Python:

```powershell
python -m simready.cli analyze tests/data/smoke_box.step
```

Expected before the fix: `InvalidInput`, `Validation FAIL`, `No findings. Clean geometry.`, duplicated report, exit code 0. Run the same command with `C:\mm\sr\python.exe` and retain it as the successful-analysis control.

- [x] **Step 2: Write failing renderer and CLI tests**

Add a terminal-renderer test using an `InvalidInput` report containing a `MissingDependency` validation error and no findings. Assert that output contains the validation check, detail, and suggestion and does not contain `Clean geometry`.

Update the missing-file terminal/JSON tests to expect a nonzero Click result. Add a CLI test at the real command seam with `simready.cli.analyze_file_safe` patched to return a controlled `InvalidInput` report. Assert nonzero exit, one occurrence of `SimReady Analysis:`, validation detail, and no clean-geometry claim. Add a successful-report control asserting exit 0, one heading, and the genuine no-findings message.

- [x] **Step 3: Verify RED**

Run:

```powershell
C:\mm\sr\python.exe -m pytest tests/test_report.py tests/test_cli.py -q
```

Expected: new assertions fail on missing validation details/clean claim, existing zero-exit assertions, and duplicate heading. No production edit before observing these failures.

- [x] **Step 4: Implement the minimal fix**

In `render_terminal_report`, render validation errors when validation failed or status is `InvalidInput`; reserve `No findings. Clean geometry.` for a valid report with no findings. Use `Console(file=StringIO(), record=True)` so Rich does not print immediately and then repeat its recorded output through `export_text()`. Set the table border explicitly to `rich.box.ASCII`; Windows console output must remain encodable through Click's CP1252 stream wrapper. In the CLI, emit terminal output with `click.echo(..., nl=False)` to avoid an extra blank line. After emitting the requested output, raise `click.exceptions.Exit(1)` when `report["status"] == "InvalidInput"`; JSON, output-file, and HTML rendering still occur before the exit.

- [x] **Step 5: Verify GREEN and original scenarios**

Run the targeted tests, then the original base-Python and `sr` commands. Expected failure path: actionable error, no clean claim, one report, exit 1. Expected success path: exit 0, one report, genuine clean claim when no findings exist.

- [x] **Step 6: Run regression verification**

Run `C:\mm\sr\python.exe -m pytest -q`; record exact pass/skip/fail counts. Inspect the diff and ensure no unrelated code changed.

### Task 2: Preserve approved GenCAD assets

**Files:**
- Create locally, ignored: `weights/gencad_qwen25vl3b_qlora/*` (7 files)
- Create locally, ignored: `data/gencad/gt_hundred.json`
- Create locally, ignored: `data/gencad/test-00000-of-00001.parquet`
- Create locally, ignored: `data/gencad/mecagent_metrics/best_iou.py`
- Create locally, ignored: `.local/LESSONS.md`
- Create locally, ignored: `.local/dlab_report_2026-10-06/*` (3 files)

- [x] **Step 1: Recheck source and destination state**

Require source files to exist and destination roots to be absent. Refuse overwrites. Do not copy `__pycache__`, the empty `scaled_generated_steps/`, the adapter ZIP, or `STATE.md`.

- [x] **Step 2: Copy without moving source**

Copy the seven adapter files from the nested `qwen_lora_adapter/qwen_lora_adapter/` directly into `weights/gencad_qwen25vl3b_qlora/`. Copy the other approved files preserving their relative paths. Use binary copy and leave every source intact.

- [x] **Step 3: Verify destinations**

For every copied file, assert source/destination SHA-256 equality. Required anchor hashes:

```text
adapter_model.safetensors 69d11308e63b77a65f2dc384a15b5fde5a7eb00f2e3321b297f62566513956e9
gt_hundred.json           0588e037a6f29cbf84d2329f7e413b507fdd257963bc367e584b489dd1db9246
test parquet              9eeadbf7da1022dc16a071de1e7512449c076e1aa22a8ffa7295d73527d6c9c5
best_iou.py               0c4b6d2334d74d029ca93444feb1d50fb745a268c3b9fda9dbb14d7bae40e19e
```

Expected: 14 copied files (7 adapter + 3 GenCAD cache + 4 private notes), zero mismatches, all source files still present. Verify Git ignores all destinations and reports no copied assets as untracked.

### Task 3: Reconcile current workspace documentation

**Files:**
- Create: `docs/impl/workspace-artifacts.md`
- Modify: `STATE.md`
- Modify: `BACKLOG.md`
- Modify: `CONTEXT.md`
- Modify: `docs/exec-plans/active/2026-10-04-sp1-bench-implementation.md`
- Modify: `.local/LESSONS.md` (local only; current workspace routing note)
- Modify: `Archive/README.md` (live-source pointers only; no files moved into Archive)

- [x] **Step 1: Write one compact artifact map**

Record canonical local paths, task, ignored/tracked status, provenance, SHA-256 anchors, and existing regeneration commands. Point to `docs/validation/gencad_eval.md` for evaluation detail rather than duplicating it. Note that the original adapter ZIP remains untouched in the GenCAD worktree pending archive approval.

- [x] **Step 2: Update current status**

STATE: current branch/workspace, CLI fix evidence, preserved assets, next action = fresh-clone README/demo remediation; keep SP1 paused. BACKLOG: mark Phase 1 inventory and asset preservation complete with evidence; leave fresh-clone and archiving/worktree items open; remove only recovered-loss subtask after checking `docs/finetune_results.md` and `trainer_state.json`. Mark historical application instructions explicitly historical rather than deleting their narrative.

- [x] **Step 3: Reconcile glossary and plan metadata**

CONTEXT: verify live tool count and RAG behavior against code; remove volatile test totals and old application timing. SP1 plan: `Status: paused`, current verification date, resume at Task 2 review per `.superpowers/sdd/progress.md`. Local lessons: state the canonical workspace while assets remain in both places pending retirement. Archive index: point live status to repo `STATE.md`/`BACKLOG.md` and current plan to active/completed exec-plan directories; do not move archive content.

- [x] **Step 4: Verify documentation claims**

Run focused searches for stale paths/tool counts/status. Run `git diff --check`, inspect `git status`, and confirm copied local assets are ignored. Do not claim fresh-clone readiness or worktree retirement.

### Task 4: Later gated phases

- [ ] Fix README setup, demos, results provenance, and generation gates with fresh execution evidence.
- [ ] Run browser-observed Streamlit chat/build/analyze and fresh-clone acceptance.
- [ ] Ask separately before any archive operation or worktree retirement.
- [ ] Preserve `sp1-bench`; reconcile `main`/`gencad` ancestry before integration decisions.
