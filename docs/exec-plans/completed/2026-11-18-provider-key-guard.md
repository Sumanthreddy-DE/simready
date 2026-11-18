# Provider-key guard coordination plan

**Status:** done
**Last verified:** 2026-11-18

**Goal:** Classify the known tool-call `reason` contamination as unscored infrastructure without excusing independent model errors.
**Architecture:** Preserve provider evidence through reply parsing; validate the spec with only the known contamination removed to detect independent defects. Return `infra_error`, `error_type=provider_arguments`, null passed/partial. Never build contaminated input.
**Spec:** User-approved policy in this session and BACKLOG.md `bench-provider-key-guard`; historical shapes in docs/validation/geometry_gen_eval.md v2.4.
**Execution:** One Orca worker, `dlab/gpt-6-1-sol`; coordinator reviews and merges.

## Constraints and review focus
- Initial product scope: simready/bench/attempt.py and tests/test_bench_attempt.py. Review expanded it to simready/bench/replay.py and tests/test_bench_replay.py because regrade lost provider evidence and changed scoring. Mandatory worker report is allowed separately.
- Known locations: tool envelope and spec root, including stringified spec and direct steps arguments. Missing steps plus reason alone is the explicit replacement exception.
- Other keys, invalid dimensions, unknown operations and reference failures stay model failures. Text-only replies do not acquire provider attribution. Inputs remain unmodified.
- Existing ParsedReply callers stay compatible. Runner/replay exclusions must continue through existing infra_error handling.
- No network/provider calls, package installations or pushes.

## Tasks
- [x] Verify clean sp1-bench base efe3f15; attempt baseline 29 passed. Full baseline 20 failed / 273 passed / 27 skipped / 6 deselected.
- [x] Behavioral probe failed five known-contamination cases on base; clean negative controls passed; identical-code diff empty. Focused regression selection failed on base (29 deselected).
- [x] Registered brief, ran one GPT-6.1 Sol worker, checked report/hotspot. One send round trip fixed regrade exclusion loss; final delegation check PASS. Worker mutation: disabled guard 28 failed / 35 passed; restored 63 passed.
- [x] Merged as 0ea126e into /tmp/simready-sp1-review; full command 342 passed / 20 failed / 27 skipped / 6 deselected, same 20 baseline failure identities. Closed Orca run run_190c2bf13256.
- [x] Main BACKLOG closure records merge SHA and test counts; completion report accompanies documentation commit.

## Harness observations
- delegation check matches output but ignores command exit status: checks use a success marker printed only after assertions/tests succeed.
- The unchanged-base FAIL requirement applies to new-behavior checks, not baseline suites or identical-code comparisons (which must pass).
- opencode stats defaults to rounded global totals without per-model breakdown; model baseline was captured shortly after the initial total snapshot. It cannot isolate this run from concurrent sessions or measure actual provider charges (all recorded costs zero).
