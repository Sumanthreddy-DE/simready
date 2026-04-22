# SimReady — Phase 2 Design Document

Date: 2026-04-21
Spec reference: `SimReady-Phase1-Design.md` remains the product/design vision. This file extends it with Phase 2 scope.

---

## Phase 1 Review Summary

### What Phase 1 delivered
- CLI-first Python package with modular architecture
- STEP file validation (file load, null shape, BRepCheck)
- Basic geometry parsing (face/edge/solid counts, bounding box)
- 10 geometry checks: degenerate geometry, non-manifold edges, open boundaries, short edges, thin walls (bbox-based), small features, small fillets, duplicate bodies, duplicate faces, orientation nuance
- Conservative auto-healing via OCC ShapeFix
- Multi-body splitting with per-body reports
- Healed STEP export (`--export-healed`)
- Stable JSON report output
- 8 test files, 7 synthetic STEP fixtures, clean + failure paths covered
- 11 disciplined commits, incremental build

### Phase 1 gaps (carried into Phase 2)

| Gap | Detail | Action |
|-----|--------|--------|
| **Sharp edges check** | Design doc check #3 (dihedral angle between adjacent faces). Not implemented. | Add in Phase 2 |
| **Self-intersection check** | Design doc check #8 (Boolean self-intersection test). Not implemented. | Add in Phase 2 |
| **Gap/overlap check** | Design doc check #7 (face-pair adjacency analysis). Open boundaries partially covers this but not face-pair gap detection. | Add in Phase 2 |
| **Validator blocks healer** | `validator.py` rejects BRepCheck failures as Critical, preventing healer from attempting repair. Pipeline heals *after* validation but validation already rejected the file. | Fix: let healer attempt repair first, re-validate after healing. Add a two-pass flow: validate → if BRepCheck fails → heal → re-validate → if still fails → reject. |
| **Thin wall check is bbox-only** | Current check compares min/max bounding box dimensions. Catches plate-like parts but misses local thin walls within complex geometry. Design doc specifies "face-pair distance comparison." | Improve in Phase 2 with ray-casting or offset-surface approach |
| **No `--verbose` CLI flag** | Design doc mentions verbose mode for per-face scoring. | Add in Phase 2 (needed for ML per-face output) |
| **No LICENSE file** | Design doc says MIT or Apache 2.0. | Add MIT LICENSE file |
| **No `report_schema.json`** | Design doc mentions it at repo root. | Add after report format is finalized |
| **No `pyproject.toml`** | Can't `pip install -e .` or use `simready` as CLI command. Only `python -m simready.cli`. | Defer to Phase 3 |
| **`checks.py` monolith** | 520+ lines in single file. Design doc planned `checks/` package with one file per check. | Refactor when adding new checks in Phase 2 |
| **Report is JSON-only** | No human-readable output. Engineers don't read raw JSON. | Major Phase 2 deliverable: terminal + HTML report |
| **No real-world test models** | Only tested on synthetic fixtures in `tests/data/`. | Test against SimJEB brackets and GrabCAD models in Phase 2 |
| **Double healing on multi-body** | `pipeline.py` heals the whole shape, then `_body_report()` heals each body again individually. Every body healed twice — wastes time, could produce inconsistent results. | Fix in Phase 2 Task 1 alongside validator two-pass flow. Heal once at top level, pass healed bodies to per-body report without re-healing. |
| **Edge length uses parameter range, not arc length** | `checks.py:_edge_length()` computes `abs(curve.LastParameter() - curve.FirstParameter())`. Correct for straight lines, wrong for curves (arcs, splines). A semicircle reports length ~3.14 regardless of radius. Short edge detection unreliable on curved edges. | Fix in Phase 2: use `GCPnts_AbscissaPoint.Length(curve)` instead. One-line change, aligns with BRepNet implementation notes which already reference the correct method. |
| **Checks return empty lists without OCC** | Every check returns `[]` when OCC imports missing. Running without pythonocc gives "SimulationReady" on any file. Validator catches this via pipeline, but direct `run_essential_checks()` calls would give false all-clear. | Low risk — document as known limitation. Pipeline path is safe. |
| **Per-face scores don't exist** | Current checks return per-shape aggregates ("3 short edges found"). Phase 2 ML score fusion and auto-labeling need per-face scores (face 7 = 0.8, face 12 = 0.3). | Refactor checks to return per-face results in Phase 2. See "Per-Face Score Refactoring" section below. |
| **No pipeline timing** | Design doc mentions performance targets (<10s simple, <30s medium). No timing captured in report. Phase 2 ML adds overhead. | Add `elapsed_seconds` to report in Phase 2. |
| **IGES mentioned but not supported** | Phase 1 design doc mentions "STEP/IGES input" in several places. Current implementation only supports STEP (`STEPControl_Reader`). IGES would need `IGESControl_Reader`. | STEP-only for Phase 1 and Phase 2. IGES support deferred to Phase 3+. Clarified in this document. |

---

## Phase 2 Goals

Build the ML layer that transforms SimReady from "clever scripting" into "domain-specific AI for CAD geometry analysis." Add human-readable reporting. Complete the remaining geometry checks. Validate against real-world models.

### Phase 2 deliverables (in priority order)
1. **ML layer** — BRepNet integration with per-face complexity scoring
2. **Auto-label pipeline** — Rules bootstrap ML training data from Fusion360 Gallery
3. **Fine-tuning scaffolding** — Pipeline to fine-tune BRepNet on auto-labeled data
4. **Human-readable report** — Terminal pretty-print + HTML single-file report
5. **Remaining geometry checks** — Sharp edges, self-intersection, improved gap detection
6. **Validator/healer fix** — Two-pass validation flow
7. **Real-world model testing** — SimJEB brackets, GrabCAD models
8. **Visual UI** — Streamlit + PyVista with 3D colored overlays

### Deliberately deferred (Phase 3+)
- `pyproject.toml` / pip packaging
- Geometry generation (separate project)
- REST API
- Boundary condition suggestions
- Thermal/CFD support
- React frontend

---

## ML Layer Design

### Architecture

```
STEP file
  |
  v
Existing pipeline (validate → heal → parse → split)
  |
  v
B-Rep Graph Extractor (NEW)
  - Extract face adjacency graph from OCC topology
  - Node features: face type, area, normal, curvature
  - Edge features: convexity (concave/convex), dihedral angle, edge length
  - Output: graph structure compatible with BRepNet input format
  |
  v
BRepNet Inference (NEW)
  - Load pre-trained weights (Fusion360 Gallery segmentation)
  - Run inference on B-Rep graph
  - Output: per-face embedding vectors + per-face complexity score (0-1)
  |
  v
Score Fusion (NEW)
  - Rule scores: from existing checks, normalized to 0-1 per face
  - ML scores: from BRepNet, already 0-1
  - Combined formula: combined = max(rule, ml) * 0.6 + min(rule, ml) * 0.4
  - See Phase 1 design doc (lines 289-309) for rule/ML agreement interpretation table. Phase 2 maps combined scores to the 0-100 numeric system described below.
  - Per-body aggregate: mean of per-face combined scores
  |
  v
Report (ENHANCED)
  - Overall readiness score (0-100)
  - Per-body ML complexity aggregate
  - Per-face scores in verbose/HTML mode
```

### BRepNet Integration

**What:** Pre-trained BRepNet model for per-face complexity scoring on B-Rep topology.

**Pre-trained task:** BRepNet was trained on Fusion360 Gallery for face segmentation (classifying face types: fillet, chamfer, pocket, boss, etc.). The per-face embeddings capture geometric complexity even though the original task is segmentation.

**How we use it:**
1. Extract B-Rep graph from OCC shape (face adjacency, node/edge features)
2. Run BRepNet inference → per-face embedding (128-dim) + per-face softmax scores
3. Derive complexity score from embedding: faces with high entropy across segmentation classes = geometrically complex = likely need mesh refinement
4. Alternatively: use embedding distance from "simple face" centroid as complexity proxy

**License:** CC BY-NC-SA 4.0 (non-commercial). SimReady is a personal/portfolio project — acceptable for demo use. Production deployment would require a custom-trained model. This constraint is documented explicitly.

**Dependency path:**
1. Try occwl (Autodesk AI Lab) for B-Rep graph extraction in BRepNet-compatible format
2. If occwl doesn't install cleanly → write minimal B-Rep graph extractor using pythonocc directly (we already have topology traversal code in `checks.py`)
3. BRepNet weights downloaded separately, not bundled in repo (license compliance)

### BRepNet Architecture Reference

Key architecture points for implementation:

**Graph structure — three entity types:**
- **Faces:** the surface patches of the B-Rep solid
- **Edges:** shared boundaries between faces
- **Coedges:** directed uses of an edge by a face. Each edge has exactly 2 coedges (one per adjacent face). This directional information captures how faces relate to each other asymmetrically — it's what makes BRepNet topology-aware rather than just geometry-aware.

**Message passing flow (circular):**
```
face → coedge → edge → coedge → face
```
Information propagates through the B-Rep topology graph in this cycle. Multiple rounds of message passing build up increasingly rich per-face representations.

**Input features per entity:**
| Entity | Features |
|--------|----------|
| Face | Surface type (plane/cylinder/cone/sphere/torus/bspline), area, normal vector at centroid, UV bounding box |
| Edge | Edge length, convexity flag (concave/convex/smooth), midpoint curvature |
| Coedge | Orientation (same/opposite as edge direction), which face it belongs to |

**Output:**
- Per-face embedding vectors (128-dim) — learned representations of geometric context
- Per-face softmax scores across 24 segmentation classes (fillet, chamfer, pocket, boss, through-hole, blind-hole, etc.)

**How we derive complexity from segmentation embeddings:**
- Faces with high entropy across many segmentation classes = geometrically ambiguous = complex
- Faces that cleanly classify as one type (e.g., clearly a planar face) = simple
- Alternatively: compute embedding distance from a "simple face" cluster centroid

**occwl's role:** Wraps pythonocc to extract exactly this graph format — face/edge/coedge adjacency + per-entity features in numpy arrays. If occwl fails, we build a lighter version using `TopExp_Explorer` + `BRepAdaptor_Surface` + `BRepAdaptor_Curve` from existing `checks.py` code.

**Paper:** Jayaraman et al., "UV-Net: Learning from Boundary Representations" (CVPR 2021) and "BRepNet: A topological message passing system for solid models" (CVPR 2021). Read these before implementing.

### Auto-Label Pipeline

**Purpose:** Generate ML training labels from rule engine output. Rules bootstrap ML, ML generalizes beyond rules.

**Why auto-label over manual label:**
- **Scale:** Fusion360 Gallery has ~8,000 models. Batch-process all of them. Manual labeling = maybe 50-100 faces per day.
- **Consistency:** Rules apply identical logic every time. Human labelers disagree on "needs refinement."
- **Narrative:** "Deterministic rules bootstrap ML training data, then ML learns to generalize to unseen geometry patterns." Real ML engineering story.
- **Honest limitation:** ML trained on rule labels can't be better than rules on training distribution. But it generalizes to unseen patterns rules miss. This tradeoff is documented.

**Fusion360 Gallery subset strategy:**
- Full dataset: ~8,000 models (large download). Start with 100-500 models.
- Filter for "bracket" and "mounting" categories if dataset labels support it — keeps training data aligned with target test part (automotive mounting bracket).
- Expand to full dataset later if initial results are promising.

**Pipeline:**
```
Fusion360 Gallery STEP files (100-500 model subset, filtered for brackets/mountings)
  |
  v
SimReady rule engine (run_essential_checks per face)
  |
  v
Per-face label generation:
  - Score each face: 0.0 (no issues) to 1.0 (worst violation)
  - Aggregate across checks: max score per face
  - Threshold: score > 0.5 → "needs_refinement", else → "acceptable"
  |
  v
Training dataset:
  - Input: B-Rep graph (from occwl or custom extractor)
  - Label: per-face binary or continuous score from rules
  |
  v
Fine-tune BRepNet on this data
  |
  v
Evaluate: compare ML predictions vs rule labels on held-out set
  - Precision/recall on "needs_refinement" class
  - Cases where ML flags faces that rules missed (generalization evidence)
```

### GPU / Infrastructure Note

**FLAG:** Fine-tuning BRepNet requires GPU. VPS development environment does not have GPU access.

**Plan:**
- Inference (Level A demo): CPU-only, runs on VPS. Pre-trained weights, no training needed.
- Fine-tuning (Level B): Use Google Colab or cloud GPU instance. Export fine-tuned weights, load for inference on VPS.
- Training scripts should be Colab-compatible (notebook or script with minimal path changes).

---

## Report Format Redesign

### Problem
Current output is raw JSON. No engineer reads this. Report needs to be human-readable with an at-a-glance summary.

### Scoring System

**Overall readiness score: 0-100**

Formula:
```
base_score = 100
- Critical finding: -100 (instant zero)
- Major finding: -15 each
- Minor finding: -5 each
- ML complexity penalty: -(mean_ml_score * 20)  # 0-20 point range
- Floor at 0
```

**Graceful degradation:** When BRepNet weights are not available, ML complexity penalty is **zero** (not 0.5 * 20 = 10). The neutral 0.5 fallback applies to per-face score fusion only (so rules still dominate the combined per-face score), but the overall 0-100 deduction skips ML entirely. This prevents phantom score penalties when ML is simply not installed.

**Color-coded labels:**
| Score Range | Label | Color |
|-------------|-------|-------|
| 90-100 | SimulationReady | Green |
| 70-89 | ReviewRecommended | Yellow |
| 40-69 | NeedsAttention | Orange |
| 0-39 | NotReady | Red |

**Per-category traffic lights:**
| Category | PASS | WARN | FAIL |
|----------|------|------|------|
| Watertight | No open boundaries | — | Open boundaries or no solid |
| Manifold | No non-manifold edges | — | Non-manifold edges found |
| Features | No small features | Minor small features | Major small features |
| Orientation | Consistent normals | Minor nuance | Inconsistent |
| Degenerate | No issues | — | Zero-length edges or collapsed faces |
| Healing | All issues auto-fixed | Partial fix | Healing failed |

### Terminal Output (default)

Using `rich` library for colored tables and formatting. ~20-30 lines.

```
SimReady Analysis: bracket.step
════════════════════════════════════════

  Score: 72/100 — NeedsAttention

  Category        Status   Issues
  ─────────────   ──────   ──────
  Watertight      PASS     0
  Manifold        FAIL     2 non-manifold edges
  Features        WARN     3 small fillets
  Orientation     PASS     0
  Degenerate      PASS     0

  Healing: 2 fixed, 1 remaining
  Bodies: 1 solid detected
  ML Complexity: 0.63 (Medium)

  Top issues:
  [MAJOR] NonManifoldEdges — 2 edges shared by >2 faces
          → Repair or simplify topology before simulation
  [MAJOR] ThinWalls — Thickness ratio 0.018
          → Inspect thin regions, confirm meshable
  [MINOR] SmallFilletsOrHoles — 3 cylindrical faces below threshold
          → Inspect small fillets, consider defeaturing

  Full report: simready analyze bracket.step --html report.html
```

### HTML Report (`--html` flag)

**Design principle:** The score IS the ML story. Don't separate "rule score" and "ML score" in the visible report. Show one unified score (0-100) that already incorporates ML. The reader sees a smart, actionable engineering report. The ML sophistication is embedded in the score, not presented as a separate technical section.

**One-line footer attribution:** "Analysis powered by rule-based geometry checks + BRepNet learned complexity scoring on B-Rep topology." That's it. Tells the reader ML is in there without lecturing.

Single scrollable page. Sections:

1. **Header** — File name, date, overall score badge (large, colored). The score already fuses rules + ML.
2. **Category grid** — Pass/warn/fail traffic lights, one row per category
3. **Heal summary** — What was fixed, what remains
4. **Findings table** — Sortable by severity, expandable detail rows
5. **How this score was computed** (collapsed by default) — Rule contribution (X points deducted for Y findings), ML contribution (mean face complexity from BRepNet embeddings), fusion formula. This is the depth layer — available on demand, not forced on the reader.
6. **Geometry summary** — Face/edge/solid counts, bounding box dimensions
7. **Raw JSON** (collapsed) — Full JSON for copy-paste or programmatic use

**Surface = clean and actionable. Depth = available on demand.** An interviewer sees a polished engineering tool. If they ask "how does the scoring work?" — expand section 5 or explain verbally.

Template: single self-contained HTML file (inline CSS, no external dependencies). Opens in any browser. Shareable.

### CLI Flags

```
python -m simready.cli analyze part.step                    # terminal pretty-print (default)
python -m simready.cli analyze part.step --json             # raw JSON (current behavior, for scripting)
python -m simready.cli analyze part.step --html report.html # HTML report file
python -m simready.cli analyze part.step --output report.json --html report.html  # both
python -m simready.cli analyze part.step --verbose          # terminal with per-face detail
python -m simready.cli analyze part.step --export-healed part_healed.step  # (existing)
```

---

## Input Format Clarification

**Phase 1 and Phase 2: STEP files only.** The Phase 1 design doc mentions "STEP/IGES" in several places — this was aspirational. The current implementation only supports STEP via `STEPControl_Reader`. IGES would need a separate `IGESControl_Reader` integration.

IGES support is deferred to Phase 3+ as a future enhancement. All Phase 2 work (ML training, auto-labeling, testing, UI) targets STEP files exclusively. This is not a limitation in practice — STEP is the dominant interchange format for structural/mechanical FEA workflows.

---

## Per-Face Score Refactoring

**Problem:** Current checks return per-shape aggregates ("detected 3 short edges"). Phase 2 ML score fusion and auto-label pipeline need per-face scores (face 7 = 0.8, face 12 = 0.3).

**Approach: Refactor existing checks (Option A).**

Why Option A (refactor) over Option B (separate module):
- Avoids code duplication — same geometric logic shouldn't exist in two places
- Keeps checks.py as the single source of truth for geometry assessment
- Per-face results can still be aggregated into the current per-shape findings format for backward compatibility
- Modular design: functions compute per-face, callers aggregate as needed

**Refactored check signature:**
```python
# Current (Phase 1):
def check_short_edges(shape, geometry_summary) -> list[dict]  # returns aggregate findings

# Refactored (Phase 2):
def check_short_edges(shape, geometry_summary) -> CheckResult
# where CheckResult contains:
#   per_face: dict[int, float]  # face_index → score (0.0 = clean, 1.0 = worst)
#   findings: list[dict]        # aggregate findings (backward compatible)
```

This way:
- Pipeline report still gets the same aggregate findings
- ML auto-label pipeline gets per-face scores for training labels
- Score fusion module gets per-face rule scores to combine with per-face ML scores
- No duplicate logic

---

## Modular Code Reuse: Parser ↔ ML Extractor

**Principle:** No duplicate OCC traversal code. The BRepNet graph extractor (`simready/ml/graph_extractor.py`) should reuse utilities from existing modules rather than reimplementing topology traversal.

**Shared utilities to extract from existing code:**
- `parser.py:_count_shapes()` — shape counting by type (faces, edges, solids)
- `parser.py:_bounding_box()` — bounding box extraction
- `checks.py` edge-face map construction (`topexp.MapShapesAndAncestors`)
- `checks.py:_edge_length()` — edge length computation (fix to use `GCPnts_AbscissaPoint.Length` first)
- `checks.py:_cylindrical_radii()` — surface type detection pattern

**Approach:** During Phase 2 refactoring, extract shared OCC traversal utilities into a `simready/occ_utils.py` module. Both `checks.py` and `ml/graph_extractor.py` import from it. This prevents the graph extractor from duplicating topology code that already works in checks.py.

---

## Pipeline Timing

Add `elapsed_seconds` field to the report output. Measures wall-clock time of the full pipeline (validate → heal → parse → check → ML → report).

```json
{
  "elapsed_seconds": 1.3,
  ...
}
```

Performance targets (from Phase 1 design doc):
- Simple parts (<50 faces): <10 seconds
- Medium parts (50-500 faces): <30 seconds
- Complex parts (500+ faces): best effort, log time

Phase 2 adds ML inference overhead. Track timing to ensure we stay within targets. If ML inference pushes past 30s on medium parts, consider caching embeddings or reducing graph extraction scope.

---

## Remaining Geometry Checks

### Sharp Edges (Design Doc Check #3)

**Method:** Calculate dihedral angle between adjacent faces sharing an edge. Use OCC `BRepAdaptor_Surface` to get face normals at edge midpoint, compute angle.

**Threshold:** < 15 degrees (configurable). Sharp internal angles cause stress concentration in FEA and force mesh refinement.

**Severity:** Minor (warning with suggestion to add fillet or confirm intentional).

### Self-Intersection (Design Doc Check #8)

**Method:** OCC `BRepAlgoAPI_Check` or `BOPAlgo_ArgumentAnalyzer` to detect self-intersecting geometry.

**Threshold:** Any occurrence.

**Severity:** Major (self-intersecting geometry blocks meshing).

**Note:** This check can be slow on complex models. Add timeout protection.

### Improved Gap/Overlap Detection (Design Doc Check #7)

**Method:** Beyond current open-boundary edge counting — analyze face-pair adjacency for gaps within tolerance. Use `BRepExtrema_DistShapeShape` for face-pair distance checks on suspicious regions.

**Threshold:** Tolerance-based (gap < assembly tolerance but > zero).

**Severity:** Major.

---

## Validator/Healer Two-Pass Fix

Current flow (broken):
```
validate → BRepCheck fails → REJECT (healer never runs)
```

Fixed flow:
```
validate_file_load(filepath)        # file exists? STEP readable? null shape?
  |
  if file load OK:
  v
brep_check(shape)                   # OCC BRepCheck_Analyzer
  |
  if brep_check fails:
  v
heal_shape(shape)                   # attempt repair
  |
  v
brep_check(healed_shape)           # re-validate
  |
  if still fails → report as Critical with "healing attempted but insufficient"
  if passes → continue with healed shape, note in report
```

This lets the healer attempt recovery before rejecting the file. Report transparently shows the two-pass outcome.

---

## Real-World Model Testing

### SimJEB (Primary)
- GE Bracket Challenge dataset from Harvard Dataverse
- 381 brackets with FEA ground truth
- ODC-By license (open)
- Download script in `scripts/download_simjeb.py`
- Run SimReady on 10-20 brackets, document findings side-by-side with known FEA results

### GrabCAD (Secondary)
- Search for "mounting bracket" and "engine bracket" STEP files
- GrabCAD ToS: free, non-commercial
- Download manually, test locally, do not commit to repo
- Document model names and SimReady results

### Success Criteria
- Zero false positives on clean models (SimReady score 90+ on known-good geometry)
- All Critical issues caught (no miss on non-manifold, open boundaries, degenerate geometry)
- ML scores correlate with geometric complexity (complex brackets score higher than simple boxes)
- Side-by-side comparison on 5-10 models for portfolio documentation

---

## Visual UI (End of Phase 2)

### Streamlit + PyVista
- Thin wrapper over same `pipeline.py`
- Upload STEP → run analysis → show 3D model with colored overlays
- Color scheme: green (clean) → yellow (minor) → red (major) per face
- ML complexity heatmap: blue (simple) → orange (complex)
- Sidebar: score badge, category grid, findings list
- Download buttons: healed STEP, JSON report, HTML report

### Known Risk
PyVista in Streamlit has rendering limitations. May need `stpyvista` wrapper or Trame backend. Test early.

---

## Separate Project Ideas (NOT SimReady)

These came up during review but are out of scope:

| Idea | Why Separate | Notes |
|------|-------------|-------|
| **Geometry generation / surrogate prediction** | Different problem domain (prediction vs analysis). MecAgent JD mentions "part generation" but SimReady is analysis-only. | Already noted in Phase 1 design doc as "Project 2" |
| **CAD software plugin** | Integrating directly into SolidWorks/Fusion/NX is a different product. SimReady works on exported STEP files. | Could be Phase 4+ or separate project |

---

## Tech Stack Additions for Phase 2

| Component | Library | Why |
|-----------|---------|-----|
| B-Rep graph extraction | occwl (primary) or custom pythonocc extractor (fallback) | BRepNet-compatible graph format |
| ML model | BRepNet (pre-trained, CC BY-NC-SA 4.0) | Per-face embeddings on B-Rep topology |
| ML framework | PyTorch | BRepNet dependency |
| Auto-label pipeline | SimReady rule engine + Fusion360 Gallery | Bootstrap training data from rules |
| Terminal formatting | rich | Colored tables, progress bars, score display |
| HTML report | Jinja2 + inline CSS | Single-file self-contained HTML |
| 3D visualization | PyVista + stpyvista | Streamlit-compatible 3D rendering |
| Web UI | Streamlit | Thin wrapper over pipeline |

---

## Decision Log (Phase 2)

1. ML layer is top priority — transforms project from scripting to AI
2. BRepNet for demo with CC BY-NC-SA 4.0 license clearly documented; production path = custom model
3. Auto-labeling chosen over manual labeling for scale, consistency, and narrative strength
4. Report format: terminal pretty-print (default) + HTML (--html flag) + JSON (--json flag)
5. Scoring: 0-100 numeric with color-coded label (Green/Yellow/Orange/Red)
6. Per-body ML aggregate in default report; per-face scores in verbose/HTML mode
7. Sharp edges, self-intersection, gap/overlap checks added to Phase 2
8. Validator/healer two-pass fix added to Phase 2
9. Geometry generation kept as separate project, not mixed into SimReady
10. Phase 2 design and plan in separate files from Phase 1 (cleaner git history)
11. Fine-tuning requires GPU — plan for Google Colab, document in plan
12. occwl is primary dependency for B-Rep graph extraction; custom extractor as fallback
13. Real-world testing on SimJEB (10-20 brackets) + GrabCAD models
14. Install packaging (pyproject.toml) deferred to Phase 3
15. BRepNet paper (CVPR 2021) must be read before implementing graph extractor
16. Fusion360 Gallery subset: start with 100-500 models, filter for brackets/mountings if labels support it
17. HTML report uses unified score (rules + ML fused) — no separate "ML section" visible by default. ML details in collapsed "How this score was computed" section.
18. Implementation order: Task 1 (validator fix) first, then Task 2 (graph extractor) — sequential, not jumping to ML directly
19. No implementation in this session — design/plan files only, implementation in later sessions on VPS
20. Double healing on multi-body: fix alongside validator two-pass (Task 1). Heal once at top level, don't re-heal per body.
21. Edge length bug: fix `_edge_length()` to use `GCPnts_AbscissaPoint.Length()` instead of parameter range. One-line fix during Phase 2.
22. Per-face scores: refactor existing checks (Option A) — no duplicate logic. Checks return both per-face scores and aggregate findings.
23. Modular code reuse: extract shared OCC traversal utilities into `simready/occ_utils.py`. Graph extractor and checks both import from it. No duplicated topology code.
24. Pipeline timing: add `elapsed_seconds` to report output. Track against performance targets.
25. STEP-only for Phase 1 and 2. IGES support deferred to Phase 3+. Phase 1 design doc mentions IGES — that was aspirational, not implemented.
26. IGES would need `IGESControl_Reader` — separate integration, different file quirks. Not worth the scope for Phase 2.
