# Attempt infrastructure-error repair implementation plan

**Status:** done
**Last verified:** 2026-11-17

**Goal:** Keep checker/backend/process failures out of model scoring, unblocking cad-rl-env Phase B through SimReady's existing attempt API.

**Architecture:** Retain the spawn worker and existing excluded classes. Guard backend setup separately from model geometry execution; supervise queue delivery alongside child liveness. Return null scoring fields for excluded outcomes and make runner accounting/resume agree.

**Tech Stack:** Python multiprocessing, pytest, existing VPS OCP environment.
**Spec:** User's 2026-11-17 infrastructure classification requirements; SP1 design §3 and implementation Task 5.

## Constraints and ownership

- Base: `sp1-bench` at `6d5fb47`, clean `/tmp/simready-sp1-review` at inspection. No live agent cwd there; two live cad-rl-env sessions own wrapper work. Preserve main's existing BACKLOG/STATE edits.
- Implementation/plan on SP1; canonical BACKLOG/STATE updates on main. No commits, tags, pushes, installs or environment creation without approval.
- Reuse `grader-spawn-fail-fast`; promote its severity/scope rather than duplicate it.
- Preserve model F4 and genuine running F8. `infra_error` / `checker_error` are unscored, never zero rewards.
- Proposed immutable patch release: `v0.5.1` (absent locally/remotely at inspection); do not move `v0.5.0`. `bench-checker-1.0.0` remains separately gated on Task 11 proofread/freeze.

## Review focus

- Missing backend and broken import must exercise real worker error boundaries.
- Spawn child exits with code 0 or nonzero and no queue payload must fail fast, not time out.
- A live hung child must time out and be reaped, including kill escalation.
- Checker/import/setup exceptions must not become F4; a real null-shape model build remains F4.
- Runner log, summary, resume and report must exclude infrastructure outcomes consistently.

## Task 1: Reproduce and repair worker/supervision contract

**Files:** `simready/bench/attempt.py`, `tests/test_bench_attempt.py`.
**Interfaces:** `grade_spec(...) -> dict` with stages `graded|build_error|timeout|infra_error|checker_error`; failures carry `error`, infrastructure carries a reason via `error_type`. `evaluate_reply(...)` propagates an explicit error and null `partial`/`passed` for excluded classes.

- [ ] Add regression tests for missing backend, build import failure, unexpected child exits, startup exception, checker exception, genuine running timeout and cleanup. Keep real OCP good-reference and model-null-build controls.
- [ ] Run tests against unchanged implementation and capture intended failures.
- [ ] Separate setup/backend errors from model build errors. Poll the queue with a monotonic deadline and child exit checks; drain a delivered payload before declaring an empty exited child. Always reap/close process and queue resources.
- [ ] Map excluded stages to existing failure classes with null scoring fields; catch grader exceptions as checker errors.
- [ ] Run attempt regressions under existing OCP env.

## Task 2: Consumer consistency and verification

**Files:** `simready/bench/runner.py`, `tests/test_bench_runner.py`, `tests/test_bench_report.py` if needed. Inspect `runlog.py`, `report.py`, `replay.py`.
**Interfaces:** Excluded attempts remain retryable, absent from model scoring, counted in summary infrastructure errors; scored `written` count excludes them.

- [ ] Add failing runner regression covering checker/infra outcomes, resume and report exclusion.
- [ ] Align summary and consecutive-error stop handling for provider and checker infrastructure outcomes.
- [ ] Run all bench/OCP dependency tests, CI spec-fast and available full-suite checks. Record environment limitations rather than installing dependencies.
- [ ] Review diff and cleanup assertions; record exact results here.

## Task 3: Dependency handoff and approval gate

**Files:** canonical main `BACKLOG.md`, `STATE.md`; SP1 implementation plan Task 5/11 and this plan.

- [ ] Correct earlier readiness assertions: the old 99-test pass did not cover infrastructure/model distinction.
- [ ] Document `grade_spec` stages and `evaluate_reply` excluded fields for cad-rl-env; no copied supervisor.
- [ ] Keep issue open pending approved commit; corrected SHA cannot exist before that gate.
- [ ] Request commit approval with proposed message, then separate tag/push approval. No checker freeze claim.

## Results

Implementation and verification complete; publication blocked only on approval gates. No corrected commit exists yet: working changes are based on `6d5fb479e866106b96900f9968f069b75da553e0` (this is NOT the corrected SHA).

**Commit approval received:** user approved SP1 repair and separate main status commits. This document ships with the repair; canonical main BACKLOG/STATE will record its resulting SHA. Version bump, tag and publication are still separate gates. The uncommitted/approval wording in the execution history below describes the pre-approval state.

### Execution ledger / rulings

- Task 1 complete: failing regressions reproduced missing backend → F4, broken import/empty exited child → F8, excluded checker result → zero, spawn/grader exceptions escaping. Initial RED: 9 failed / 9 passed (one control fixture corrected: identical-box subtraction is an empty compound, not null). Real kernel control now uses schema-valid dx=1e-12 and raises native Standard_DomainError → F4.
- Task 2 complete: runner RED 3 failed / 26 passed; replay RED 2 failed / 6 passed. GREEN covers excluded log/resume/report/summary and explicit replay errors.
- Ruling: retain existing SP1 worktree, no second worktree — no other live agent cwd there and initial tree clean; monitor git status. Cost if wrong: concurrent edit collision; no git integration done.
- Ruling: this plan is its own ledger; no new top-level `.superpowers` convention — project rules prohibit new structure without separate authorization. Cost: no automated skill task ledger scripts.
- Ruling: startup (including checker imports) shares the wall-clock budget but expiration before readiness is infra; ready live build/check expiration is F8. Cost: callers with tiny budgets get infrastructure rather than model failures, intentionally.
- Independent review found four substantive issues: arbitrary Python builder bugs → F4; queue partial-frame reads exceeding deadline; checker import after readiness; malformed result escaping. All addressed in one fix pass. Additional RED: 7 failures for builder bug/protocol/setup timeout. Reviewer's external-bounded probe reproduced partial-frame queue hang; new atomic mailbox partial-write/crash regression verifies the replacement.
- Ruling: replace multiprocessing Queue with private atomic file mailbox — Queue timeout bounds readiness, not complete frame receipt, and can hang forever on mid-frame child death. Parent reads only atomically published results; crashed writes remain unpublished and are cleaned with TemporaryDirectory after child reaping. Cost: local temporary-disk I/O per attempt; local filesystem assumed responsive.
- Ruling: F4 only for native Standard exceptions or explicit null result; unexpected Python builder errors are checker_error. Cost: an unrecognized backend exception is conservatively unscored rather than penalizing the model. OCP verified; pythonocc exception packaging not live-verified in this session.
- No review findings deferred. No dependencies/environments installed; no commit/tag/push.

### Exact checks (VPS)

All commands run in `/tmp/simready-sp1-review` unless stated otherwise, using existing `/home/sumanth/.venvs/simready-ocp/bin/python`:

1. Baseline before edits: `.../bin/python -m pytest -q tests/test_bench_attempt.py tests/test_bench_runner.py tests/test_bench_report.py` → 22 passed in 11.16s.
2. Original dependency slice plus early regressions: `.../bin/python -m pytest -q tests/test_occ_compat.py tests/test_bench_geometry.py tests/test_bench_checker.py tests/test_bench_reference_specs.py tests/test_bench_attempt.py tests/test_bench_concepts.py tests/test_bench_concepts_file.py` → 110 passed in 44.78s (before review additions).
3. CI spec-fast: `.../bin/python -m pytest tests/test_gen_spec.py -q` → 23 passed in 0.22s.
4. Final combined: `.../bin/python -m pytest -q tests/test_bench_*.py tests/test_occ_compat.py tests/test_gen_spec.py` → **175 passed, 1 deselected in 75.32s**. Covers real good geometry, real kernel F4, missing backend/import, zero/nonzero child exit (also after ready), running timeout, SIGTERM-ignore kill escalation, partial-write crash, malformed protocol, checker/executor exceptions, runner/replay/regrade.
5. Required full suite: `.../bin/python -m pytest -m "not live_llm" -q` → collection error `tests/test_defect_head.py`: no torch (6 skipped, 6 deselected). Stopped at dependency gate; no installation attempted.
6. Available suite: `.../bin/python -m pytest -m "not live_llm" -q --ignore=tests/test_defect_head.py --tb=no` → **20 failed, 273 passed, 27 skipped, 6 deselected in 89.20s**. Baseline HEAD exported via `git archive HEAD` to `/tmp/opencode/simready-attempt-baseline`, same command → **same 20 failed**, 247 passed, 28 skipped, 1 deselected in 37.18s. No additional failed test IDs. Failures:
   - `test_brepnet.py`: `test_brepnet_fallback_returns_per_face_scores_and_embeddings`, `test_brepsage_backend_engages_when_checkpoint_exists`.
   - `test_checks.py`: `test_small_feature_fixture_flags_small_geometry`, `test_duplicate_body_fixture_flags_duplicate_body_heuristic`, `test_duplicate_face_fixture_flags_duplicate_face_heuristic`.
   - `test_graph_extractor.py`: `test_extract_brep_graph_smoke_box`, `test_smoke_box_exact_counts`, `test_extract_brep_graph_multi_body_works`, `test_extract_brep_graph_node_features_include_phase2_fields`, `test_extract_brep_graph_edge_features_include_dihedral_metadata`, `test_extract_brep_graph_multi_body_per_body_extraction`, `test_uv_bounds_returns_nonzero_for_box_face`.
   - `test_pipeline.py`: `test_analyze_multi_body_file`, `test_analyze_small_feature_file`, `test_analyze_duplicate_body_file`, `test_analyze_duplicate_face_file`, `test_combined_per_face_scores_match_face_count`, `test_self_intersection_skipped_when_face_count_exceeds_limit`, `test_brepnet_inference_is_honestly_labelled_heuristic`.
   - `test_splitter.py`: `test_split_bodies_multi_body_fixture`.
7. `git diff --check` → clean on SP1 and main. No configured repository lint command; CI requires spec-fast and full-suite, reported above.

### Dependency handoff

cad-rl-env can use the corrected working implementation through `simready.bench.attempt.evaluate_reply` / `grade_spec`, without copying process supervision. Pin only the eventual approved corrected SHA/tag; v0.5.0 does not contain this fix.

- `grade_spec`: `stage=graded` provides `report` and `fingerprint`; `build_error` maps to F4; `timeout` maps to F8 only after readiness. `infra_error`/`checker_error` carry `error` and usually `error_type`; unexpected exit additionally has `exitcode`. No reward field is returned at this layer.
- `evaluate_reply`: inspect `failure_class` first. For `infra_error` or `checker_error`, `partial=None`, `passed=None`, `error` describes the fault, `error_type` categorizes it; `check_report`/`fingerprint`/`build_error` remain null. Abort/retry or raise the wrapper's infrastructure exception, never coerce null to zero/false or emit a reward for that sample.
- Scored model failures retain `partial=0.0`, `passed=False`, F4/F8 and compatible `build_error`; successful grading carries checker `partial`, `passed`, `check_report`, `fingerprint`.
- Runner excludes infrastructure from scored `written`, increments `infra_errors`, stops after repeated infra, retries on resume, report excludes them. Regrade retains exclusion; replay raises explicit infrastructure errors.
- Canonical main BACKLOG expands/promotes existing `grader-spawn-fail-fast` to S1 and corrects readiness claims; main STATE updated while preserving pre-existing edits. SP1 Task 11 references this repair. Merge main status into SP1 later under branch rules, only with approval.
- Next decision: approve SP1 repair commit (suggested `fix(bench): exclude grader infrastructure failures from model scoring`) and separate canonical main status commit. Record actual corrected SHA here after commit. Then approve package patch release: bump package version to 0.5.1, commit metadata, create a NEW immutable annotated `v0.5.1` on the approved corrected release commit and user-publish it. Recheck tag availability first. No existing tag is moved. `bench-checker-1.0.0` is not ready: concepts proofread, frozen hash, CHECKER_VERSION freeze remain separate Task 11 gates.
- Limitations: no pythonocc/Windows run, no new wheel/install verification, no hosted calls, full-suite unavailable as green due to baseline OCP/ML gaps above. Process cleanup tested on Linux including kill escalation; filesystem mailbox assumes responsive local temporary storage.
