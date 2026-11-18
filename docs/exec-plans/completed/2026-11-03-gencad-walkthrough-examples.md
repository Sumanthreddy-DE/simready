# apply-call-walkthrough — four GenCAD examples — task brief

**Status:** done
**Last verified:** 2026-11-03

BACKLOG S1 `apply-call-walkthrough` (remaining part: "3-4 generated examples"). Written for
an agent on the VPS in opencode; reviewed on the laptop, where Claude checks every image
(you cannot view images — say so wherever it matters, never describe a picture you did not
measure). Worktree `~/projects/Mech/SimReady-walkthrough`, branch `docs/gencad-examples`,
cut from `main`.

**A second agent works in parallel** in `~/projects/Mech/SimReady` (branch `feat/gen-cli`).
Never touch that checkout, its branch, `simready/`, `tests/`, `README.md` or the env
`simready-fix` except to **run** it (decision 3).

## Deliverable

`docs/validation/gencad_examples.md` — a one-page walkthrough aid for a call with MecAgent,
four examples, each with: idx, what it shows (2–3 sentences), the numbers, and side-by-side
renders of the reference and the generated part. Images in
`docs/validation/gencad/examples/`. Link the new page from the "Files and how to reproduce"
section of `docs/validation/gencad_eval.md` with one line (the only edit to that file).

| # | idx | Shows | Numbers to state (all already recorded — re-read, don't recompute) |
|---|---|---|---|
| 1 | 400 | the easy win: single plate, IoU 1.0 | `scores_qwen25vl3b_qlora.json`, `per_row_analysis.json` |
| 2 | 350 | a failure: truncated program (`'(' was never closed` at `max_new_tokens` 1825) | sketch counts from `per_row_analysis.json`; show the **last 6 lines** of its program from `gen_qwen25vl3b_qlora.jsonl` |
| 3 | 5699 | good IoU, broken part: IoU 0.830 shell / 0.893 filled, generated part self-intersects (NeedsAttention 47.5), reference does not | `gencad_eval.md:120`, `checker_generated.jsonl`, `checker_reference.jsonl`, `iou_shell_vs_filled.json` |
| 4 | 4836 | the metric finding: same tube, shell IoU 0.010 vs filled 0.588 | `gencad_eval.md:62`, `iou_shell_vs_filled.json` |

All source files are under `docs/validation/gencad/` (verified present: generated STEPs
`steps/qwen25vl3b_qlora_{400,5699,4836}.step`; idx 350 has no STEP — it never ran).

## Decided — do not change these

1. **No dataset content in the repo.** The GenCAD-Code dataset (`CADCODER/GenCAD-Code`) declares
   no license on Hugging Face. Do not commit its input images or its reference programs. You may
   render the reference *geometry* (our own render) and quote numbers. Input images may be
   saved under `data/gencad/` (gitignored) for the owner's call, never under `docs/`.
2. **Reference STEPs** come from the existing exporter: `scripts/gencad_export_reference_steps.py`
   (writes `data/gencad/reference_steps/gt_<idx>.step`, gitignored). It needs cadquery +
   trimesh in a separate env (its docstring). Create env `gencad` under the throwaway root
   (`micromamba create -n gencad python=3.11 -y`, then `pip install cadquery trimesh scipy pandas pyarrow`)
   — that is the only install allowed. You may add an optional `--idx 400 5699 4836` argument
   to that script so it exports only those rows (default behaviour unchanged).
3. **Renders**: one script, new file `scripts/gencad_examples.py`, run in env `simready-fix`
   (pythonOCC). Reuse the tessellate + painter's draw of `simready/copilot/png_render.py`
   (`_read_step`, `_extract_triangles`, `_save_png`; private helpers are fine to import from a
   script) but colour every triangle one neutral grey, not by score, and use the same
   isometric view for reference and generated. Output names fixed:
   `examples/<idx>_reference.png`, `examples/<idx>_generated.png`; 800×600; each file ≤ 150 KB.
   No change to `png_render.py`.
4. For each rendered pair also record, by measurement (not by looking): bounding-box
   dimensions of both solids and the face counts — put them in the page next to the images.
5. Page voice: plain, short sentences, numbers first, no marketing words, no praise. State the
   limits the eval doc already states (two self-intersection cases are an example, not a rate).

## Environment

```bash
export MAMBA_ROOT_PREFIX=~/simready-fresh/mamba/root PIP_CACHE_DIR=~/simready-fresh/cache/pip XDG_CACHE_HOME=~/simready-fresh/cache PATH=~/simready-fresh/mamba/bin:$PATH
```

Never `micromamba shell init`, never edit dotfiles. At the end, if `~/.conda` or `~/.mamba`
exist and did not exist at your start, delete them and say so. Report `du -sh ~/simready-fresh`.

## Rules

- Setup was done by the owner (`git worktree add ../SimReady-walkthrough -b docs/gencad-examples main`
  from `~/projects/Mech/SimReady`). Check you are in `~/projects/Mech/SimReady-walkthrough` on
  `docs/gencad-examples`; work only there.
- Commits: (1) exporter `--idx` + `scripts/gencad_examples.py`, (2) images + page + the one
  link line, prefix `gencad-examples:`; (3) handoff.
- Never edit `BACKLOG.md`, `STATE.md`, memory files, `docs/superpowers/`, `weights/`,
  `requirements.txt`, `environment.yml`, or any existing file under `docs/validation/` other
  than the one link line. No `/save-session`. No push.
- `python -m pytest -q` in `simready-fix` before and after: no new failures (you add no tests;
  this is a docs task).
- End: `docs/handoff-2026-11-03-gencad-examples.md` — files changed, per idx the numbers you
  quoted with their source file, the measured bbox/face counts, image sizes, the exact commands
  you ran, commit SHAs, anything not done. Commit it.
