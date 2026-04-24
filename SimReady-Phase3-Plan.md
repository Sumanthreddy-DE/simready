# SimReady Phase 3: Demo-Ready & Real-World Hardening

**Goal:** Take SimReady from "working pipeline with scaffold UI" to "demo-ready product" suitable for showing to MecAgent (AI CAD copilot company), portfolio presentation, and real-world GrabCAD models.

**Predecessor:** Phase 1 (core pipeline) and Phase 2 (ML layer + reports) are complete. See `SimReady-Phase1-Plan.md` and `SimReady-Phase2-Plan.md` for history. 58 tests pass. CLI, JSON, HTML reports all work. Streamlit UI is scaffold only.

**What Phase 3 covers:** OCC compatibility hardening, pipeline robustness for complex geometry, complexity-aware scoring, Streamlit UI rewrite, report polish, GrabCAD real-world testing, and demo packaging.

**Audience for this plan:** An AI agent that will implement these changes autonomously. The human reviewer will verify after.

**Environment:**
- Python 3.10 via micromamba at `C:/mm/sr`
- Run tests: `C:/Users/suman/AppData/Local/micromamba/Library/bin/micromamba.exe run -p C:/mm/sr python -m pytest tests/ -v`
- Run Streamlit: `C:/Users/suman/AppData/Local/micromamba/Library/bin/micromamba.exe run -p C:/mm/sr streamlit run ui/app.py`
- pythonocc-core 7.9.3 installed (use `breptools.UVBounds` not `breptools_UVBounds`)
- All OCC imports must be wrapped in try/except ImportError for graceful degradation

---

## Current State (what already works)

### Pipeline (`simready/pipeline.py`)
- `analyze_file(filepath, export_healed_path=None)` → full report dict
- Two-pass validation → healing → rule checks → graph extraction → ML inference → score fusion
- Multi-body splitting with per-body reports
- Returns: status, score (0-100), findings, geometry, graph metadata, ML metadata, per-face scores

### CLI (`simready/cli.py`)
- `python -m simready.cli analyze part.step` — terminal pretty-print (rich)
- `--json` — raw JSON output
- `--html report.html` — self-contained HTML report
- `--export-healed part_healed.step` — export healed geometry
- `--verbose` — per-face scores in terminal

### Reports
- Terminal: rich-formatted with score, geometry table, findings list (`simready/report.py`)
- HTML: dark theme, Jinja2 template, score badge, findings table, scoring details, raw JSON (`simready/html_report.py` + `simready/templates/report.html`)

### ML Layer
- Graph extractor: face nodes, edge features, coedge traversal, adjacency (`simready/ml/graph_extractor.py`)
- BRepNet: heuristic fallback model, per-face scores + embeddings (`simready/ml/brepnet.py`)
- Combiner: 60/40 rule+ML fusion, 0-100 scoring, severity labels (`simready/ml/combiner.py`)

### Streamlit UI (`ui/app.py`) — scaffold only
- File upload + pipeline call
- Score metric + status
- Findings JSON dump + geometry JSON dump
- Face overlays dataframe
- No 3D visualization, no visual polish

### Tests
- 58 tests across 12 test files, all passing
- Coverage: pipeline, checks, graph extractor, combiner, BRepNet, CLI, reports, validator, parser, healer, splitter, UI viz helpers

---

## Pre-Task 0: Codex Review Fixes (DO FIRST — before anything else)

Two high-severity findings from adversarial review. Fix these before any other work.

### Fix 0a: Harden `uv_bounds()` against runtime OCC exceptions

**File:** `simready/occ_utils.py` (lines 79-92)

**Problem:** The `uv_bounds()` compat shim only catches `ImportError` and `AttributeError`. If `breptools.UVBounds(face)` raises a runtime OCC exception (e.g. on degenerate geometry, NURBS evaluation failure, or a different call signature in an older build), the exception escapes. Since `extract_brep_graph()` calls `uv_bounds()` without a guard, one bad face crashes the entire pipeline.

**Fix:** Catch `Exception` on call-time, try legacy path on any failure, return zeros only after both fail:

```python
def uv_bounds(face: Any) -> tuple[float, float, float, float]:
    """Return (umin, umax, vmin, vmax) for a face, with pythonocc version compat."""
    # Try new API first (pythonocc 7.9+)
    try:
        from OCC.Core.BRepTools import breptools
        return tuple(float(v) for v in breptools.UVBounds(face))
    except Exception:
        pass
    # Fall back to deprecated free function
    try:
        from OCC.Core.BRepTools import breptools_UVBounds
        return tuple(float(v) for v in breptools_UVBounds(face))
    except Exception:
        pass
    return (0.0, 0.0, 0.0, 0.0)
```

Change is minimal: `(ImportError, AttributeError)` → `Exception` on both try blocks.

### Fix 0b: Restore `TopologyExplorer` constructor fallback

**File:** `simready/ml/graph_extractor.py` (lines 261-268)

**Problem:** `_safe_topology_explorer()` now passes `ignore_orientation=True` but catches all exceptions uniformly. On older pythonocc where `ignore_orientation` keyword is unsupported, this returns `None`, making the entire `_attached_faces_by_edge_via_topology_explorer()` fallback path useless. Silent graph corruption — empty adjacency, empty connected_faces.

**Fix:** Try with keyword first, fall back to plain constructor:

```python
def _safe_topology_explorer(shape: Any):
    """Return a TopologyExplorer with ignore_orientation=True for unique edges."""
    if TopologyExplorer is None:
        return None
    try:
        return TopologyExplorer(shape, ignore_orientation=True)
    except TypeError:
        # Older pythonocc without ignore_orientation keyword
        try:
            return TopologyExplorer(shape)
        except Exception:
            return None
    except Exception:
        return None
```

Key change: catch `TypeError` specifically (wrong keyword), retry without it. Other exceptions still return `None`.

### Verification for Fix 0a and 0b

Run the full test suite after both fixes:
```bash
C:/Users/suman/AppData/Local/micromamba/Library/bin/micromamba.exe run -p C:/mm/sr python -m pytest tests/ -v
```

All 58 tests must still pass. These are defensive changes — they don't change behavior on pythonocc 7.9, only add safety for older/different builds.

---

## What Needs To Be Done

### Task 1: Streamlit UI Polish (HIGH PRIORITY — this is the demo)

**File:** `ui/app.py`

The current UI is a bare scaffold. Transform it into something that looks like a real product demo.

**Layout redesign:**

```
+--------------------------------------------------+
|  SimReady                              [sidebar]  |
|                                        Score: 72  |
|  [Upload STEP file]                    Status: RA |
|                                        Elapsed: s |
|  +-----------+  +-------------------------+       |
|  | Geometry  |  | Findings                |       |
|  | Faces: 6  |  | [severity] [check] [d.] |       |
|  | Edges: 12 |  | [severity] [check] [d.] |       |
|  | Solids: 1 |  |                         |       |
|  +-----------+  +-------------------------+       |
|                                                   |
|  Score Breakdown                                  |
|  [overall] [rule_mean] [ml_penalty] [label]       |
|                                                   |
|  Graph Topology                                   |
|  Faces: 6 | Edges: 12 | Coedges: 24 | Adj: 12   |
|                                                   |
|  Per-Face Heatmap Table                           |
|  [face_idx] [combined] [color] [ml] [ml_color]   |
|                                                   |
|  Multi-Body (if applicable)                       |
|  [Tab: Body 1] [Tab: Body 2] ...                 |
|                                                   |
|  ML Details (expander)                            |
|  Download: [JSON] [HTML] [Healed STEP]            |
+--------------------------------------------------+
```

**Specific requirements:**

1. **Sidebar** with:
   - Score as large `st.metric` with delta showing label (SimulationReady/ReviewRecommended/NeedsAttention/NotReady)
   - Status color indicator (green/yellow/orange/red)
   - Elapsed time
   - Download buttons: JSON report, HTML report, healed STEP (if available)

2. **Main area** with sections:
   - **Geometry summary** — `st.columns` with face/edge/solid counts + bounding box dimensions
   - **Findings table** — `st.dataframe` with severity color coding, not raw JSON. Columns: Severity, Check, Detail, Suggestion. Sort by severity (Critical > Major > Minor > Info)
   - **Score breakdown** — show how score was computed: overall, rule face mean, ML penalty, label
   - **Graph topology** — face/edge/coedge/adjacency counts from graph metadata
   - **Per-face heatmap** — `st.dataframe` with colored score columns using `build_face_overlay_payload()`
   - **Multi-body tabs** — if `report["bodies"]` has entries, show `st.tabs` with per-body findings, geometry, score
   - **ML details** — `st.expander` with model name, weights status, score source, aggregate score, notes
   - **Raw JSON** — `st.expander` at bottom

3. **Styling:**
   - Use `st.set_page_config(page_title="SimReady", page_icon="...", layout="wide")`
   - Add custom CSS via `st.markdown(unsafe_allow_html=True)` for severity colors in the findings table
   - Clean section headers with `st.subheader` and dividers

4. **Error handling:**
   - Show `st.error` if analysis fails
   - Show `st.warning` if status is NeedsAttention or NotReady
   - Show `st.success` if SimulationReady

5. **Download buttons:**
   - JSON: `st.download_button` with `json.dumps(report, indent=2)`
   - HTML: generate HTML report to temp file, offer download
   - Healed STEP: only if `report.get("healed_export")` exists

**Do NOT attempt 3D visualization.** PyVista/stpyvista integration is complex and unreliable. The data tables and scores are the demo value.

**Test after:** Upload `tests/data/smoke_box.step` — should show clean results. Upload `tests/data/multi_body.step` — should show multi-body tabs. Upload `tests/data/open_face.step` — should show findings.

---

### Task 2: Add Sample Analysis Script for Demo

**Create:** `scripts/demo_analysis.py`

A simple script that runs the pipeline on all test fixtures and prints a summary table. Useful for quick terminal demo without Streamlit.

```python
"""Run SimReady analysis on all test fixtures and print summary."""
from pathlib import Path
from simready.pipeline import analyze_file

fixtures = sorted(Path("tests/data").glob("*.step"))
for f in fixtures:
    report = analyze_file(str(f))
    score = report.get("score", {}).get("overall", "n/a")
    status = report.get("status", "Unknown")
    findings = len(report.get("findings", []))
    bodies = len(report.get("bodies", []))
    print(f"{f.name:30s}  score={score:>6}  status={status:20s}  findings={findings}  bodies={bodies}")
```

Keep it simple. No argparse needed.

---

### Task 3: HTML Report Template Improvements

**File:** `simready/templates/report.html`

The HTML report works but needs small polish:

1. **Add graph topology section** after geometry summary:
   ```html
   <section class="panel">
     <h2>B-Rep Graph</h2>
     <div class="grid">
       <div class="stat"><strong>Graph Faces</strong><br />{{ report.graph.face_count if report.graph else 'n/a' }}</div>
       <div class="stat"><strong>Graph Edges</strong><br />{{ report.graph.edge_count if report.graph else 'n/a' }}</div>
       <div class="stat"><strong>Coedges</strong><br />{{ report.graph.coedge_count if report.graph else 'n/a' }}</div>
       <div class="stat"><strong>Adjacency</strong><br />{{ report.graph.adjacency_count if report.graph else 'n/a' }}</div>
     </div>
   </section>
   ```

2. **Add multi-body section** if bodies exist:
   ```html
   {% if report.bodies %}
   <section class="panel">
     <h2>Multi-Body Analysis</h2>
     {% for body in report.bodies %}
     <details>
       <summary>Body {{ body.body_index }} — {{ body.status }} ({{ body.score.overall|default('n/a')|round(1) }}/100)</summary>
       <div class="grid">
         <div class="stat"><strong>Faces</strong><br />{{ body.geometry.face_count }}</div>
         <div class="stat"><strong>Findings</strong><br />{{ body.findings|length }}</div>
         <div class="stat"><strong>Score</strong><br />{{ body.score.overall|default('n/a')|round(1) }}</div>
       </div>
     </details>
     {% endfor %}
   </section>
   {% endif %}
   ```

3. **Add heal summary section** if healing was applied:
   ```html
   {% if report.heal %}
   <section class="panel">
     <h2>Healing</h2>
     <div class="grid">
       <div class="stat"><strong>Attempted</strong><br />{{ report.heal.attempted }}</div>
       <div class="stat"><strong>Applied</strong><br />{{ report.heal.applied }}</div>
       <div class="stat"><strong>Valid Before</strong><br />{{ report.heal.valid_before|default('n/a') }}</div>
       <div class="stat"><strong>Valid After</strong><br />{{ report.heal.valid_after|default('n/a') }}</div>
     </div>
   </section>
   {% endif %}
   ```

4. **Score badge color** should reflect status:
   - SimulationReady → green (`#22c55e`)
   - ReviewRecommended → yellow (`#eab308`)
   - NeedsAttention → orange (`#f97316`)
   - NotReady → red (`#ef4444`)
   - InvalidInput → red

   Add a JS or Jinja2 conditional to set the badge background color.

**Do NOT change the existing sections** — only add new ones and adjust the badge color.

---

### Task 4: Terminal Report Improvements

**File:** `simready/report.py`

The terminal report (`render_terminal_report`) works but could show more info:

1. **Add graph topology row** to the table:
   ```python
   graph = report.get("graph") or {}
   table.add_row("Graph Edges", str(graph.get("edge_count", "n/a")))
   table.add_row("Coedges", str(graph.get("coedge_count", "n/a")))
   ```

2. **Add ML status line** after findings:
   ```python
   ml = report.get("ml") or {}
   if ml.get("available"):
       console.print(f"ML: {ml.get('model_name', 'unknown')} ({ml.get('score_source', 'n/a')})")
   ```

3. **Color the score** based on status:
   ```python
   status = report.get("status", "")
   color = {"SimulationReady": "green", "ReviewRecommended": "yellow", "NeedsAttention": "dark_orange", "NotReady": "red"}.get(status, "white")
   console.print(f"Score: [bold {color}]{score.get('overall', 'n/a')}[/bold {color}]/100  {status}")
   ```

**Keep changes minimal** — don't restructure the function.

---

### Task 5: Environment & Packaging Polish

1. **Pin pythonocc-core version** in `environment.yml`:
   ```yaml
   - pythonocc-core>=7.8
   ```

2. **Add missing dependency** `pyvista` is NOT needed (no 3D viz). Remove any references if present.

3. **Verify `requirements.txt`** matches what's actually used. Current list:
   ```
   click>=8.1
   pytest>=8.0
   rich>=13.0
   jinja2>=3.1
   torch>=2.0
   streamlit>=1.30
   ```
   This is correct. `torch` is optional (BRepNet only). Add a comment:
   ```
   # Core
   click>=8.1
   rich>=13.0
   jinja2>=3.1
   # Optional: ML inference
   torch>=2.0
   # Optional: Web UI
   streamlit>=1.30
   # Testing
   pytest>=8.0
   ```

4. **Update `environment.yml`** to match — currently has `pytorch` which is the conda package name for `torch`. This is correct for conda but verify it resolves.

---

### Task 6: README Update

**File:** `README.md`

Update the "Current Caveats" section to reflect actual state:

```markdown
## Current Caveats

- BRepNet model uses heuristic fallback (geometry-based scoring) — actual neural weights require fine-tuning on labeled data.
- pythonocc-core 7.9+ required (older versions may have API incompatibilities).
- Streamlit UI provides data visualization only — no 3D CAD rendering.
- Test coverage is comprehensive for the analysis pipeline; real-world validation on industrial parts is ongoing.
```

Add a "Demo" section:

```markdown
## Demo

### Terminal
```bash
python -m simready.cli analyze tests/data/smoke_box.step
python -m simready.cli analyze tests/data/multi_body.step --verbose
python -m simready.cli analyze tests/data/open_face.step --html report.html
```

### Streamlit UI
```bash
streamlit run ui/app.py
```
Upload any STEP file to see the full analysis report.

### Batch Analysis
```bash
python scripts/demo_analysis.py
```
```

---

### Task 7: Pipeline Timeout & Exception Hardening (GrabCAD Readiness)

Real-world STEP files from GrabCAD/SimJEB can have hundreds of faces, NURBS surfaces, degenerate geometry, and other edge cases our test fixtures don't cover. The pipeline must not crash — it should always return a report, even if partial.

#### 7a: Pipeline-level timeout

**File:** `simready/pipeline.py`

Wrap the core analysis in a timeout. If analysis exceeds the limit, return a partial report with what was computed so far.

```python
import signal
import threading

ANALYSIS_TIMEOUT_SECONDS = 120  # 2 minutes max

def analyze_file(filepath: str, export_healed_path: str | None = None, timeout: int = ANALYSIS_TIMEOUT_SECONDS) -> dict[str, Any]:
    # ... existing code ...
```

**Implementation approach — use threading with a result container:**

```python
def analyze_file(filepath: str, export_healed_path: str | None = None, timeout: int = ANALYSIS_TIMEOUT_SECONDS) -> dict[str, Any]:
    started = time.perf_counter()
    result_container: list[dict[str, Any]] = []
    error_container: list[Exception] = []

    def _run():
        try:
            result_container.append(_analyze_file_inner(filepath, export_healed_path, started))
        except Exception as exc:
            error_container.append(exc)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    thread.join(timeout=timeout)

    if result_container:
        return result_container[0]
    
    elapsed = time.perf_counter() - started
    error_msg = str(error_container[0]) if error_container else f"Analysis timed out after {timeout}s"
    return build_report(
        filepath,
        SimpleNamespace(is_valid=False, errors=[{"severity": "Critical", "message": error_msg}]),
        None,
        [],
        bodies=[],
        elapsed_seconds=elapsed,
    )
```

Move the current `analyze_file` body into `_analyze_file_inner(filepath, export_healed_path, started)`.

**Do NOT use `signal.alarm`** — it doesn't work on Windows. Use threading.

**Add `timeout` parameter** to the CLI as well:
```python
@click.option("--timeout", type=int, default=120, help="Analysis timeout in seconds")
```

And to the Streamlit UI, add a sidebar slider:
```python
timeout = st.sidebar.slider("Analysis timeout (seconds)", 30, 300, 120)
```

#### 7b: Graph extractor exception hardening

**File:** `simready/ml/graph_extractor.py`

The `extract_brep_graph()` function has three main loops that iterate over faces and edges. If one face/edge throws an OCC exception (degenerate geometry, NURBS evaluation failure), the whole extraction crashes. Wrap each iteration in try/except so one bad face doesn't kill the graph.

**Face feature loop** (around line 378):
```python
for entry in faces:
    try:
        surface_type = _surface_type_name(entry.face)
        area = _face_area(entry.face)
        centroid = _face_centroid(entry.face)
        uv = uv_bounds(entry.face)
        normal = _face_normal(entry.face)
    except Exception:
        surface_type = "unknown"
        area = 0.0
        centroid = (0.0, 0.0, 0.0)
        uv = (0.0, 0.0, 0.0, 0.0)
        normal = (0.0, 0.0, 0.0)
    face_normals[entry.index] = normal
    graph.node_features.append({...})  # same as before
```

**Edge feature loop** (around line 401):
```python
for edge_entry in edges:
    attached = attached_faces_by_edge_hash.get(edge_entry.hash_code, [])
    try:
        length = edge_length(edge_entry.edge)
        curvature = _edge_midpoint_curvature(edge_entry.edge)
    except Exception:
        length = 0.0
        curvature = 0.0
    # ... rest of loop unchanged
```

**Coedge loop** (around line 442): Already has try/except on `WireExplorer`. Good enough.

**Add metadata about failures:**
```python
graph.metadata["face_feature_errors"] = face_error_count
graph.metadata["edge_feature_errors"] = edge_error_count
```

This way the report shows if any features were degraded.

#### 7c: Checks module exception hardening

**File:** `simready/checks.py`

The `run_essential_checks_detailed()` function calls multiple check functions. If one check throws an OCC exception on complex geometry, all subsequent checks are skipped.

Find `run_essential_checks_detailed` and wrap each check call:

```python
def run_essential_checks_detailed(shape: Any, geometry_summary: Any) -> CheckResult:
    results: list[CheckResult] = []
    for check_fn in [check_short_edges, check_thin_walls, check_small_features, ...]:
        try:
            results.append(check_fn(shape, geometry_summary))
        except Exception:
            # Log but don't crash — skip this check
            results.append(_result(findings=[{
                "check": check_fn.__name__,
                "severity": "Info",
                "detail": f"Check skipped due to internal error on this geometry.",
                "suggestion": "This check could not be completed. Manual review recommended.",
            }]))
    return _merge_check_results(results)
```

**Important:** Do NOT change how individual checks work internally. Only wrap the top-level calls.

#### 7d: BRepNet heuristic performance fix

**File:** `simready/ml/brepnet.py`

The `HeuristicBRepNetModel.infer()` method has an O(n*m) adjacency degree computation:

```python
adjacency_degree = sum(1 for pair in graph.adjacency if face_index in pair)
```

For a model with 500 faces and 750 adjacency pairs, this is 500 * 750 = 375,000 iterations. Precompute an adjacency degree map once:

```python
def infer(self, graph: GraphData) -> BRepNetInferenceResult:
    # Precompute adjacency degree map
    degree_map: dict[int, int] = {}
    for a, b in graph.adjacency:
        degree_map[a] = degree_map.get(a, 0) + 1
        degree_map[b] = degree_map.get(b, 0) + 1
    
    for node in graph.node_features:
        face_index = int(node.get("face_index", 0))
        adjacency_degree = degree_map.get(face_index, 0)
        # ... rest unchanged
```

Same fix in `_heuristic_face_score()` — it has the identical pattern. Either pass the `degree_map` or precompute inside the function.

---

### Task 8: Complexity Tier & Confidence Indicator

**Files:** `simready/ml/combiner.py`, `simready/pipeline.py`, `simready/report.py`, `simready/templates/report.html`, `ui/app.py`

Add a complexity tier to the report so users know how much to trust the score on complex models.

#### 8a: Complexity tier function

**File:** `simready/ml/combiner.py`

Add after `score_label()`:

```python
def complexity_tier(face_count: int) -> dict[str, Any]:
    """Classify model complexity and score confidence."""
    if face_count <= 50:
        return {
            "tier": "simple",
            "label": "Simple Geometry",
            "confidence": "high",
            "note": "Score is well-calibrated for simple geometry.",
        }
    if face_count <= 200:
        return {
            "tier": "moderate",
            "label": "Moderate Geometry",
            "confidence": "medium",
            "note": "Score is indicative. Manual review recommended for critical applications.",
        }
    if face_count <= 1000:
        return {
            "tier": "complex",
            "label": "Complex Geometry",
            "confidence": "low",
            "note": "Score is approximate. Checks may miss issues on complex geometry. Manual review strongly recommended.",
        }
    return {
        "tier": "very_complex",
        "label": "Very Complex Geometry",
        "confidence": "minimal",
        "note": "Model exceeds typical calibration range. Score should be treated as a rough indicator only.",
    }
```

#### 8b: Wire into pipeline

**File:** `simready/pipeline.py`

Import and call `complexity_tier` in `analyze_file` and `_body_report`:

```python
from simready.ml.combiner import score_label, score_report, complexity_tier

# In the report dict, add:
report["complexity"] = complexity_tier(geometry_summary.face_count)
```

Same for `_body_report`:
```python
return {
    ...
    "complexity": complexity_tier(geometry_summary.face_count),
}
```

#### 8c: Show in reports

**Terminal report** (`simready/report.py`): Add a line after the score:
```python
complexity = report.get("complexity", {})
if complexity:
    console.print(f"Complexity: {complexity.get('label', 'Unknown')} (confidence: {complexity.get('confidence', 'n/a')})")
```

**HTML report** (`simready/templates/report.html`): Add to hero section after score badge:
```html
{% if report.complexity %}
<p>Complexity: <strong>{{ report.complexity.label }}</strong> — confidence: {{ report.complexity.confidence }}</p>
<p class="meta">{{ report.complexity.note }}</p>
{% endif %}
```

**Streamlit UI** (`ui/app.py`): Show in sidebar under score:
```python
complexity = report.get("complexity", {})
if complexity:
    st.sidebar.caption(f"{complexity.get('label')} — {complexity.get('confidence')} confidence")
```

#### 8d: Test

**File:** `tests/test_combiner.py`

```python
from simready.ml.combiner import complexity_tier

def test_complexity_tier_simple():
    result = complexity_tier(6)
    assert result["tier"] == "simple"
    assert result["confidence"] == "high"

def test_complexity_tier_moderate():
    result = complexity_tier(100)
    assert result["tier"] == "moderate"

def test_complexity_tier_complex():
    result = complexity_tier(500)
    assert result["tier"] == "complex"

def test_complexity_tier_very_complex():
    result = complexity_tier(1500)
    assert result["tier"] == "very_complex"
    assert result["confidence"] == "minimal"
```

---

### Task 9: GrabCAD Test Fixtures & Smoke Tests

**Purpose:** Download 3-5 real-world STEP files from GrabCAD, add as test fixtures, and write tests that assert "no crash + report structure valid."

#### 9a: Download script

**Create:** `scripts/download_grabcad_samples.py`

```python
"""Download sample GrabCAD STEP files for real-world testing.

Since GrabCAD requires login for downloads, this script provides instructions
and verifies downloaded files are placed correctly.
"""
from pathlib import Path

SAMPLE_DIR = Path("tests/data/grabcad")
EXPECTED_FILES = [
    "bracket_simple.step",       # < 50 faces, simple bracket
    "bracket_medium.step",       # 50-200 faces, moderate complexity
    "housing_complex.step",      # 200+ faces, complex housing/enclosure
]

def check_samples():
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    missing = [f for f in EXPECTED_FILES if not (SAMPLE_DIR / f).exists()]
    if missing:
        print("Missing GrabCAD sample files:")
        print(f"  Place them in: {SAMPLE_DIR.resolve()}")
        for f in missing:
            print(f"  - {f}")
        print()
        print("Download instructions:")
        print("1. Go to grabcad.com and search for 'bracket STEP'")
        print("2. Download 3 models of varying complexity")
        print("3. Rename to the expected filenames above")
        print("4. Place in the tests/data/grabcad/ directory")
    else:
        print(f"All {len(EXPECTED_FILES)} sample files present.")
    return missing

if __name__ == "__main__":
    check_samples()
```

#### 9b: Smoke tests for real-world files

**Create:** `tests/test_grabcad.py`

```python
"""Smoke tests for real-world GrabCAD STEP files.

These tests are skipped if the GrabCAD sample files are not present.
They verify that the pipeline does not crash on real-world geometry
and produces a structurally valid report.
"""
import pytest
from pathlib import Path
from simready.pipeline import analyze_file

GRABCAD_DIR = Path("tests/data/grabcad")
GRABCAD_FILES = list(GRABCAD_DIR.glob("*.step")) + list(GRABCAD_DIR.glob("*.stp"))

REQUIRED_REPORT_KEYS = {"input_file", "status", "summary", "validation", "geometry", "findings"}


@pytest.mark.skipif(not GRABCAD_FILES, reason="No GrabCAD sample files in tests/data/grabcad/")
@pytest.mark.parametrize("step_file", GRABCAD_FILES, ids=lambda p: p.name)
def test_grabcad_no_crash(step_file):
    """Pipeline must not crash on real-world STEP files."""
    report = analyze_file(str(step_file))
    assert isinstance(report, dict)
    assert REQUIRED_REPORT_KEYS <= set(report.keys())
    assert report["status"] in {"SimulationReady", "ReviewRecommended", "NeedsAttention", "NotReady", "InvalidInput"}


@pytest.mark.skipif(not GRABCAD_FILES, reason="No GrabCAD sample files in tests/data/grabcad/")
@pytest.mark.parametrize("step_file", GRABCAD_FILES, ids=lambda p: p.name)
def test_grabcad_score_in_range(step_file):
    """Score must be a number between 0 and 100."""
    report = analyze_file(str(step_file))
    score = report.get("score", {}).get("overall")
    assert score is not None
    assert 0 <= score <= 100


@pytest.mark.skipif(not GRABCAD_FILES, reason="No GrabCAD sample files in tests/data/grabcad/")
@pytest.mark.parametrize("step_file", GRABCAD_FILES, ids=lambda p: p.name)
def test_grabcad_has_complexity_tier(step_file):
    """Report must include complexity tier after Task 8."""
    report = analyze_file(str(step_file))
    assert "complexity" in report
    assert report["complexity"]["tier"] in {"simple", "moderate", "complex", "very_complex"}
    assert report["complexity"]["confidence"] in {"high", "medium", "low", "minimal"}
```

**Important:** These tests use `@pytest.mark.skipif` so they don't fail when GrabCAD files aren't present. The regular test suite stays clean. When files are added, the tests activate automatically.

#### 9c: Add `tests/data/grabcad/` to `.gitignore`

GrabCAD files are copyrighted — don't commit them. Add to `.gitignore`:
```
tests/data/grabcad/
```

---

## Build Order

Execute in this order. Each task is independent enough to verify before moving on.

1. **Task 7** — Pipeline hardening (timeout, exception wrapping, perf fix) — do this FIRST so all later testing benefits
2. **Task 8** — Complexity tier (combiner + pipeline + reports)
3. **Task 1** — Streamlit UI (biggest visual impact)
4. **Task 3** — HTML template improvements
5. **Task 4** — Terminal report improvements
6. **Task 2** — Demo script
7. **Task 9** — GrabCAD test fixtures (can be done in parallel with UI work)
8. **Task 5** — Environment polish
9. **Task 6** — README update (last — reflects final state)

## Verification After Each Task

After each task, run the full test suite:
```bash
C:/Users/suman/AppData/Local/micromamba/Library/bin/micromamba.exe run -p C:/mm/sr python -m pytest tests/ -v
```

All 58+ tests must pass. Do not break existing functionality.

For Task 1 (Streamlit), also manually verify:
```bash
C:/Users/suman/AppData/Local/micromamba/Library/bin/micromamba.exe run -p C:/mm/sr streamlit run ui/app.py
```
Upload `tests/data/smoke_box.step`, `tests/data/multi_body.step`, and `tests/data/open_face.step`.

For Task 9 (GrabCAD), if sample files are present:
```bash
C:/Users/suman/AppData/Local/micromamba/Library/bin/micromamba.exe run -p C:/mm/sr python -m pytest tests/test_grabcad.py -v
```

---

## What Is NOT In Scope

These are future work, not part of this plan:

- **3D visualization** (PyVista/stpyvista) — too complex for demo timeline
- **Real BRepNet neural weights** — requires labeled training data
- **Fine-tuning pipeline** — scaffolds exist in `scripts/train.py`, not activating now
- **Sharp edges check** — planned in Phase 2 but not critical for demo
- **Self-intersection check** — planned in Phase 2 but not critical for demo
- **CI/CD pipeline** — nice-to-have, not demo-critical
- **pip installable package** — future work

---

## Files Summary

| File | Action | Task |
|------|--------|------|
| `simready/pipeline.py` | Add timeout wrapper, complexity tier | 7a, 8b |
| `simready/ml/graph_extractor.py` | Exception hardening in loops | 7b |
| `simready/checks.py` | Wrap check calls in try/except | 7c |
| `simready/ml/brepnet.py` | Precompute adjacency degree map | 7d |
| `simready/ml/combiner.py` | Add `complexity_tier()` function | 8a |
| `simready/cli.py` | Add `--timeout` flag | 7a |
| `ui/app.py` | Major rewrite + timeout slider + complexity display | 1, 7a, 8c |
| `simready/report.py` | Add graph info, ML status, colored score, complexity | 4, 8c |
| `simready/templates/report.html` | Add graph, multi-body, heal, complexity sections | 3, 8c |
| `scripts/demo_analysis.py` | Create new | 2 |
| `scripts/download_grabcad_samples.py` | Create new | 9a |
| `tests/test_grabcad.py` | Create new (skippable smoke tests) | 9b |
| `tests/test_combiner.py` | Add complexity tier tests | 8d |
| `.gitignore` | Add `tests/data/grabcad/` | 9c |
| `requirements.txt` | Reorganize with comments | 5 |
| `environment.yml` | Pin pythonocc version | 5 |
| `README.md` | Update caveats + add demo section | 6 |
