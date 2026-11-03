# GenCAD examples handoff — 2026-11-03

## Result and commits

Executed `docs/exec-plans/active/2026-11-03-gencad-walkthrough-examples.md` in
`/home/sumanth/projects/Mech/SimReady-walkthrough`, branch `docs/gencad-examples`,
starting at `110dd2f`. The branch was clean before work.

1. `e6b228e` — `gencad-examples: export selected references and render measured pairs`
2. `5df4fa0` — `gencad-examples: add four-case walkthrough with paired renders`
3. This handoff commit — `gencad-examples: record verification and provenance handoff`
   (resolve its SHA with `git log -1 --format=%H -- docs/handoff-2026-11-03-gencad-examples.md`).

Files changed:

- `scripts/gencad_export_reference_steps.py`: optional `--idx`, validates selected
  rows; no argument still exports all valid rows. Reports the number exported this run.
- `scripts/gencad_examples.py`: imports the existing STEP reader, tessellator and
  painter; replaces all triangle colours with neutral grey. Prints measured XYZ
  bounds, face/triangle counts, dimensions and PNG bytes as JSON.
- `docs/validation/gencad_examples.md`: four selected examples, six renders,
  exact six-line idx 350 excerpt, sources and limits.
- `docs/validation/gencad/examples/{400,5699,4836}_{reference,generated}.png`.
- `docs/validation/gencad_eval.md`: exactly one added link line under
  “Files and how to reproduce”.
- This handoff.

## Quoted evidence (read from saved files, not re-scored)

All source paths in this table are relative to `docs/validation/gencad/`, except
`gencad_eval.md`, which is in the parent directory.

| idx | Quoted numbers / claim | Source |
|---|---|---|
| 400 | valid, IoU 1.0; reference/generated sketches 1/1 | `scores_qwen25vl3b_qlora.json`, `per_row_analysis.json` |
| 350 | invalid, IoU 0; reference/generated sketches 3/8; unclosed `(` at line 38 | same two files |
| 350 | max_new_tokens 1825; last six program lines copied exactly | `gencad_eval.md` Setup and failure discussion; `gen_qwen25vl3b_qlora.jsonl`, `code` field |
| 5699 | shell 0.8303417328270625 → 0.830; filled 0.8934029071934402 → 0.893 | `iou_shell_vs_filled.json` |
| 5699 | generated NeedsAttention, overall 47.54008195229939 → 47.5; SelfIntersection Major | `checker_generated.jsonl` |
| 5699 | reference ReviewRecommended, overall 77.74071888128917 → 77.7; no SelfIntersection flag | `checker_reference.jsonl` |
| 4836 | shell 0.010038165943430752 → 0.010; filled 0.5877957658779577 → 0.588 | `iou_shell_vs_filled.json` (local shell variant, not the slightly different Colab value) |
| 4836 | reference outer/inner r 0.138/0.055, length 0.734; generated 0.182/0.079, length 0.750 | `gencad_eval.md` metric finding |

Context on the page (6k examples, one epoch, 100-row eval; checker largest side
100 mm; scale-normalized IoU; two self-intersection cases are examples, not a
rate) comes from `docs/validation/gencad_eval.md`.

## Fresh geometry measurements and PNG checks

Axis-aligned bounds use OCC `brepbndlib.AddOptimal(shape, bbox, False, False)`
before tessellation, with neither mesh bounds nor shape-tolerance expansion.
Face counts use `simready.occ_utils.iter_faces`. Original GenCAD coordinate
units, not physical mm. The page rounds to six decimals.

| idx | role | bbox X × Y × Z | faces | triangles | PNG bytes |
|---|---|---|---|---|---|
| 400 | reference | 0.75 × 0.615789473684 × 0.0078125 | 6 | 12 | 3668 |
| 400 | generated | 1.5 × 1.252631578947 × 0.015625 | 6 | 12 | 3660 |
| 5699 | reference | 1.50087450218102 × 1.5 × 0.0703125 | 15 | 664 | 3662 |
| 5699 | generated | 1.50006006537872 × 1.3079208187263598 × 0.0390625 | 14 | 452 | 3667 |
| 4836 | reference | 0.276315789474158 × 0.276315789474 × 0.734375 | 4 | 208 | 5425 |
| 4836 | generated | 0.363157894736579 × 0.363157894736 × 0.75 | 4 | 208 | 5356 |

Each PNG is 800×600, valid per Pillow, ≤150,000 bytes, and contains exactly
white `(255,255,255)` and grey `(153,153,153)`. Same fixed projection for both
roles, independently fitted; these are not common-scale comparison images.
No visual review was possible in this run. The laptop owner must inspect every
image; no picture-based diagnosis is claimed here.

Reference programs, downloaded parquet, downloaded metric and the three exported
reference STEPs are under ignored `data/gencad/`. No input images were downloaded.
No dataset reference programs or reference STEPs were staged or committed.
CadQuery 2.8.0 and trimesh 5.2.0 were installed only in the allowed new `gencad`
environment (Python 3.11.18); `simready-fix` was only run.

## Commands and verification

Commands ran on the Linux VPS from this worktree. Environment prefix below was
set on every micromamba call (each Bash invocation has its own environment):

```bash
export MAMBA_ROOT_PREFIX=~/simready-fresh/mamba/root
export PIP_CACHE_DIR=~/simready-fresh/cache/pip
export XDG_CACHE_HOME=~/simready-fresh/cache
export PATH=~/simready-fresh/mamba/bin:$PATH
```

Exact task-producing commands, in order (the pytest command ran twice):

```bash
git status --short --branch
git worktree list
micromamba run -n simready-fix python -m pytest -q
micromamba create -n gencad python=3.11 -y
micromamba run -n gencad pip install cadquery trimesh scipy pandas pyarrow
micromamba run -n gencad python scripts/gencad_reference.py
micromamba run -n gencad python scripts/gencad_export_reference_steps.py --idx 400 5699 4836
micromamba run -n simready-fix python scripts/gencad_examples.py
micromamba run -n gencad python scripts/gencad_export_reference_steps.py --help
git diff --check
git diff -- scripts/gencad_export_reference_steps.py
git status --short
git add scripts/gencad_export_reference_steps.py scripts/gencad_examples.py
git commit -m "gencad-examples: export selected references and render measured pairs"
git diff --numstat
git diff -- docs/validation/gencad_eval.md
git add docs/validation/gencad/examples docs/validation/gencad_examples.md docs/validation/gencad_eval.md
git commit -m "gencad-examples: add four-case walkthrough with paired renders"
micromamba run -n simready-fix python -m pytest -q
git diff 110dd2f..HEAD --stat
git diff 110dd2f..HEAD -- scripts/gencad_export_reference_steps.py scripts/gencad_examples.py docs/validation/gencad_examples.md docs/validation/gencad_eval.md
git check-ignore data/gencad/gt_hundred.json data/gencad/reference_steps/gt_400.step data/gencad/reference_steps/gt_5699.step data/gencad/reference_steps/gt_4836.step
```

Baseline: **231 passed, 11 skipped, 3 warnings**, 109.33 s.
After changes: **231 passed, 11 skipped, 3 warnings**, 96.43 s.
Both are full `python -m pytest -q` runs in `simready-fix`. No new tests added.
Warnings unchanged: anyio pytest CallSpec deprecation and two torch.jit deprecations.

Exact successful image-validation command:

```bash
micromamba run -n simready-fix python -c 'from pathlib import Path; from PIL import Image; paths=sorted(Path("docs/validation/gencad/examples").glob("*.png")); assert len(paths)==6; [(Image.open(p).verify(), print(str(p), Image.open(p).size, p.stat().st_size)) for p in paths]; assert all(Image.open(p).size==(800,600) and p.stat().st_size<=150000 and {c for n,c in Image.open(p).getcolors(480000)}=={(153,153,153),(255,255,255)} for p in paths)'
```

The first image-validation attempt incorrectly called `verify()` after reading
pixels and failed with “verify must be called directly after open”. The command
above reopens the file for each check and passed on all six. This was a probe
error; no render change was needed.

Exact excerpt and initial link-validation command (before writing this handoff):

```bash
python -c 'import json,pathlib,re; root=pathlib.Path("."); p=root/"docs/validation/gencad_examples.md"; text=p.read_text(); gen=next(json.loads(l) for l in (p.parent/"gencad/gen_qwen25vl3b_qlora.jsonl").read_text().splitlines() if json.loads(l)["idx"]==350); excerpt=text.split("```python\n")[1].split("\n```")[0]; assert excerpt=="\n".join(gen["code"].splitlines()[-6:]); links=re.findall(r"\]\(([^)]+)\)",text); missing=[x for x in links if not (p.parent/x.split("#")[0]).exists()]; assert missing==["../handoff-2026-11-03-gencad-examples.md"],missing; print("Exact six-line excerpt verified; links verified except pending handoff"); print("page words",len(text.split()))'
```

The exact six-line excerpt matched; the only missing link was this then-pending
handoff. Final validation checks all page file targets exist.
Read-only Python inspection also printed the four selected score rows, checker
rows, and the idx 350 excerpt directly from their saved JSON/JSONL sources.

Final review: self-review of the whole diff against the task brief; no subagent
was dispatched. Changed paths match the permitted scope. No application code,
tests, README, backlog, state, memory, weights or dependencies files were edited.

### Cleanup

`~/.conda` and `~/.mamba` were absent before the baseline. Micromamba created
`~/.conda/environments.txt` (only the new gencad env path) and
`~/.mamba/pkgs/urls.txt` (empty). Inspected both before removing these files with
the file-edit tool, then removed the empty directories:

```bash
rmdir /home/sumanth/.conda /home/sumanth/.mamba/pkgs /home/sumanth/.mamba
du -sh /home/sumanth/simready-fresh
test ! -e /home/sumanth/.conda
test ! -e /home/sumanth/.mamba
```

Both absence checks passed; `du -sh` reported **7.2G**. No shell initialization
or dotfile edits. No push or merge performed.

## Outstanding / decisions

- Laptop visual review remains; I cannot view these images in this run.
- Idx 350 has no generated geometry; its six-line excerpt replaces a render pair.
  This follows the explicit three-index export/render list, rather than fabricating
  an output for the failed program.
- The exporter default path was inspected as unchanged (all valid rows), but not
  run over all 88 references: this task exported only 400, 5699 and 4836.
- Saved scores and checker results were not recomputed, as required.
- The plan file remains active, since edits to it were outside the allowed file list.
