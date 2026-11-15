# GenCAD stop rules: full results (offline, 2026-11-12)

Detail page for the stop-rule experiment summarized in [gencad_eval.md](gencad_eval.md#stop-rules).
Brief and run log: `docs/exec-plans/completed/2026-11-12-gencad-stop-rules.md`.

Rules, applied to the saved QLoRA generations: R0 = no change (reproduces the original
scores). R1 = if the program does not parse, roll back to its last complete `solid=` line.
R2 = cut at the first repeated sketch block, then R1. R3 = keep at most K sketch blocks.

## Summary

R1 recovers all 12 truncated programs: VSR **88/100 → 100/100**; IoU with
invalid=0 **0.225081 → 0.229609**. Geometry improvement is small. R2 also recovers
12/12, with no material IoU improvement over R1. No rule makes a valid row invalid.
The valid-only mean falls because the 12 newly runnable rows have low IoU; its
denominator changes from 88 to 100. VSR here means the metric loads a solid,
not that the SimReady checker certifies its topology or simulation readiness.

### Controls and implementation

R0 reproduced all 100 committed validity flags, with maximum absolute IoU
difference **0.000326988368**, below the required 0.001. It passed before any rule
was scored. Negative control: R1 preserves all 88 previously valid programs
byte-identically. R2 changes 34/100 programs (including all 12 invalid rows).
Separate-process rescoring introduces tiny numerical differences even for
unchanged programs; these are not evidence of geometry gains.

Scorer: `scripts/gencad_stop_rules.py --rule R0|R1|R2|R3`, with `--k 1` through
`--k 8` for R3. Pure rule functions see only generated code. R1 preserves parsable
programs, otherwise rolls back to the last complete `solid=` statement. R2 cuts
before the first textually equal block after normalizing sketch indices, then
applies R1; different geometry or a different combine statement is not equal.
R3 retains at most K complete blocks and removes incomplete trailing material.

Metric: MecAgent `metrics/best_iou.py`, commit
`dc94ef8cce16a7d45da9767fab42c0625ec10cb1` (the expected revision), unchanged
notebook cell-5 logic, including STEP export, one fresh process per sample and
120 s timeout. Environment: Python 3.11.18, cadquery 2.8.0,
cadquery-ocp 7.9.3.1.1, trimesh 5.2.0, numpy 2.4.6, scipy 1.17.1.
All non-R0 runs completed without per-row errors. Scores and machine-readable
aggregate/bucket tables: `gencad/stop_rules/scores_*.json` and `summary.json`.
References were downloaded with `scripts/gencad_reference.py`; reference programs
and images remain in the gitignored cache.

### All 100 rows

Changed = byte changes versus generated R0 code; I→V / V→I = validity flips.
Δ both = mean IoU change against locally rescored R0 on the 88 rows valid under
both rules. R3 is an **eval-set sensitivity sweep, never a headline or selected K**.

| Rule | VSR | IoU valid-only | IoU invalid=0 | Changed | I→V | V→I | Δ both |
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

### By reference sketch count (reporting only)

Counts use `^wp_sketch\d+\s*=`, as in `gencad_analyse.py`, not sketch comments.
Bucket sizes are 57 / 18 / 12 / 13. Every non-R0 rule achieves 100% VSR in
every bucket, and every V→I count is zero. I→V counts for every non-R0 rule are
respectively 0 / 4 / 5 / 3. The both-valid denominators are 57 / 14 / 7 / 10.
These constants apply to each row below; R0 has zero changes and flips.

| Ref sketches | Rule | VSR | IoU valid-only | IoU invalid=0 | Changed | Δ both |
|---|---|---:|---:|---:|---:|---:|
| 1 | R0 | 57/57 | 0.311851 | 0.311851 | 0 | +0.00000000 |
| 1 | R1 | 57/57 | 0.311851 | 0.311851 | 0 | +0.00000000 |
| 1 | R2 | 57/57 | 0.311851 | 0.311851 | 5 | +0.00000000 |
| 1 | R3 K=1 | 57/57 | 0.309493 | 0.309493 | 16 | -0.00235832 |
| 1 | R3 K=2 | 57/57 | 0.311599 | 0.311599 | 7 | -0.00025242 |
| 1 | R3 K=3 | 57/57 | 0.311564 | 0.311564 | 4 | -0.00028676 |
| 1 | R3 K=4 | 57/57 | 0.311543 | 0.311543 | 2 | -0.00030851 |
| 1 | R3 K=5 | 57/57 | 0.311851 | 0.311851 | 0 | +0.00000000 |
| 1 | R3 K=6 | 57/57 | 0.311851 | 0.311851 | 0 | +0.00000000 |
| 1 | R3 K=7 | 57/57 | 0.311851 | 0.311851 | 0 | +0.00000000 |
| 1 | R3 K=8 | 57/57 | 0.311851 | 0.311851 | 0 | +0.00000000 |
| 2 | R0 | 14/18 | 0.199210 | 0.154941 | 0 | +0.00000000 |
| 2 | R1 | 18/18 | 0.163184 | 0.163184 | 4 | +0.00000015 |
| 2 | R2 | 18/18 | 0.163184 | 0.163184 | 9 | +0.00000000 |
| 2 | R3 K=1 | 18/18 | 0.164604 | 0.164604 | 16 | +0.00175133 |
| 2 | R3 K=2 | 18/18 | 0.163184 | 0.163184 | 10 | +0.00000000 |
| 2 | R3 K=3 | 18/18 | 0.163184 | 0.163184 | 7 | +0.00000015 |
| 2 | R3 K=4 | 18/18 | 0.163184 | 0.163184 | 5 | +0.00000015 |
| 2 | R3 K=5 | 18/18 | 0.163184 | 0.163184 | 5 | +0.00000000 |
| 2 | R3 K=6 | 18/18 | 0.163184 | 0.163184 | 4 | +0.00000000 |
| 2 | R3 K=7 | 18/18 | 0.163184 | 0.163184 | 4 | +0.00000015 |
| 2 | R3 K=8 | 18/18 | 0.163184 | 0.163184 | 4 | +0.00000000 |
| 3 | R0 | 7/12 | 0.147398 | 0.085982 | 0 | +0.00000000 |
| 3 | R1 | 12/12 | 0.100946 | 0.100946 | 5 | +0.00000000 |
| 3 | R2 | 12/12 | 0.100946 | 0.100946 | 10 | +0.00000000 |
| 3 | R3 K=1 | 12/12 | 0.108320 | 0.108320 | 12 | +0.01263564 |
| 3 | R3 K=2 | 12/12 | 0.100932 | 0.100932 | 11 | -0.00002329 |
| 3 | R3 K=3 | 12/12 | 0.100946 | 0.100946 | 9 | +0.00000000 |
| 3 | R3 K=4 | 12/12 | 0.100946 | 0.100946 | 8 | +0.00000000 |
| 3 | R3 K=5 | 12/12 | 0.100946 | 0.100946 | 7 | +0.00000000 |
| 3 | R3 K=6 | 12/12 | 0.100946 | 0.100946 | 5 | +0.00000000 |
| 3 | R3 K=7 | 12/12 | 0.100946 | 0.100946 | 5 | +0.00000000 |
| 3 | R3 K=8 | 12/12 | 0.100946 | 0.100946 | 5 | +0.00000000 |
| 4–8 | R0 | 10/13 | 0.091186 | 0.070143 | 0 | +0.00000000 |
| 4–8 | R1 | 13/13 | 0.079751 | 0.079751 | 3 | -0.00000742 |
| 4–8 | R2 | 13/13 | 0.079756 | 0.079756 | 10 | +0.00000000 |
| 4–8 | R3 K=1 | 13/13 | 0.077752 | 0.077752 | 12 | -0.00260517 |
| 4–8 | R3 K=2 | 13/13 | 0.079750 | 0.079750 | 10 | -0.00000836 |
| 4–8 | R3 K=3 | 13/13 | 0.079751 | 0.079751 | 9 | -0.00000742 |
| 4–8 | R3 K=4 | 13/13 | 0.079751 | 0.079751 | 6 | -0.00000742 |
| 4–8 | R3 K=5 | 13/13 | 0.079751 | 0.079751 | 5 | -0.00000742 |
| 4–8 | R3 K=6 | 13/13 | 0.079751 | 0.079751 | 3 | -0.00000742 |
| 4–8 | R3 K=7 | 13/13 | 0.079756 | 0.079756 | 3 | +0.00000000 |
| 4–8 | R3 K=8 | 13/13 | 0.079751 | 0.079751 | 3 | -0.00000742 |

### Greedy equivalence and evidence boundary

The saved run uses `do_sample=False`. Any deterministic prefix-local decision
retains exactly the text greedy inference would have emitted up to that cut;
no new generation or GPU is needed to score that retained program. This assumes
the same prompt/model/decoding and a stop implementation that discards the
look-ahead used to detect a repeated block. R1 is specifically end-of-generation
rollback: a temporarily unfinished call is normal during decoding, so R1 is not
an instruction to stop at the first incomplete token. R2 must observe a repeated
block before discarding it. These experiments do not demonstrate inference-time
token savings or an online stopping implementation.

Evidence is limited to one tuned model and these 100 saved rows. No reference
code or sketch count enters a rule; reference counts only stratify this report.
R3's K sweep is evaluated on this same set, so choosing K here would tune on the
eval set. R1 repairs syntax and raises VSR without changing the original 88 valid
programs, but does not solve geometry fidelity. R2's extra text cuts provide no
material fidelity benefit. No retraining, new generation, filled-voxel scoring,
checker re-evaluation, or independent-model validation was performed.
