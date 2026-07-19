# Wave 1 Hygiene Batch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the six wave-1 bottlenecks from the 2026-07-19 triage: truth-sweep stale docstrings + system prompt, rename the `render`/`renderer` module collision, anchor cwd-dependent paths to repo root, ship a committed seed RAG index, add CI, and record waves 2/3 in BACKLOG.md.

**Architecture:** Six independent, individually-committable tasks against `main`. No new subsystems; every change is a correction or hardening of existing code. Tests run in the sr env (`C:\mm\sr\python.exe`); repo root is the cwd for all commands.

**Tech Stack:** Python 3.10 (sr conda env: pythonocc-core 7.9, torch 2.12 cpu, PyG 2.7, pydantic, openai, sentence-transformers, pytest), GitHub Actions (setup-python + mamba-org/setup-micromamba).

## Global Constraints

- NEVER `git push` (PreToolUse hook blocks it; user pushes). Never combine commit+push in one command.
- No AI attribution in commits.
- Test command shape: `& C:\mm\sr\python.exe -m pytest <target> -q` from repo root (pytest.ini sets `pythonpath = .`).
- Suite baseline before this plan: **198 passed** in sr env. Every task must end ≥ that count, 0 failures.
- Never Read `.env`; key names only.
- `data/fea_docs_index.json` (24.7 MB) stays gitignored — only the new seed index is committed.

---

### Task 1: Truth sweep — docstrings, system prompt, README counts

**Files:**
- Modify: `simready/ml/model.py:1-10` (docstring "Two heads" → three)
- Modify: `simready/copilot/tools.py:1-7` (docstring "Three tools" → four)
- Modify: `simready/copilot/agent.py:34-93` (`DEFAULT_SYSTEM_PROMPT`: "three tools" → four, add `build_part` description + workflow rule)
- Modify: `README.md` (test count 167 → 198 in two places: "Known limits" bullet and `tests/` line in Project layout)

**Interfaces:**
- Produces: `DEFAULT_SYSTEM_PROMPT` now documents `build_part`; gen-v2 (wave 2) relies on this instead of injecting an extra instruction block.

- [ ] **Step 1: Fix `model.py` module docstring**

Replace lines 1–10 header block so head list reads:

```python
"""PyG GraphSAGE multi-task per-face model for B-Rep analysis.

Three heads on a shared GraphSAGE encoder:

- `refinement_logits`  — per-face binary classification (rule-derived label — circular).
- `complexity_scores`  — per-face scalar regression (graph-feature proxy in [0, 1]).
- `defect_logits`      — graph-level 4-class defect classifier (injected ground-truth
  tags from generate_degraded_steps.py — non-circular).

Designed for CPU training on the parametric SimReady dataset (~500 graphs).
Keep the model small so 5-10 epochs are seconds on CPU.
"""
```

- [ ] **Step 2: Fix `tools.py` module docstring**

```python
"""Tool resolvers for the SimReady Copilot.

Four tools exposed to the LLM:
- analyze_geometry: runs the SimReady pipeline on a STEP file.
- suggest_fixes: ranks per-finding fix suggestions by severity.
- lookup_standard: RAG lookup over indexed FEA standards docs.
- build_part: generates a STEP file from a typed parametric spec (simready.gen).
"""
```

- [ ] **Step 3: Update `DEFAULT_SYSTEM_PROMPT` in `agent.py`**

Change `You have three tools:` → `You have four tools:` and append to the tool list (after the `lookup_standard` entry):

```text
- build_part(spec): generate a NEW STEP file from a typed parametric spec. Grammar:
  box(dx, dy, dz, at), cyl(r, h, at) [+Z axis], fuse(a, b), cut(a, b); dims in mm;
  a/b are 0-based indices of earlier steps; the last step is the returned part.
  Returns step_path on success. Use ONLY when the user asks you to CREATE a part.
```

Append to `Workflow rules:` (after the suggest_fixes rule):

```text
- When the user asks you to CREATE / generate a part, call build_part first; after it
  returns step_path, ALWAYS call analyze_geometry(step_path) before describing the
  result. Treat ML defect predictions on generated parts as advisory, not blocking.
```

- [ ] **Step 4: Fix README test counts**

`README.md` "Known limits": `167 tests pass` → `198 tests pass`. Project layout: `tests/           167 tests` → `tests/           198 tests`.

- [ ] **Step 5: Run the full suite**

Run: `& C:\mm\sr\python.exe -m pytest -q`
Expected: 198 passed. (If any test asserts on the old prompt text, fix the assertion to the new text — the prompt is the source of truth.)

- [ ] **Step 6: Commit**

```bash
git add simready/ml/model.py simready/copilot/tools.py simready/copilot/agent.py README.md
git commit -m "docs: truth sweep — 3-head/4-tool docstrings, build_part in system prompt, 198 test count"
```

---

### Task 2: Rename `render.py` → `png_render.py`

**Files:**
- Rename: `simready/copilot/render.py` → `simready/copilot/png_render.py`
- Rename: `tests/test_copilot_render.py` → `tests/test_copilot_png_render.py`
- Modify: `simready/copilot/tools.py:205` (import site)

**Interfaces:**
- Produces: `simready.copilot.png_render.render_face_score_png(...)` (signature unchanged). `renderer.py` (Rich CLI event renderer) keeps its name.

- [ ] **Step 1: git mv both files**

```bash
git mv simready/copilot/render.py simready/copilot/png_render.py
git mv tests/test_copilot_render.py tests/test_copilot_png_render.py
```

- [ ] **Step 2: Update import sites**

`simready/copilot/tools.py:205`: `from simready.copilot.render import render_face_score_png` → `from simready.copilot.png_render import render_face_score_png`.

`tests/test_copilot_png_render.py`: `from simready.copilot import render, tools` → `from simready.copilot import png_render, tools`; replace every `render.` module reference with `png_render.` (check for `monkeypatch.setattr(render, ...)` / `render.render_face_score_png` patterns).

- [ ] **Step 3: Grep for stragglers**

Run: `git grep -n "copilot.render\b\|copilot import render\b"` — expected: no hits outside `png_render` names. Also check `docs/` mentions; update if any reference `render.py` as a path.

- [ ] **Step 4: Run the suite**

Run: `& C:\mm\sr\python.exe -m pytest -q`
Expected: 198 passed.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: rename copilot/render.py to png_render.py (collides with renderer.py)"
```

---

### Task 3: Repo-root anchoring for `build_part` output and RAG index paths

**Files:**
- Modify: `simready/gen/build.py` (`_REPO_ROOT`, default output dir)
- Modify: `simready/copilot/rag.py:38` (`DEFAULT_INDEX_PATH` anchor)
- Test: `tests/test_gen_build.py` (new pure-python test)

**Interfaces:**
- Produces: `simready.gen.build.resolve_output_dir(output_dir, repo_root) -> Path` (new, pure-python, no OCC). `rag._REPO_ROOT: Path`. Task 4 consumes `rag._REPO_ROOT`.

- [ ] **Step 1: Write the failing test** (append to `tests/test_gen_build.py`)

```python
def test_resolve_output_dir_ignores_cwd(tmp_path, monkeypatch):
    """Default output dir is anchored to the repo root, not the process cwd."""
    from simready.gen.build import resolve_output_dir

    monkeypatch.chdir(tmp_path)
    resolved = resolve_output_dir(None, None)
    assert resolved.is_absolute()
    assert str(tmp_path) not in str(resolved)
    assert resolved.parts[-2:] == ("data", "gen_parts")


def test_resolve_output_dir_explicit_wins(tmp_path):
    from simready.gen.build import resolve_output_dir

    explicit = tmp_path / "out"
    assert resolve_output_dir(explicit, None) == explicit
```

- [ ] **Step 2: Run to verify failure**

Run: `& C:\mm\sr\python.exe -m pytest tests/test_gen_build.py -q -k resolve_output_dir`
Expected: FAIL — `ImportError: cannot import name 'resolve_output_dir'`.

- [ ] **Step 3: Implement in `build.py`**

Below `DEFAULT_OUTPUT_DIR` add:

```python
# Anchor generated parts to the repo root regardless of process cwd —
# Streamlit / installed-package launches don't run from the repo root.
_REPO_ROOT = Path(__file__).resolve().parents[2]


def resolve_output_dir(
    output_dir: str | os.PathLike[str] | None,
    repo_root: str | os.PathLike[str] | None,
) -> Path:
    """Pick the directory generated STEPs land in. Explicit args win; the
    default is ``<repo>/data/gen_parts`` independent of ``Path.cwd()``."""
    if output_dir is not None:
        return Path(output_dir)
    root = Path(repo_root) if repo_root is not None else _REPO_ROOT
    return root / DEFAULT_OUTPUT_DIR
```

In `build_part`, replace the two lines

```python
    root = Path(repo_root) if repo_root is not None else Path.cwd()
    out_dir = Path(output_dir) if output_dir is not None else root / DEFAULT_OUTPUT_DIR
```

with

```python
    out_dir = resolve_output_dir(output_dir, repo_root)
```

In `rag.py`, replace `DEFAULT_INDEX_PATH = Path("data/fea_docs_index.json")` with:

```python
_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INDEX_PATH = _REPO_ROOT / "data" / "fea_docs_index.json"
```

- [ ] **Step 4: Run tests**

Run: `& C:\mm\sr\python.exe -m pytest tests/test_gen_build.py tests/test_copilot_rag.py -q` then full `-q` suite.
Expected: all pass, 200 total (198 + 2 new).

- [ ] **Step 5: Commit**

```bash
git add simready/gen/build.py simready/copilot/rag.py tests/test_gen_build.py
git commit -m "fix: anchor gen output dir and RAG index path to repo root, not cwd"
```

---

### Task 4: Committed seed RAG index + fallback

**Files:**
- Create: `data/fea_docs_index_seed.json` (generated, committed — must be < 2 MB)
- Modify: `simready/copilot/rag.py` (`SEED_INDEX_PATH` + fallback in `get_default_index`)
- Test: `tests/test_copilot_rag.py` (fallback test)

**Interfaces:**
- Consumes: `rag._REPO_ROOT` from Task 3.
- Produces: `rag.SEED_INDEX_PATH: Path`; `get_default_index()` falls back to the seed when the full index is absent and no explicit path/env override is given.

- [ ] **Step 1: Write the failing fallback test** (append to `tests/test_copilot_rag.py`, reusing the file's existing fake-embedder/index-building fixtures — read the file first and match its construction pattern for a tiny on-disk index)

```python
def test_get_default_index_falls_back_to_seed(tmp_path, monkeypatch):
    """When the full index is missing, the committed seed index loads instead."""
    from simready.copilot import rag

    missing = tmp_path / "nope.json"
    seed = tmp_path / "seed.json"
    # Build a 2-entry index with the module's own save path so the schema matches.
    entries = [
        {"source": "seed.pdf", "page": 1, "chunk_id": 0, "text": "aspect ratio limits"},
        {"source": "seed.pdf", "page": 2, "chunk_id": 1, "text": "element quality"},
    ]
    idx = rag.build_index(entries, _FakeEmbedder())  # match existing test fixture name
    idx.save(seed)

    monkeypatch.delenv("SIMREADY_RAG_INDEX", raising=False)
    monkeypatch.setattr(rag, "DEFAULT_INDEX_PATH", missing)
    monkeypatch.setattr(rag, "SEED_INDEX_PATH", seed)
    rag._INDEX_CACHE.clear()
    loaded = rag.get_default_index()
    assert loaded.meta["n_chunks"] == 2
```

(Adapt `_FakeEmbedder` to whatever the existing fake embedder in that test file is called; do not invent a second fake.)

- [ ] **Step 2: Run to verify failure**

Run: `& C:\mm\sr\python.exe -m pytest tests/test_copilot_rag.py -q -k seed`
Expected: FAIL — `AttributeError: ... has no attribute 'SEED_INDEX_PATH'`.

- [ ] **Step 3: Implement fallback in `rag.py`**

Below `DEFAULT_INDEX_PATH`:

```python
# Tiny committed index (one small public PDF) so a fresh clone gets a live
# lookup_standard tool instead of "no_index". The full 24 MB index stays local.
SEED_INDEX_PATH = _REPO_ROOT / "data" / "fea_docs_index_seed.json"
```

Rework `get_default_index`:

```python
def get_default_index(path: str | Path | None = None) -> RagIndex:
    """Load (and cache) the default RAG index.

    Resolution order: explicit ``path`` arg → ``SIMREADY_RAG_INDEX`` env →
    ``DEFAULT_INDEX_PATH`` → committed ``SEED_INDEX_PATH``. Raises
    FileNotFoundError only when none exist.
    """
    explicit = path or os.environ.get("SIMREADY_RAG_INDEX")
    if explicit:
        resolved = Path(explicit)
    elif DEFAULT_INDEX_PATH.exists():
        resolved = DEFAULT_INDEX_PATH
    else:
        resolved = SEED_INDEX_PATH
    key = str(resolved.resolve()) if resolved.exists() else str(resolved)
    if key not in _INDEX_CACHE:
        _INDEX_CACHE[key] = RagIndex.load(resolved)
    return _INDEX_CACHE[key]
```

- [ ] **Step 4: Run tests**

Run: `& C:\mm\sr\python.exe -m pytest tests/test_copilot_rag.py -q` then full suite.
Expected: pass (201 total).

- [ ] **Step 5: Generate the seed index** (sr env; real sentence-transformers embed of the one 50 KB PDF)

```powershell
New-Item -ItemType Directory -Force tmp_seed_docs
Copy-Item data/fea_docs/901851.pdf tmp_seed_docs/
& C:\mm\sr\python.exe scripts/index_fea_docs.py --input tmp_seed_docs --output data/fea_docs_index_seed.json
Remove-Item -Recurse -Force tmp_seed_docs -Confirm:$false
```

Then check size: `(Get-Item data/fea_docs_index_seed.json).Length / 1MB` — expected < 2 MB. If ≥ 2 MB, abort commit and shrink (crop PDF pages) before committing.

Smoke: `& C:\mm\sr\python.exe -c "import os; os.environ.pop('SIMREADY_RAG_INDEX', None); import shutil; shutil.move('data/fea_docs_index.json','data/fea_docs_index.json.bak'); from simready.copilot.tools import lookup_standard; r = lookup_standard('mesh element aspect ratio'); print(r['status'], len(r['results'])); shutil.move('data/fea_docs_index.json.bak','data/fea_docs_index.json')"`
Expected: `ok <n>=1..3`.

- [ ] **Step 6: Commit**

```bash
git add simready/copilot/rag.py tests/test_copilot_rag.py data/fea_docs_index_seed.json
git commit -m "feat(rag): committed seed index so lookup_standard works on fresh clones"
```

---

### Task 5: CI — fast spec job + full micromamba job

**Files:**
- Create: `.github/workflows/ci.yml`
- Modify: `pytest.ini` (register `live_llm` marker)

**Interfaces:**
- Produces: `live_llm` pytest marker (gen v2's `tests/test_gen_e2e.py` will use it; CI excludes it).

- [ ] **Step 1: Register the marker in `pytest.ini`**

```ini
[pytest]
pythonpath = .
markers =
    live_llm: hits a real LLM endpoint; excluded from CI and default runs
```

- [ ] **Step 2: Write `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  spec-fast:
    # Pure-python subset: proves the DSL schema layer with zero native deps.
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install pydantic pytest
      - run: pytest tests/test_gen_spec.py -q

  full-suite:
    # Full sr-equivalent env via micromamba. continue-on-error until proven
    # stable on linux-64 (environment.yml was authored on Windows).
    runs-on: ubuntu-latest
    continue-on-error: true
    steps:
      - uses: actions/checkout@v4
      - uses: mamba-org/setup-micromamba@v2
        with:
          environment-file: environment.yml
          cache-environment: true
      - name: Install pip deps
        shell: bash -el {0}
        run: pip install -r requirements.txt
      - name: Run suite (no live-LLM tests)
        shell: bash -el {0}
        run: pytest -m "not live_llm" -q
```

- [ ] **Step 3: Verify the fast job's command locally**

Run: `& C:\mm\sr\python.exe -m pytest tests/test_gen_spec.py -q` — expected: all pass (17 tests).
Run full suite once more with the marker line in place: `& C:\mm\sr\python.exe -m pytest -q` — expected: 201 passed (marker registration must not deselect anything).

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml pytest.ini
git commit -m "ci: GitHub Actions — fast spec job + full micromamba suite (continue-on-error)"
```

- [ ] **Step 5: Hand push to user, then check runs**

User pushes (hook prints the line). After push: `gh run list --limit 2` and `gh run watch` the latest. Expected: `spec-fast` green. `full-suite` may fail on env resolution — record outcome in BACKLOG as `ci-full-suite-promote` (S3: drop `continue-on-error` once green) with the actual error if any.

---

### Task 6: BACKLOG truth pass + wave 2/3 recording + STATE.md refresh

**Files:**
- Modify: `BACKLOG.md`
- Modify: `STATE.md` (user authorized hand-edit 2026-07-19)

- [ ] **Step 1: Correct the false application line**

In `BACKLOG.md` Archived: `**2026-05-18 · apply-timeline-tight** — Application sent to MecAgent at v0.4.0-apply (34a93e7). Item obsolete.` → `**2026-05-18 · apply-timeline-tight** — CORRECTED 2026-07-19: application was NEVER sent; v0.4.0-apply tagged the prep snapshot only. Apply deferred until project substantial (user decision 2026-07-19).`

- [ ] **Step 2: Add the wave plan section**

Insert after the severity rubric block, replacing nothing:

```markdown
## Triage 2026-07-19 — wave plan (Fable session)

Application to MecAgent NEVER sent (v0.4.0-apply = prep tag). New goal: make the
project substantial, then apply. Full assessment in session transcript; dashboard:

**Wave 1 — hygiene (DONE this session, see Done):** truth sweep (docstrings +
build_part system prompt + README counts), render→png_render rename, repo-root
path anchoring, committed seed RAG index, CI (spec job + micromamba full job),
this truth pass.

**Wave 2 — substance (next sessions, in order):**
1. `geometry-gen-v2` (S1 stamp) — live-LLM E_grammar runner; prompt drafted in
   docs/session-prompts.md Stream A. NIM Llama-70B primary + NEW: Kimi K2.7
   second backend (user adds KIMI_API_KEY to .env; base_url swap).
2. `analyze-file-occ-hang-per-check` (S2) — demo killer; per-check precheck +
   subprocess isolation at UI entry points.
3. `defect-head-real-cad-augmentation` (S2) — hardest, highest ML value.

**Wave 3 — user-gated / decisions:**
- `finish-or-relabel-finetune` — DECIDED 2026-07-19: RUN one Colab QLoRA
  collaboratively (user + assistant), then stop investing.
- `real-eval-set-grow` (S3) — user downloads 20–30 STEPs.
- `gmsh-calibration` (S2) — do-or-drop decision still open.
- NIM key: rotated (user confirmed 2026-07-19).
```

- [ ] **Step 3: Record wave-1 closes in Done this session**

Add `## Done this session (2026-07-19)` above the 2026-05-31 block, one line per Task 1–5 commit with SHA (fill from `git log --oneline -6`). Compress the `Done this session (2026-05-31)` block into a one-liner under Archived (per sweep convention). Update `Last swept: 2026-07-19` line.

- [ ] **Step 4: Refresh STATE.md**

Update `Last touched: 2026-07-19`; `## Done` gains one line (`Wave-1 hygiene batch: truth sweep, png_render rename, path anchoring, seed RAG index, CI — see BACKLOG Done 2026-07-19`); `## Doing` → `Wave 2 next: gen v2 live-LLM runner (docs/session-prompts.md Stream A) + Kimi second backend`; `## Pipeline` reordered to the wave plan; `## Resume here` → paste Stream A prompt; add Landmine: `Memory + old BACKLOG claimed "applied to MecAgent 2026-05-18" — FALSE, never applied (corrected 2026-07-19)`.

- [ ] **Step 5: Commit**

```bash
git add BACKLOG.md STATE.md
git commit -m "docs: 2026-07-19 triage — correct never-applied record, wave 1 closes, wave 2/3 plan"
```

---

## Self-Review

- Spec coverage: all six wave-1 items have tasks (1=docstrings/prompt, 2=rename, 3=cwd, 4=seed index, 5=CI, 6=BACKLOG+STATE). ✓
- Placeholder scan: Task 4 Step 1 asks the implementer to match the existing fake-embedder fixture name — deliberate (fixture exists in `tests/test_copilot_rag.py`; do not duplicate it). No TBDs. ✓
- Type consistency: `resolve_output_dir(output_dir, repo_root) -> Path` used identically in Task 3 test and impl; `rag._REPO_ROOT` defined in Task 3, consumed in Task 4. ✓
- Suite count arithmetic: 198 → +2 (Task 3) → +1 (Task 4) = 201 expected at Task 5 Step 3. ✓
