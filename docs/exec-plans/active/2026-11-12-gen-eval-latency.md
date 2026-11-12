# gen-eval-latency — measure, then slim the analyze step for eval callers — task brief

**Status:** done
**Last verified:** 2026-11-12

BACKLOG S3 `gen-eval-latency`. Written for an agent on the VPS in opencode. Claude reviews
and merges; you stop after the last commit.

## Problem

Generation-eval prompts ran 40–143 s wall against a ~60 s budget
(`docs/validation/geometry_gen_eval.md` §3). Part of that is LLM round-trips, which you cannot
change. The rest is our own work per prompt:

- `build_part` (`simready/gen/build.py:181`) builds in a spawn child process (hang guard, keep it).
- `analyze_geometry` (`simready/copilot/tools.py:172`) runs `analyze_file_safe`
  (`simready/pipeline.py:280`), a spawn child that pays interpreter + torch import on every
  call (its own docstring, `pipeline.py:297`), then renders a PNG (`render_image=True` by
  default) and always writes a healed STEP (`_maybe_heal_step`, no flag).
- `tests/test_gen_e2e.py` then analyzes the final part a second time via
  `analyze_generated_part` (`simready/gen/verify.py:10`, already `render_image=False`).

§3 of the eval doc says the analyze is "in-process"; that is stale (the subprocess guard
landed the same day). Measure, do not trust either text.

## Environment

```bash
export MAMBA_ROOT_PREFIX=~/simready-fresh/mamba/root PIP_CACHE_DIR=~/simready-fresh/cache/pip XDG_CACHE_HOME=~/simready-fresh/cache PATH=~/simready-fresh/mamba/bin:$PATH
PY=/home/sumanth/simready-fresh/mamba/root/envs/simready-fix/bin/python
```

Spell out `$PY` in every command. Never `micromamba shell init`, never edit dotfiles, no installs.
Never read `.env`.

## Steps

1. Setup: `git -C /home/sumanth/projects/Mech/SimReady worktree add /tmp/simready-gen-latency -b perf/gen-eval-latency main`.
   Work only in `/tmp/simready-gen-latency`. Never touch the main checkout.
2. Baseline full suite in the worktree, 20-minute timeout, with this exact prefix (dummy values
   keep `tests/test_gen_e2e.py` collected and deselected, as in the 2026-11-11 OCC-split run):
   `OPENAI_BASE_URL=https://example.invalid/v1 OPENAI_MODEL=offline-control OPENAI_API_KEY=offline-control $PY -m pytest -q -p no:cacheprovider`.
   Expected near `239 passed, 10 skipped, 5 deselected`; record the exact line you get.
3. New script `scripts/time_gen_eval.py` — no LLM calls. Specs: the five final specs from the
   v2.1 table in `geometry_gen_eval.md` (normal_box, thin_plate, l_bracket, bracket_with_hole,
   small_feature_box), written in the real `PartSpec` format (read `simready/gen/spec.py`;
   validate each with `PartSpec.model_validate`). For each spec, 3 rounds, time separately:
   `build_part`; `analyze_file_safe`; PNG render; heal; and the whole `analyze_generated_part`.
   Also time one child that only imports what the analyze child imports (to split import cost
   from analysis cost). Print a table (stage × first round / mean of rounds 2–3) and write
   JSON to `data/gen_eval/timing_<label>.json` (gitignored). Commit the script alone:
   `perf: add offline timing script for the generation eval path`.
4. Run it (`--label before`). From the numbers, name the dominant stages. Write them into the
   `## Result` section below before changing any code.
5. Implement only levers the numbers justify, each its own commit with tests:
   - a. A `heal_step: bool = True` keyword on `analyze_geometry`; `analyze_generated_part`
     passes `render_image=False, heal_step=False`. Default behaviour unchanged.
   - b. If the agent-loop `analyze_geometry` call is a large share: a way for eval callers to
     run it slim **without** changing the tool schema the LLM sees and without changing UI or
     CLI behaviour. Propose it in the Result section first; implement only if it is small and
     testable. No environment-variable switches.
   - Not in scope: a persistent build/analyze worker. If the import cost dominates, estimate
     its saving from your numbers in the Result section and stop there.
   Tests: default call still returns `image_path` and `healed_step_path`; slim call returns
   neither and writes no file under `data/copilot_renders/` or `data/healed_steps/`. Mark any
   test that needs pythonocc with `@pytest.mark.occ`.
6. Re-run the timing script (`--label after`) and the full suite with the same prefix. Allowed
   difference: only your new tests added; no new failures or skips.
7. Fill `## Result`: commits, before/after table, suite lines, what you did not do and why.
   Set `**Status:** done`. Commit: `docs: record gen-eval-latency results`. Stop.

## Rules

- No live LLM runs. The VPS `.env` points at D Labs, which corrupts tool-call arguments; the
  owner decides a live re-run later.
- Never edit `BACKLOG.md`, `STATE.md`, `README.md`, `docs/validation/`, `requirements.txt`,
  `environment.yml`, `weights/`, memory files. No `/save-session`. No push, no merge.
- No AI attribution in commits.

## Result

### Before implementation (2026-11-12)

Worktree `/tmp/simready-gen-latency`, branch `perf/gen-eval-latency`, base `f073d31`.
Timing script committed alone as `4b72ae5`.
Baseline: `239 passed, 10 skipped, 5 deselected, 3 warnings in 136.85s (0:02:16)`.

Measured rounds 2–3, averaged across the five parts: analysis child wall ~8.97 s,
import-only child ~3.92 s, build ~1.16 s, PNG ~0.033 s, heal/export ~0.024 s,
final verifier ~8.89 s. Analysis dominates; artifact work is under 1% of analysis.
The agent-loop analyze path is therefore a large share of local work, but a slim
agent-dispatch option would save only ~0.057 s per call here. **Do not implement
lever b**: no measurable latency case for new agent configuration. Implement the
explicit lever a to eliminate unnecessary verifier output files, not as a claimed
material speedup. The alternative of removing subprocess isolation is rejected:
the hang guard matters more than these timings.

Ruling: the import-only child mirrors the worker's pipeline import, including
interpreter startup/exit; it does not include later lazy torch/PyG imports during
inference. It is a lower-bound attribution probe, not total import cost. Reusing
a worker might avoid ~3.92 s per analyze (~7.83 s for two analyses per prompt)
from this measured component alone, before any lazy-import/model-reuse benefit;
a persistent worker is outside scope.

Pre-flight: the timing script consumes the unchanged analysis/verifier APIs;
lever a adds only a default-preserving keyword. No shared-interface conflict.
This brief is the execution authority; no separate spec is named. Execution
progress and rulings are recorded here to keep all task work in the prescribed
worktree and existing plan structure.

Lever a committed as `a1e7aa7`. Regression evidence: the default artifact case
passed before the change; the slim verifier case failed on `healed_step_path`
being present. After implementation both pass; targeted tools/verifier suite:
`34 passed, 1 warning in 23.54s`. Tests use real OCC, a real child analysis,
and fresh temporary directories to check actual artifact presence/absence;
the whole module carries `pytest.mark.occ`.

### Before / after wall timings

Seconds; each cell is the arithmetic mean across all five parts. First = round 1
of each part; later = mean of rounds 2–3 of each part (fresh child each time,
same long-lived parent). These are not cold-cache measurements. Raw 15-round
records per run and exact specs are in ignored `data/gen_eval/timing_before.json`
and `data/gen_eval/timing_after.json`; after-run stdout is `timing_after.log` there.

| Stage | Before first | Before later | After first | After later |
|---|---:|---:|---:|---:|
| Import-only child | 4.0370 | 3.9151 | 4.1480 | 4.5067 |
| `build_part` | 1.2095 | 1.1627 | 1.2834 | 1.1802 |
| `analyze_file_safe` | 9.2185 | 8.9717 | 9.4804 | 8.9963 |
| PNG render | 0.0513 | 0.0333 | 0.0569 | 0.0337 |
| Heal/export | 0.0324 | 0.0242 | 0.0248 | 0.0237 |
| Whole `analyze_generated_part` | 8.7674 | 8.8884 | 9.2143 | 10.6654 |

Stages overlap: the whole verifier includes a second analysis, so do not sum it
with standalone analysis as if they were exclusive sub-stages of one call.
PNG and heal/export are deliberately timed independently in **both** runs even
though the verifier no longer invokes either. The before verifier already omitted
PNG; lever a removes only its ~0.024 s heal/export work.

**No measured speedup.** After verifier's later mean rose, dominated by the
small-feature part (18.0057 s later mean versus 9.2312 s before); other after
part means were 8.4539–9.3042 s. Keep that outlier in the table: three rounds
cannot establish a performance regression or speedup of tens of milliseconds.
The reliable result is elimination of verifier artifacts with unchanged analysis
semantics. No live endpoint latency or end-to-end prompt-budget claim is made.

### Verification and completion

- Before: `239 passed, 10 skipped, 5 deselected, 3 warnings in 136.85s (0:02:16)`.
- After, same exact offline-control prefix and no-cache pytest command:
  `241 passed, 10 skipped, 5 deselected, 3 warnings in 161.19s (0:02:41)`.
- Difference: exactly the two new OCC artifact-policy cases. No new failures,
  skips or deselections. Existing warnings: anyio/pytest alias and torch JIT
  deprecation. Both timing runs completed all five specs × three rounds.
- Review: self-review of the whole branch against steps 1–7; no subagent
  delegation requested. Checked the default/schema contract, actual output-file
  assertions, spawn-safe script imports, label/path validation, and overlapping
  timing interpretation. `git diff --check` clean. No deferred code findings.
- Ruling: use this Result section as the execution ledger, rather than creating
  a separate harness workspace or task briefs. This preserves the user's exact
  file/commit sequence and worktree-only constraint; cost if wrong is weaker
  automated resume bookkeeping. The import-probe ruling above costs potentially
  understating worker-reuse savings; it does not justify removing the hang guard.
- Not done: lever b (artifact cost too small for new configuration), persistent
  workers (explicitly out of scope), LLM runs (prohibited). No edits to the stale
  validation document because `docs/validation/` is prohibited by this brief.
- Commits: `4b72ae5` timing script; `a1e7aa7` lever a and regression tests;
  final commit titled `docs: record gen-eval-latency results` contains this record.
  Execution stops immediately after that commit for owner review/merge.
