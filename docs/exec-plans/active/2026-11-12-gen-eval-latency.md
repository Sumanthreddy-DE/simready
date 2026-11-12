# gen-eval-latency — measure, then slim the analyze step for eval callers — task brief

**Status:** active
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

_(agent fills this in)_
