# gencad-stop-problem — offline stop rules on the saved generations — task brief

**Status:** done
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

Worktree: `/tmp/simready-stop-rules`, branch `exp/gencad-stop-rules`, base
`836f553`. Implementation and scoring stayed in that worktree; the only install
was the approved `gencad` environment.

Commits:
- `e2b3451` — `gencad: add offline stop-rule scorer`
- `9b3436d` — `gencad: score stop rules on the saved generations`
- Final record commit: `docs: record gencad stop-rule results` (this commit).

Both suites used the exact offline environment prefix and pytest command in
step 2, with a 20-minute command timeout. Exact summary lines:

```text
241 passed, 10 skipped, 5 deselected, 3 warnings in 169.51s (0:02:49)
260 passed, 10 skipped, 5 deselected, 3 warnings in 175.33s (0:02:55)
```

Only the 19 new tests were added. Rule tests first failed collection because the
new module did not exist, then passed after implementation; positive-control
gate tests were added afterward and passed. No claim of test-first coverage is
made for those four gate tests. Rules were also applied to all 100 saved programs:
all 1,000 R1/R2/R3 output combinations parse successfully. The evaluation-doc edit
was checked mechanically to be an insertion of only the permitted section.
Final code review was self-review; no fresh-context reviewer was dispatched.

**Positive control:** R0 completed all 100 rows before any rule was scored:
zero validity-flag mismatches; maximum absolute IoU difference
`0.00032698836756284155` (threshold `0.001`). R0 VSR `88/100`, IoU valid-only
`0.2557739051600322`, IoU invalid=0 `0.2250810365408283`. MecAgent clone SHA:
`dc94ef8cce16a7d45da9767fab42c0625ec10cb1`, matching the expected revision.
The first R0 attempt hit the shell's 20-minute timeout at 98 rows; R0 was rerun
in full with a longer shell timeout. Each child retained the required 120 s
timeout. Scoring was subsequently interrupted after R3 K=3; the six complete
100-row files and R0 gate were rechecked before resuming at K=4. No partial
scores were used.

**Negative control:** R1 preserves all 88 originally valid programs
byte-identically. R2 changes 34/100 generated programs. No rule uses reference
code, sketch count or length; references are used for scoring and stratification.

| Rule | VSR | IoU valid-only | IoU invalid=0 | Changed vs R0 | I→V | V→I | Mean Δ IoU both-valid |
|---|---:|---:|---:|---:|---:|---:|---:|
| R0 | 88/100 | 0.255774 | 0.225081 | 0 | 0 | 0 | +0.00000000 |
| R1 | 100/100 | 0.229609 | 0.229609 | 12 | 12 | 0 | -0.00000082 |
| R2 | 100/100 | 0.229610 | 0.229610 | 34 | 12 | 0 | +0.00000000 |
| R3 K=1 | 100/100 | 0.229146 | 0.229146 | 56 | 12 | 0 | -0.00053986 |
| R3 K=2 | 100/100 | 0.229464 | 0.229464 | 38 | 12 | 0 | -0.00016630 |
| R3 K=3 | 100/100 | 0.229446 | 0.229446 | 29 | 12 | 0 | -0.00018656 |
| R3 K=4 | 100/100 | 0.229433 | 0.229433 | 21 | 12 | 0 | -0.00020065 |
| R3 K=5 | 100/100 | 0.229609 | 0.229609 | 17 | 12 | 0 | -0.00000084 |
| R3 K=6 | 100/100 | 0.229609 | 0.229609 | 12 | 12 | 0 | -0.00000084 |
| R3 K=7 | 100/100 | 0.229610 | 0.229610 | 12 | 12 | 0 | +0.00000002 |
| R3 K=8 | 100/100 | 0.229609 | 0.229609 | 12 | 12 | 0 | -0.00000084 |

The both-valid denominator is 88. R3 is sensitivity-only: no K was selected.
Full bucket tables (1 / 2 / 3 / 4–8 sketches; n=57/18/12/13) are in the new
`docs/validation/gencad_eval.md` section; all 55 aggregate/bucket records are in
`docs/validation/gencad/stop_rules/summary.json`. Reference sketch counts use
the existing analysis script's workplane-assignment regex, not comments.

**Finding:** R1 repairs all 12 truncations while leaving the original 88 valid
programs intact. Invalid=0 mean IoU improves by about 0.00453; fidelity remains
low. R2 adds no material metric improvement. The tiny both-valid deltas for
unchanged programs are numerical rescoring variation. R1 is end-of-generation
rollback; the greedy-prefix argument does not establish online stopping or
token savings. R2 needs look-ahead before discarding the duplicate block.

**Environment:** Python 3.11.18; cadquery 2.8.0; cadquery-ocp 7.9.3.1.1;
trimesh 5.2.0; numpy 2.4.6; scipy 1.17.1. `du -sh ~/simready-fresh`:
`6.3G`. Both `~/.conda` and `~/.mamba` existed at start and remain; neither was
deleted. Reference parquet/programs and the metric clone remain gitignored.
The temporary table-aggregation helper is in `data/gencad/` (gitignored), not
a new committed CLI.

**Not done:** new generation, GPU work, retraining, parameter selection,
filled-voxel scoring, checker reruns, other models, online stop integration,
push, merge, or edits to the prohibited project/status/environment files.
No dataset images or reference programs were committed. No `.env` was read.
