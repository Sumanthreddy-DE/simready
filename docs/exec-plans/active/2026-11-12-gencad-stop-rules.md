# gencad-stop-problem — offline stop rules on the saved generations — task brief

**Status:** active
**Last verified:** 2026-11-12

BACKLOG S2 `gencad-stop-problem`, on the path to S1 `apply-submit-mecagent-test`. Written for
an agent on the VPS in opencode. Claude reviews and merges; you stop after the last commit.

## Problem

Tuned Qwen2.5-VL-3B on MecAgent's GenCAD-Code test, `hundred_subset`: VSR 88/100. All 12
failures hit `max_new_tokens` 1825 mid-line (`'(' was never closed`); 11 of 12 wrote more
sketches than the reference. Over-generation also happens in valid rows (idx 37: 5 sketches
vs 1). Full record: `docs/validation/gencad_eval.md`.

The 100 raw outputs are committed: `docs/validation/gencad/gen_qwen25vl3b_qlora.jsonl`
(`idx`, `raw`, `code`; `code` = `raw` with one Markdown fence stripped). Decoding was
greedy (`do_sample=False`, notebook `notebooks/gencad_baseline.ipynb` cell 4). So any rule
that only cuts the output at a point decided from the text before it gives **exactly** what a
stop rule at inference would give. No GPU, no new generation.

Program shape (GenCAD style), per sketch k:
```
# Generating a workplane for sketch k
wp_sketchk = cq.Workplane(cq.Plane(...))
loopk=wp_sketchk.moveTo(...)...close()
solidk=wp_sketchk.add(loopk).extrude(...)
solid=solid0              # k = 0
solid=solid.union(solidk) # k > 0 (or .cut)
```
A single "stop after the first `solid=` line" rule is wrong: it would cut every multi-sketch part.

## Decided — do not change these

1. **No rule may use the reference** (its sketch count, length or code). Rules see only the
   generated text. Any parameter (e.g. a sketch cap K) is never tuned on these 100 rows for a
   headline number.
2. **Rules to score** (pure functions of the generated `code` string):
   - `R0` unchanged — positive control.
   - `R1` trim-incomplete: if the program does not end on a complete statement, cut back to
     the end of the last complete `solid=` line. Programs that already end complete are
     returned byte-identical.
   - `R2` repeat-stop: stop before the first sketch block whose text, with sketch indices
     normalised (`sketch3`/`loop3`/`solid3` → `N`), equals an earlier block; then apply R1.
   - `R3` sketch-cap sweep, K = 1..8: keep at most K complete sketch blocks. **Sensitivity
     table only, never a headline** (K would be chosen on the eval set).
3. **Scoring is the notebook's cell 5, unchanged in logic**: MecAgent's own
   `metrics/best_iou.py` (`_load_solid_from_code`, `_normalized_mesh`, `iou_best`), each sample
   in its own Python process, 120 s timeout; VSR = loads to a solid; IoU over valid rows
   (MecAgent's definition) and with invalid = 0. Clone
   `https://github.com/MecAgent/mecagent-technical-test` to
   `data/gencad/mecagent-technical-test` (gitignored) and record its commit SHA (HEAD was
   `dc94ef8` on 2026-11-12; if it differs, use it anyway and say so).
4. References: `scripts/gencad_reference.py` writes `data/gencad/gt_hundred.json` (downloads
   the test parquet from Hugging Face into the gitignored `data/gencad/`). No dataset content (images,
   reference programs) is committed anywhere.
5. **Positive control first.** R0 must reproduce the committed
   `docs/validation/gencad/scores_qwen25vl3b_qlora.json`: the same `valid` flag on all 100
   rows and IoU max abs difference ≤ 1e-3 (a 2026-10 local re-score matched to 4e-4). If it
   does not, stop, record the mismatch in `## Result`, commit, and do not score any rule.
6. **Negative control.** Assert in code that R1 returns all 88 valid programs byte-identical,
   and report how many programs R2 changes.

## Environment

```bash
export MAMBA_ROOT_PREFIX=~/simready-fresh/mamba/root PIP_CACHE_DIR=~/simready-fresh/cache/pip XDG_CACHE_HOME=~/simready-fresh/cache PATH=~/simready-fresh/mamba/bin:$PATH
PY=/home/sumanth/simready-fresh/mamba/root/envs/simready-fix/bin/python   # repo tests, pandas
```

**The one allowed install:** a new env `gencad` for cadquery scoring (owner-approved 2026-11-12):
`micromamba create -n gencad python=3.11 -y`, then
`~/simready-fresh/mamba/root/envs/gencad/bin/python -m pip install cadquery trimesh scipy numpy`.
Call it `$GQ`. Never `micromamba shell init`, never edit dotfiles, never touch `simready-fix`
except to run it. At the end, if `~/.conda` or `~/.mamba` exist and did not exist at your
start, delete them and say so. Report `du -sh ~/simready-fresh`. Never read `.env`.

## Steps

1. Setup: `git -C /home/sumanth/projects/Mech/SimReady worktree add /tmp/simready-stop-rules -b exp/gencad-stop-rules main`.
   Work only in `/tmp/simready-stop-rules`.
2. Baseline repo suite: `OPENAI_BASE_URL=https://example.invalid/v1 OPENAI_MODEL=offline-control OPENAI_API_KEY=offline-control $PY -m pytest -q -p no:cacheprovider`
   (20-minute timeout). Expected `241 passed, 10 skipped, 5 deselected`; record the exact line.
3. `scripts/gencad_stop_rules.py`: the rule functions R1–R3 at module level using only the
   standard library (so `from scripts.gencad_stop_rules import ...` works in tests without
   cadquery); `main()` imports `gencad_common` and does the scoring. CLI:
   `--rule R0|R1|R2|R3 [--k N] [--limit N]`. Writes
   `docs/validation/gencad/stop_rules/scores_<rule>[_k<N>].json` (same row format as the
   committed scores file) and prints `n / VSR / IoU valid-only / IoU invalid=0`.
   `tests/test_gencad_stop_rules.py`: R1 identity on a complete program; R1 cut on a program
   ending mid-call; R2 stops at a repeated block and not at a merely similar one; R3 keeps
   exactly K blocks; none of them ever leaves an unclosed parenthesis. Commit:
   `gencad: add offline stop-rule scorer`.
4. Run `$PY scripts/gencad_reference.py`, clone the MecAgent repo, then R0 with `$GQ`
   (positive control, decision 5). Then R1, R2, R3 for K = 1..8.
5. Table for each rule: VSR, IoU valid-only, IoU invalid=0, rows changed vs R0, rows that
   flipped invalid→valid and valid→invalid, mean IoU change on rows valid under both. Split
   by reference sketch count with the buckets `gencad_eval.md` already uses (1 / 2 / 3 / 4–8) — reporting by reference
   count is fine; *choosing* a rule by it is not.
6. Docs: new section `## Stop rules (offline, 2026-11-12)` in `docs/validation/gencad_eval.md`
   just before `## Next steps (from this evidence)`, with the tables, the greedy-equivalence argument, the MecAgent
   commit SHA, and an evidence boundary (one model, 100 rows, R3 is tuned on the eval set). Do
   not edit any other part of that file. Commit results + docs:
   `gencad: score stop rules on the saved generations`.
7. Full suite again with the same prefix: only your new tests added.
8. Fill `## Result` (commits, both suite lines, positive-control numbers, the table, what you
   did not do). Set `**Status:** done`. Commit: `docs: record gencad stop-rule results`. Stop.

## Rules

- Never edit `BACKLOG.md`, `STATE.md`, `README.md`, notebooks, `weights/`,
  `requirements.txt`, `environment.yml`, memory files, or other files under `docs/validation/`
  except the one new section and the new `stop_rules/` folder. No `/save-session`.
- No push, no merge. No AI attribution in commits.
- Plain report voice: numbers first, no marketing words. If no rule helps, say so — a negative
  result is a result.

## Result

_(agent fills this in)_
