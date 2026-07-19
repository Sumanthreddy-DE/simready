# Wave-2 Items 2+3: OCC Hang Guard + Defect-Head Real-CAD Augmentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** (A) `analyze_file` can no longer freeze a UI/tool caller on real CAD — culprit check identified, guarded, and all entry points subprocess-isolated; (B) the defect head's 100 % FP rate on real McMaster parts is attacked with feature-rich (filleted/chamfered) training data and honestly re-measured.

**Architecture:** A: diagnose per-stage (the hang may not even be in a *check* — heal/parse/graph are candidates too), guard the culprit with the proven precheck+watchdog pattern from `check_self_intersection`, then promote `eval_real_cad.py`'s spawn-subprocess+terminate pattern into a library-level `analyze_file_safe()` used by copilot tool, Streamlit UI, and CLI. Per-check subprocesses rejected: 13 × ~7 s Windows spawn overhead. B: enrich BOTH classes (clean and degraded) with manufactured features so feature-richness stays orthogonal to the label, retrain source-grouped, re-run the real-CAD eval.

**Tech Stack:** sr env (`C:\mm\sr\python.exe`, pythonocc-core 7.9, torch-cpu, PyG), pytest, multiprocessing spawn.

## Global Constraints

- Every command: `$env:PYTHONPATH = "C:\Users\suman\Desktop\Docs\Job\Projects\Mech\SimReady"` + sr python (PowerShell).
- Python thread timeouts DO NOT stop OCC C++ (`lessons_pythonocc-gotchas.md`). Only `multiprocessing` spawn + `Process.terminate()` kills. 12 h were lost to this once.
- Defect head is ADVISORY, never a gate (`real_eval.md` §1).
- `tests/data/real_eval/` is gitignored and local-only — every test touching it needs skip-if-absent (CI!).
- Suite baseline: 202 default-selected tests green, 5 live_llm deselected via pytest.ini addopts. Must not regress.
- `scripts/smoke_real_llm.py` stubs `tools.analyze_file` by module-global swap — Task A3 must keep that seam working.
- Commits: conventional format, no AI attribution. Push is hook-blocked → hand to user.
- Known-hang parts (all in `tests/data/real_eval/`): `43505K359_*.STEP` (58 f), `44685K321_*.STEP` (58 f), `1483N211_*.STEP` (267 f), `4519N12_*.STEP` (578 f). Known-good control: `33125T73_*.STEP` (34 f, 0.16 s).

---

## Phase A — `analyze-file-occ-hang-per-check` (S2)

### Task A1: Diagnosis — which stage hangs?

**Files:**
- Create: `scripts/diagnose_occ_hang.py`
- Create: `docs/validation/occ_hang_diagnosis.md` (results)

**Interfaces:**
- Produces: culprit stage name(s) + per-stage timings consumed by Task A2 to place the guard.

- [x] **Step 1: Write the probe script.** One spawn subprocess **per stage per part** (a hung stage kills only that probe). Stages: `load` (validate_file_load), `validate` (validate_brep), `heal` (heal_shape), `parse` (parse_geometry), each of the 13 checks by name, `graph` (extract_brep_graph), `ml` (run_brepnet_inference). Later stages rebuild their inputs inside the child (re-load + re-heal) — wall-time per probe includes that rebuild; report `stage_seconds = total - rebuild_baseline` where rebuild_baseline = the load+heal+parse probe times for that part.

```python
"""Per-stage OCC hang attribution for analyze_file on real CAD.

Each (part, stage) probe runs in its own spawn subprocess with a hard
timeout + terminate, so a hung stage cannot take the batch down.
Writes a JSON + markdown table naming the slowest / hanging stage.

Usage (sr env):
    python scripts/diagnose_occ_hang.py --input tests/data/real_eval \
        --stage-timeout 90 --output docs/validation/occ_hang_diagnosis
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import time
from pathlib import Path

STAGES = [
    "load", "validate", "heal", "parse",
    # checks.py::run_essential_checks_detailed order:
    "check_degenerate_geometry", "check_non_manifold_edges",
    "check_open_boundaries", "check_short_edges", "check_thin_walls",
    "check_small_features", "check_small_fillets",
    "check_duplicate_body_heuristic", "check_thin_solid",
    "check_duplicate_face_heuristic", "check_orientation_nuance",
    "check_sharp_edges", "check_self_intersection",
    "graph", "ml",
]


def _probe(step_path: str, stage: str, q) -> None:
    """Child: rebuild prerequisites, run one stage, report seconds."""
    from simready.validator import validate_brep, validate_file_load
    from simready.healer import heal_shape
    from simready.parser import parse_geometry

    t0 = time.perf_counter()
    load = validate_file_load(step_path)
    if not load.is_valid:
        q.put({"stage": stage, "error": "load_invalid"}); return
    shape = load.shape
    if stage == "load":
        q.put({"stage": stage, "seconds": time.perf_counter() - t0}); return
    if stage == "validate":
        t = time.perf_counter(); validate_brep(shape)
        q.put({"stage": stage, "seconds": time.perf_counter() - t}); return
    healed = heal_shape(shape)
    shape = healed.healed_shape
    if stage == "heal":
        q.put({"stage": stage, "seconds": time.perf_counter() - t0}); return
    summary = parse_geometry(shape)
    if stage == "parse":
        q.put({"stage": stage, "seconds": time.perf_counter() - t0}); return
    if stage.startswith("check_"):
        import simready.checks as checks
        fn = getattr(checks, stage)
        args = (shape,) if stage in ("check_non_manifold_edges",
                                     "check_sharp_edges",
                                     "check_self_intersection") else (shape, summary)
        t = time.perf_counter(); fn(*args)
        q.put({"stage": stage, "seconds": time.perf_counter() - t}); return
    if stage == "graph":
        from simready.ml.graph_extractor import extract_brep_graph
        t = time.perf_counter(); extract_brep_graph(shape)
        q.put({"stage": stage, "seconds": time.perf_counter() - t}); return
    if stage == "ml":
        from simready.ml.graph_extractor import extract_brep_graph
        from simready.ml.brepnet import run_brepnet_inference
        graph = extract_brep_graph(shape)
        t = time.perf_counter(); run_brepnet_inference(graph)
        q.put({"stage": stage, "seconds": time.perf_counter() - t}); return
    q.put({"stage": stage, "error": "unknown_stage"})


def probe_part(step_path: Path, stage_timeout: float) -> list[dict]:
    ctx = mp.get_context("spawn")
    rows = []
    for stage in STAGES:
        q = ctx.Queue()
        p = ctx.Process(target=_probe, args=(str(step_path), stage, q))
        started = time.perf_counter()
        p.start(); p.join(timeout=stage_timeout)
        if p.is_alive():
            p.terminate(); p.join(5)
            rows.append({"stage": stage, "timeout": True,
                         "wall": time.perf_counter() - started})
        else:
            rows.append(q.get() if not q.empty()
                        else {"stage": stage, "error": "no_result"})
        print(f"  {stage}: {rows[-1]}", flush=True)
    return rows
```

(Complete the `main()`: argparse per usage string, iterate `--input` dir sorted by face count via `validate_file_load` + `count_shapes` — or just hardcode the 4 hang stems + `33125T73` control via `--parts` filter; write `<output>.json` + `<output>.md` table part × stage.)

- [x] **Step 2: Smoke on the control part** (fast, proves plumbing):
Run: `& C:\mm\sr\python.exe scripts/diagnose_occ_hang.py --input tests/data/real_eval --parts 33125T73 --stage-timeout 90`
Expected: all stages < ~5 s, no timeouts.

- [x] **Step 3: Run on the 4 hang parts.** `--parts 43505K359 44685K321 1483N211 4519N12 --stage-timeout 90`. Expected: ≥1 stage per part hits `timeout: True` — that's the culprit. Budget: worst case ~4 parts × couple timeouts × 90 s + spawn overhead ≈ 15–25 min. Run in background.

- [x] **Step 4: Write `docs/validation/occ_hang_diagnosis.md`** — part × stage table + one-paragraph culprit statement. Honest note if culprits differ per part.

- [x] **Step 5: Commit** — `feat(diag): per-stage OCC hang attribution script + results`.

### Task A2: Guard the culprit check(s)

**Files:**
- Modify: `simready/checks.py` (culprit fn + extract shared watchdog helper)
- Test: `tests/test_checks_guards.py` (create)

**Interfaces:**
- Consumes: culprit stage name from A1.
- Produces: guarded check returning an Info "skipped" finding instead of hanging; `_run_with_watchdog(fn, timeout_s) -> tuple[bool, Any]` helper reusable by other checks.

Exact edit depends on A1's culprit — the *pattern* is locked (mirror `check_self_intersection`'s two guards, `checks.py:714-786`):

- [x] **Step 1: Failing test first.** Guard contract, culprit-agnostic (replace `check_sharp_edges` with the real culprit):

```python
import pytest
from simready import checks

occ = pytest.importorskip("OCC.Core.BRepPrimAPI")


def test_guarded_check_skips_over_face_limit(monkeypatch):
    """Above the face limit the check must return an Info skip, not run."""
    from simready.gen.spec import PartSpec
    from simready.gen.build import build_shape

    shape = build_shape(PartSpec.model_validate(
        {"steps": [{"op": "box", "dx": 10, "dy": 10, "dz": 10}]}))
    monkeypatch.setattr(checks, "<CULPRIT>_FACE_LIMIT", 3)
    result = checks.check_<culprit>(shape)          # signature per culprit
    assert any("skip" in f["detail"].lower() for f in result.findings)
    assert all(f["severity"] == "Info" for f in result.findings)


def test_watchdog_returns_timeout_flag():
    import time
    ok, _ = checks._run_with_watchdog(lambda: time.sleep(3), timeout_s=0.2)
    assert ok is False
```

- [x] **Step 2: Run** `pytest tests/test_checks_guards.py -v` → FAIL (helper/limit missing).
- [x] **Step 3: Implement.** Extract the daemon-thread+join pattern out of `check_self_intersection` into `_run_with_watchdog`; add `<CULPRIT>_FACE_LIMIT` module constant + precheck + watchdog to the culprit fn, emitting the same Info-finding shape `check_self_intersection` uses. Keep the watchdog as *soft* guard (thread can't kill C++ — the hard kill is Task A3's subprocess; say so in the docstring).
- [x] **Step 4: Run** guard tests + `pytest -q` (full default suite) → all green.
- [x] **Step 5: Commit** — `fix(checks): face-limit + watchdog guard on <culprit> (real-CAD hang)`.

### Task A3: `analyze_file_safe` — subprocess isolation at entry points

**Files:**
- Modify: `simready/pipeline.py` (add `_safe_worker`, `analyze_file_safe`)
- Modify: `simready/copilot/tools.py:191` (analyze_geometry → safe)
- Modify: `ui/app.py:74`, `simready/cli.py:29` (→ safe)
- Test: `tests/test_pipeline_safe.py` (create)

**Interfaces:**
- Produces: `analyze_file_safe(filepath, export_healed_path=None, timeout=120) -> dict` — same report shape as `analyze_file`; on timeout returns the existing `AnalysisTimeout` report (`pipeline.py:221-240` shape) so downstream summarizers need no change.

- [x] **Step 1: Failing tests.**

```python
import pytest
from simready.pipeline import analyze_file_safe

occ = pytest.importorskip("OCC.Core.BRepPrimAPI")


@pytest.fixture()
def box_step(tmp_path):
    from simready.gen.spec import PartSpec
    from simready.gen.build import build_shape, write_step
    p = tmp_path / "box.step"
    write_step(build_shape(PartSpec.model_validate(
        {"steps": [{"op": "box", "dx": 20, "dy": 20, "dz": 20}]})), p)
    return p


def test_safe_happy_path_matches_report_shape(box_step):
    report = analyze_file_safe(str(box_step), timeout=120)
    assert report["status"] != "InvalidInput"
    assert report["geometry"]["face_count"] == 6
    assert "score" in report and "findings" in report


def test_safe_timeout_returns_timeout_report(box_step):
    # Impossible-to-meet budget forces the kill path deterministically:
    # spawn+import alone exceeds it.
    report = analyze_file_safe(str(box_step), timeout=0.01)
    assert report["status"] == "InvalidInput"
    errs = report["validation"]["errors"]
    assert errs and errs[0]["check"] == "AnalysisTimeout"
```

- [x] **Step 2: Run** → FAIL (`analyze_file_safe` not defined).
- [x] **Step 3: Implement** in `pipeline.py`:

```python
def _safe_worker(filepath: str, export_healed_path: str | None, q) -> None:
    started = time.perf_counter()
    try:
        q.put(_analyze_file_inner(filepath, export_healed_path, started))
    except Exception as exc:
        q.put({"__error__": str(exc)})


def analyze_file_safe(
    filepath: str,
    export_healed_path: str | None = None,
    timeout: float = ANALYSIS_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """analyze_file with a *hard* kill switch.

    Runs the full analysis in a spawn subprocess and terminates it on
    timeout — the only reliable way to stop a hung OCC C++ call on
    Windows (thread timeouts, incl. analyze_file's own, cannot).
    Same report contract as analyze_file; timeout yields the
    AnalysisTimeout report.
    """
    import multiprocessing as mp

    started = time.perf_counter()
    ctx = mp.get_context("spawn")
    q = ctx.Queue()
    proc = ctx.Process(target=_safe_worker, args=(filepath, export_healed_path, q))
    proc.start()
    proc.join(timeout=timeout)
    if proc.is_alive():
        proc.terminate()
        proc.join(5)
        return _timeout_report(filepath, timeout, time.perf_counter() - started)
    if not q.empty():
        result = q.get()
        if "__error__" not in result:
            return result
        return _error_report(filepath, result["__error__"], time.perf_counter() - started)
    return _timeout_report(filepath, timeout, time.perf_counter() - started)
```

Refactor the existing timeout-report literal (`pipeline.py:221-240`) into `_timeout_report` / `_error_report` helpers used by both `analyze_file` and `analyze_file_safe` (DRY; identical dict shape). Queue note: report dicts are plain JSON-able (verified by session persist) — safe through spawn pickling.
Wire call sites: `tools.py` — import `analyze_file_safe` **as a module attr lookup** (`from simready import pipeline` + `pipeline.analyze_file_safe(...)` is NOT needed; keep `from simready.pipeline import analyze_file_safe` but ALSO keep the old `analyze_file` import so `smoke_real_llm.py`'s `tools.analyze_file = stub` seam keeps working — the resolver checks `if analyze_file is not _real_analyze_file: use the stub` is over-engineering; simpler: change the resolver to call the module-level name `analyze_file_safe` and update `smoke_real_llm.py` to stub `tools.analyze_file_safe` instead — one line there). `ui/app.py:74` + `cli.py:29`: swap name, pass existing `timeout` through.
- [x] **Step 4: Run** new tests + full `pytest -q` + `scripts/smoke_real_llm.py` still imports (collection-level check). Expected: green; timeout test ~ spawn overhead seconds.
- [x] **Step 5: Commit** — `fix(pipeline): analyze_file_safe hard-kill wrapper; UI/tool/CLI entry points isolated`.

### Task A4: Prove it on the hang set + docs

**Files:**
- Test: `tests/test_real_eval_regression.py` (create, skip-if-absent)
- Modify: `docs/validation/real_eval.md` (§3 update), `BACKLOG.md`, `STATE.md`

- [x] **Step 1: Regression test** (local-only, CI skips):

```python
import pytest
from pathlib import Path

occ = pytest.importorskip("OCC.Core.BRepPrimAPI")

REAL_EVAL = Path(__file__).resolve().parents[1] / "tests" / "data" / "real_eval"
HANG_STEMS = ["43505K359", "44685K321"]  # 58-face flanges; keep runtime sane

pytestmark = pytest.mark.skipif(
    not REAL_EVAL.exists(), reason="gitignored real_eval data absent"
)


@pytest.mark.parametrize("stem", HANG_STEMS)
def test_former_hang_part_completes_or_times_out_cleanly(stem):
    from simready.pipeline import analyze_file_safe
    matches = list(REAL_EVAL.glob(f"{stem}*.STEP"))
    if not matches:
        pytest.skip(f"{stem} not present")
    report = analyze_file_safe(str(matches[0]), timeout=90)
    # Contract: returns within budget either a full report or a clean
    # AnalysisTimeout — never hangs the caller.
    assert report["status"] != ""
```

- [x] **Step 2: Run it** + re-run `scripts/diagnose_occ_hang.py`-informed spot check: do the 4 killed parts now *complete* under guarded checks (guard skips culprit) or still time out but cleanly? Record which.
- [x] **Step 3: Update `docs/validation/real_eval.md` §3** — culprit named, guard shipped, "script-level workaround" paragraph replaced with library-level fix; per-part before/after table.
- [x] **Step 4: BACKLOG** — close `analyze-file-occ-hang-per-check` → Done w/ SHA; STATE.md Doing → item 3.
- [x] **Step 5: Commit** — `docs(validation): hang culprit + guard results; close analyze-file-occ-hang-per-check`.

---

## Phase B — `defect-head-real-cad-augmentation` (S2)

### Task B1: Manufactured-feature randomization in the generator

**Files:**
- Modify: `scripts/generate_parametric_steps.py`
- Test: `tests/test_generate_features.py` (create)

**Interfaces:**
- Produces: `apply_random_features(shape, rng, fillet_prob, chamfer_prob) -> shape` + CLI flags `--fillet-prob P --chamfer-prob P` (default 0.0 = old behavior byte-identical).

- [x] **Step 1: Failing test.**

```python
import pytest
import random

occ = pytest.importorskip("OCC.Core.BRepPrimAPI")

from scripts.generate_parametric_steps import gen_normal_box, apply_random_features
from simready.occ_utils import count_topology


def test_fillet_increases_face_count():
    rng = random.Random(42)
    base = gen_normal_box(rng)
    featured = apply_random_features(base, rng, fillet_prob=1.0, chamfer_prob=0.0)
    assert count_topology(featured)["face_count"] > 6


def test_zero_prob_is_identity():
    rng = random.Random(42)
    base = gen_normal_box(rng)
    out = apply_random_features(base, rng, fillet_prob=0.0, chamfer_prob=0.0)
    assert count_topology(out)["face_count"] == 6


def test_failed_fillet_falls_back_to_base():
    # Radius larger than the part must not crash generation.
    rng = random.Random(42)
    base = gen_normal_box(rng)
    out = apply_random_features(base, rng, fillet_prob=1.0,
                                chamfer_prob=0.0, radius_range=(500.0, 600.0))
    assert count_topology(out)["face_count"] >= 6  # base or partial
```

- [x] **Step 2: Run** → FAIL (`apply_random_features` missing).
- [x] **Step 3: Implement.**

```python
def apply_random_features(
    shape,
    rng: random.Random,
    fillet_prob: float = 0.0,
    chamfer_prob: float = 0.0,
    radius_range: tuple[float, float] = (1.0, 4.0),
):
    """Randomly fillet/chamfer edges so 'clean' training geometry carries
    manufactured features (real-CAD FP fix — see real_eval.md §1).

    Per-edge Bernoulli; every OCC failure (tangency, radius > local size)
    falls back to the previous good shape — generation never aborts.
    """
    from OCC.Core.BRepFilletAPI import BRepFilletAPI_MakeChamfer, BRepFilletAPI_MakeFillet
    from OCC.Core.TopAbs import TopAbs_EDGE
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopoDS import topods

    for prob, maker_cls in ((fillet_prob, BRepFilletAPI_MakeFillet),
                            (chamfer_prob, BRepFilletAPI_MakeChamfer)):
        if prob <= 0.0:
            continue
        maker = maker_cls(shape)
        n_added = 0
        exp = TopExp_Explorer(shape, TopAbs_EDGE)
        while exp.More():
            if rng.random() < prob:
                radius = rng.uniform(*radius_range)
                try:
                    maker.Add(radius, topods.Edge(exp.Current()))
                    n_added += 1
                except Exception:
                    pass
            exp.Next()
        if n_added:
            try:
                maker.Build()
                if maker.IsDone():
                    shape = maker.Shape()
            except Exception:
                pass  # keep previous good shape
    return shape
```

Wire into `main()`: two `add_argument` flags, apply after each category generator, per-edge prob default ~0.3 when flag set. Keep filename stems unchanged (category prefix drives grouping; feature-richness must NOT be inferable from the label side).
- [x] **Step 4: Run** tests → PASS. Also eyeball: one featured STEP through `analyze_file` (valid, no Critical).
- [x] **Step 5: Commit** — `feat(datagen): random fillet/chamfer features for real-CAD domain randomization`.

### Task B2: Build combined-v2 dataset

**Files:** none created in repo (all output dirs gitignored). Record counts in B4's doc.

- [x] **Step 1: Generate feature-rich cleans** (~300):
`& C:\mm\sr\python.exe scripts/generate_parametric_steps.py --output data/parametric_featured --per-category 60 --fillet-prob 0.3 --chamfer-prob 0.15`
- [x] **Step 2: Degrade them** (~900 attempts):
`& C:\mm\sr\python.exe scripts/generate_degraded_steps.py --input data/parametric_featured --output data/parametric_featured_degraded`
Check `manifest.json` failure count — fillets may break `open_shell` face-removal occasionally; acceptable if ≥70 % succeed.
- [x] **Step 3: Label everything into one dir** (old 500 clean + 600 degraded + new featured clean + featured degraded):
`& C:\mm\sr\python.exe scripts/auto_label.py data/parametric data/labels_combined_v2 --extra-inputs data/parametric_degraded data/parametric_featured data/parametric_featured_degraded`
Expected: ~2100–2300 labeled graphs (some degrade failures). Long run (analyze per part) — background, ~30–60 min.
- [x] **Step 4: Sanity:** count `.labels.json` + spot-check one featured file has `graph_label` clean and one degraded-featured has its defect tag.

### Task B3: Retrain, source-grouped

- [x] **Step 1:** `& C:\mm\sr\python.exe scripts/train.py data/labels_combined_v2 weights --epochs 10 --batch-size 16` (grouped split is the default; `--random-split` is the leaky opt-in — do NOT pass it).
- [x] **Step 2:** Record val defect acc + per-class vs baseline 0.756 (clean 0.87 / sliver 1.0 / open_shell 0.571 / self_int 0.371). A few points' drop is acceptable if real-CAD FP falls; collapse (< 0.6) = stop, investigate class balance.
- [x] **Step 3:** `& C:\mm\sr\python.exe scripts/auto_label.py tests/data data/labels_fixtures_v2` + `& C:\mm\sr\python.exe scripts/evaluate.py data/labels_fixtures_v2 weights/brepnet.pt --output weights/eval_fixtures.json` (refresh tracked fixtures metrics).
- [x] **Step 4: Run full default suite** — ML-dependent tests must stay green with the new checkpoint.
- [x] **Step 5: Commit** — `feat(ml): retrain defect head on feature-randomized combined-v2 set` (tracked: `weights/brepnet.pt`, `brepnet_meta.json`, `metrics.json`, `eval_fixtures.json`).

### Task B4: Re-measure on real CAD + honest docs

- [x] **Step 1:** `& C:\mm\sr\python.exe scripts/eval_real_cad.py --analyze-timeout 90` (now benefits from Phase A guards too). Primary metric: defect-head FP count on analyzed presumed-clean parts (baseline 7/7, median conf > 0.95).
- [x] **Step 2:** Update `docs/validation/defect_classifier.md` (v2 section: dataset mix, val metrics, real-CAD FP before/after) + `real_eval.md` header/result lines. If FP stays high — say exactly that; the honest negative is still the deliverable (matches repo's eval discipline).
- [x] **Step 3:** BACKLOG close `defect-head-real-cad-augmentation` → Done w/ SHA (or downgrade + reopen w/ findings if FP unchanged); STATE.md + memory one-liners.
- [x] **Step 4: Commit** — `docs(validation): defect-head v2 real-CAD FP re-measure`.

---

## Risks (honest)

- A1 may show the hang in `heal_shape`/`parse_geometry`/`graph`, not a check — guard placement moves accordingly (same pattern, different fn); `analyze_file_safe` covers all cases regardless.
- Windows spawn overhead adds ~5–10 s to every UI/tool analyze call after A3. Acceptable for demo safety; note in docs. (Persistent worker = later optimization, ties into S3 `gen-eval-latency`.)
- OCC fillets fail often on boolean edges — fallback keeps generation alive but real featured coverage may be < nominal prob; record achieved feature rates.
- B may not fix the FP rate (root cause could be NURBS surface types absent from the box/cyl grammar entirely). Then the honest write-up + reopened item with findings is the outcome — do not force a positive claim.
- auto_label on ~1200 new parts is the long pole (~30–60 min); run in background, keep working.
