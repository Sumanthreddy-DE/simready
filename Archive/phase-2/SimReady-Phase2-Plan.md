# SimReady Phase 2 Implementation Plan

**Goal:** Add ML-based geometry analysis, human-readable reporting, remaining checks, and visual UI to SimReady.

**Phase 2 principle:** ML layer first — it's the highest-value differentiator. Report format second — it's what users (and interviewers) actually see. Visual UI last — it builds on both.

**Timeline estimate:** ~2 weeks focused work.

**Spec reference:** `SimReady-Phase2-Design.md` for detailed design decisions. `SimReady-Phase1-Design.md` for original product vision.

---

## Approved Build Order

### Pre-work (before coding)
- Read BRepNet paper: "BRepNet: A topological message passing system for solid models" (CVPR 2021)
- Read UV-Net paper: "UV-Net: Learning from Boundary Representations" (CVPR 2021)
- Browse BRepNet repo code, understand input format and model architecture
- Browse occwl repo, check installation instructions and compatibility

### Phase 2A: ML Foundation (Days 1-5)
1. Fix validator/healer two-pass flow + fix double healing on multi-body + extract shared OCC utils
2. Fix edge length computation (`GCPnts_AbscissaPoint.Length`) + refactor checks for per-face scores
3. B-Rep graph extractor (occwl or custom, reusing shared OCC utils)
4. BRepNet inference integration (pre-trained weights, CPU)
5. Score fusion (rules + ML combined scoring)
6. Auto-label pipeline on Fusion360 Gallery data
7. Fine-tuning scaffolding (Colab-compatible)

### Phase 2B: Report & Checks (Days 6-9)
1. Terminal pretty-print report (rich library)
2. HTML single-file report (Jinja2)
3. Overall scoring system (0-100 + color label)
4. Sharp edges check
5. Self-intersection check
6. `--verbose`, `--json`, `--html` CLI flags

### Phase 2C: Validation & UI (Days 10-14)
1. Test against SimJEB bracket models (5-10)
2. Test against GrabCAD models (3-5)
3. Document results side-by-side
4. Streamlit + PyVista web UI
5. Update README with demo screenshots
6. Final polish (README already rewritten, LICENSE already added)

---

## Phase 2A Tasks

### Task 1: Validator/Healer Two-Pass Fix + Pipeline Cleanup

**Modify:**
- `simready/validator.py` — split into file-load validation and BRep validation
- `simready/pipeline.py` — wire two-pass flow: validate → heal → re-validate
- `simready/pipeline.py` — fix double healing on multi-body files (heal once at top level, pass healed bodies to `_body_report()` without re-healing)
- Create `simready/occ_utils.py` — extract shared OCC traversal utilities (shape counting, bounding box, edge-face maps) from parser.py and checks.py. Both modules + future graph extractor import from here.
- Add `elapsed_seconds` field to report output (wall-clock pipeline timing)

**Two-pass flow:**
```
validate_file_load(path)  →  if OK  →  brep_check(shape)
                                          |
                                    if fails  →  heal(shape)  →  brep_check(healed)
                                                                    |
                                                              if still fails → Critical
                                                              if passes → continue with healed shape
```

**Multi-body fix:**
```
Current (broken):  heal(whole_shape) → split → heal(body_1) → heal(body_2)  # double healing
Fixed:             heal(whole_shape) → split(healed_shape) → analyze(body_1) → analyze(body_2)  # heal once
```

**Done when:**
- File that fails BRepCheck but is healable → gets healed and continues
- File that fails BRepCheck and healing doesn't help → still rejected as Critical
- Report shows two-pass outcome transparently
- Multi-body files healed once, not per-body
- `simready/occ_utils.py` exists, parser.py and checks.py import from it
- Report includes `elapsed_seconds`

---

### Task 2: Edge Length Fix + Per-Face Score Refactoring

**Modify:**
- `simready/checks.py` — fix `_edge_length()` to use `GCPnts_AbscissaPoint.Length(curve)` instead of parameter range. Current approach is wrong for curved edges (arcs, splines report parameter range as length, not physical arc length).
- `simready/checks.py` — refactor checks to return per-face scores alongside aggregate findings. Each check returns a `CheckResult` with both `per_face: dict[int, float]` (face_index → 0-1 score) and `findings: list[dict]` (backward-compatible aggregates).
- Move checks.py into `simready/checks/` package if size warrants it after refactor.

**Why per-face scores matter:**
- Auto-label pipeline needs per-face scores for ML training labels
- Score fusion needs per-face rule scores to combine with per-face ML scores
- Without this, ML integration is blocked

**Done when:**
- `_edge_length()` returns correct arc length for curved edges
- At least short_edges, thin_walls, small_features, and small_fillets checks return per-face scores
- Existing aggregate findings still work (backward compatible)
- Existing tests still pass

---

### Task 3: B-Rep Graph Extractor

**Create:**
- `simready/ml/__init__.py`
- `simready/ml/graph_extractor.py`
- `tests/test_graph_extractor.py`

**Responsibilities:**
- Extract face adjacency graph from OCC shape
- Node features per face: surface type, area, normal vector, mean curvature
- Edge features per adjacency: convexity (concave/convex/smooth), dihedral angle, edge length
- Output format compatible with BRepNet input

**Strategy:**
1. First try: use occwl for extraction (it wraps OCC topology into BRepNet-compatible format)
2. Fallback: write custom extractor using pythonocc (`TopExp_Explorer`, `BRepAdaptor_Surface`, `BRepAdaptor_Curve`)
3. Reuse shared OCC utilities from `simready/occ_utils.py` (created in Task 1) — edge-face maps, shape counting, bounding box. Do not duplicate topology traversal code.

**Done when:**
- Given a valid OCC shape, produces a graph dict with node features, edge features, adjacency list
- Works on the smoke_box.step fixture
- Works on multi_body.step (per-body extraction)

**FLAG: occwl installation risk.** occwl is a research repo (84 stars, Autodesk AI Lab). May have installation issues. Budget 0.5 days for environment setup. If occwl fails, custom extractor adds ~2 days.

---

### Task 4: BRepNet Inference

**Create:**
- `simready/ml/brepnet.py`
- `tests/test_brepnet.py`

**Responsibilities:**
- Load pre-trained BRepNet weights (downloaded separately, not in repo)
- Run inference on B-Rep graph → per-face embeddings (128-dim) + per-face scores (0-1)
- Derive complexity score from embeddings (entropy-based or distance-from-simple-centroid)
- Handle missing weights gracefully (return neutral 0.5 scores, like Phase 1 design doc specifies)

**License compliance:**
- BRepNet weights: CC BY-NC-SA 4.0 — personal/portfolio use only
- Weights NOT committed to repo
- Download script or instructions in `scripts/download_brepnet_weights.py`
- Code clearly documents: "Production deployment requires custom-trained model"

**Done when:**
- Given a B-Rep graph, returns per-face complexity scores
- Without weights, returns neutral scores (graceful degradation)
- Inference runs on CPU in < 5 seconds for typical bracket geometry

---

### Task 5: Score Fusion

**Create:**
- `simready/ml/combiner.py`
- `tests/test_combiner.py`

**Responsibilities:**
- Take rule scores (per-face, from checks) and ML scores (per-face, from BRepNet)
- Normalize rule scores to 0-1 per face
- Fuse: `combined = max(rule, ml) * 0.6 + min(rule, ml) * 0.4`
- Per-body aggregate: mean of per-face combined scores
- Overall model score: weighted mean across bodies

**Done when:**
- Combined scores produce sensible output on test fixtures
- ML-only and rules-only modes both work (if one source unavailable)

---

### Task 6: Auto-Label Pipeline

**Create:**
- `scripts/auto_label.py`
- `scripts/download_fusion360.py` (or instructions)

**Fusion360 subset:** Start with 100-500 models. Filter for "bracket" and "mounting" categories if dataset labels support it — keeps training data aligned with target test part.

**Pipeline:**
```
1. Download Fusion360 Gallery STEP files (subset: 100-500 models, filtered for brackets/mountings)
2. For each model:
   a. Run simready pipeline (validate → parse → checks)
   b. Extract per-face rule scores
   c. Generate label: score > 0.5 → "needs_refinement", else → "acceptable"
   d. Extract B-Rep graph (Task 3)
   e. Save: {graph, labels} pair
3. Output: training dataset directory with graph + label files
```

**Done when:**
- Can process a batch of Fusion360 STEP files
- Produces labeled dataset suitable for BRepNet fine-tuning
- Handles failures gracefully (skip broken files, log errors)

---

### Task 7: Fine-Tuning Scaffolding

**Create:**
- `scripts/train.py` (or `notebooks/finetune_brepnet.ipynb` for Colab)
- `scripts/evaluate.py`

**Responsibilities:**
- Load auto-labeled dataset
- Fine-tune BRepNet on per-face complexity prediction task
- Train/val split (80/20)
- Log training metrics (loss, precision, recall on "needs_refinement")
- Save fine-tuned weights
- Evaluation script: compare ML predictions vs rule labels on held-out set

**FLAG: Requires GPU.** Fine-tuning on CPU is impractical. Plan:
- Training script must be Colab-compatible (minimal path changes, Google Drive mounting for data)
- Inference remains CPU-only (load fine-tuned weights on VPS)
- Document Colab setup in README or `scripts/README.md`

**Done when:**
- Training script runs on Colab
- Fine-tuned model produces per-face scores
- Evaluation shows ML generalizes (flags some faces rules missed)

---

## Phase 2B Tasks

### Task 8: Terminal Pretty-Print Report

**Modify:**
- `simready/report.py` — add terminal formatting
- `simready/cli.py` — make pretty-print the default output

**Dependencies:**
- `rich` library (add to requirements.txt)

**Output format:**
```
SimReady Analysis: bracket.step
════════════════════════════════════════

  Score: 72/100 — NeedsAttention [orange]

  Category        Status   Issues
  ─────────────   ──────   ──────
  Watertight      PASS     0
  Manifold        FAIL     2 non-manifold edges
  Features        WARN     3 small fillets
  ...

  Top issues:
  [MAJOR] NonManifoldEdges — 2 edges shared by >2 faces
          → Repair or simplify topology
  ...
```

**Done when:**
- Default CLI output is colored, formatted, human-readable
- `--json` flag restores current JSON behavior
- Score calculation matches design doc formula

---

### Task 9: HTML Single-File Report

**Create:**
- `simready/html_report.py`
- `simready/templates/report.html` (Jinja2 template)

**Modify:**
- `simready/cli.py` — add `--html` flag

**Design principle:** Unified score (rules + ML fused). No separate "ML section" visible by default. ML details in collapsed depth section.

**Structure:**
1. Header with score badge (0-100, color-coded) — score already incorporates ML
2. Category pass/warn/fail grid
3. Heal summary
4. Findings table (sortable by severity, expandable detail rows)
5. "How this score was computed" (collapsed by default) — rule contribution, ML contribution, fusion formula
6. Geometry summary (face/edge/solid counts, dimensions)
7. Raw JSON (collapsed)
8. Footer: "Analysis powered by rule-based geometry checks + BRepNet learned complexity scoring on B-Rep topology"

**Done when:**
- `simready analyze part.step --html report.html` produces self-contained HTML file
- Opens in any browser, looks professional
- Inline CSS, no external dependencies

---

### Task 10: Sharp Edges Check

**Create or modify:**
- Add `check_sharp_edges()` to checks module

**Method:**
- For each edge shared by exactly 2 faces: compute dihedral angle using face normals at edge midpoint
- Flag edges with angle < 15 degrees (configurable)

**Severity:** Minor

**Done when:**
- Synthetic test file with known sharp edge is flagged
- Clean box is not flagged (all 90-degree edges pass)

---

### Task 11: Self-Intersection Check

**Create or modify:**
- Add `check_self_intersection()` to checks module

**Method:**
- Use OCC `BOPAlgo_ArgumentAnalyzer` or `BRepAlgoAPI_Check`
- Detect any self-intersecting geometry

**Severity:** Major

**Note:** Can be slow on complex models. Add 30-second timeout.

**Done when:**
- Synthetic test file with known self-intersection is flagged
- Clean models pass without timeout

---

### Task 12: CLI Flags Update

**Modify:**
- `simready/cli.py`

**Add:**
- `--json` — raw JSON output (current default becomes this flag)
- `--html PATH` — generate HTML report
- `--verbose` — include per-face detail in terminal output

**Default behavior change:** pretty-print terminal output (Task 8) becomes default.

---

## Phase 2C Tasks

### Task 13: Real-World Model Testing

**Steps:**
1. Download 10-20 SimJEB bracket models (`scripts/download_simjeb.py`)
2. Run SimReady on each, save reports
3. Download 3-5 GrabCAD bracket STEP files manually
4. Run SimReady on each, save reports
5. Document results: `docs/validation_results/` with per-model findings
6. Side-by-side comparison: SimReady findings vs known model complexity

**Done when:**
- 10+ real models tested
- Results documented
- Zero false positives on known-clean geometry
- All Critical issues caught

---

### Task 14: Streamlit + PyVista Web UI

**Create:**
- `ui/app.py`
- `ui/viz.py`

**Features:**
- File upload → run pipeline → show results
- 3D model with colored face overlays (green=clean, yellow=minor, red=major)
- ML complexity heatmap (blue=simple, orange=complex)
- Sidebar: score badge, category grid, findings list
- Download buttons: healed STEP, JSON, HTML report
- Multi-body: per-body tabs

**Risk:** PyVista + Streamlit rendering. Test `stpyvista` or Trame backend early.

**Done when:**
- Upload STEP → see 3D colored model + analysis results
- Works in browser
- Calls same `pipeline.py` (no separate logic)

---

### Task 15: Polish

- Update README with demo screenshots after UI is built (README structure already rewritten)
- ~~Add MIT LICENSE file~~ — already added
- Add `report_schema.json`
- Refactor `checks.py` into `checks/` package if it's gotten too large
- Update `environment.yml` and `requirements.txt` with new dependencies

---

## New Dependencies for Phase 2

```
# requirements.txt additions
torch>=2.0
rich>=13.0
jinja2>=3.1

# environment.yml additions (conda-forge)
- pytorch
- rich
- jinja2
- streamlit        # Phase 2C only
- pyvista          # Phase 2C only
```

Note: occwl may need `pip install git+https://github.com/AutodeskAILab/occwl.git`

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| occwl won't install cleanly | Medium | Medium | Custom B-Rep extractor fallback (2 days) |
| BRepNet weights don't produce useful complexity scores | Medium | High | Embeddings still useful; fine-tuning on auto-labels addresses this |
| Fusion360 Gallery download is slow/broken | Low | Medium | Start with small subset (100 models), expand later |
| GPU not available for fine-tuning | Low | Medium | Google Colab free tier; inference is CPU-only |
| PyVista + Streamlit rendering issues | Medium | Low | stpyvista wrapper; this is end-of-phase, non-blocking |
| Self-intersection check is too slow | Medium | Low | 30-second timeout, skip with warning |

---

## Exit Criteria for Phase 2

Phase 2 is complete when SimReady can:
- Run BRepNet inference on STEP geometry and produce per-face ML scores
- Fuse rule scores + ML scores into combined assessment
- Generate auto-labeled training data from Fusion360 Gallery
- Fine-tune BRepNet on auto-labeled data (Colab notebook works)
- Output human-readable terminal report with 0-100 score and color coding
- Output self-contained HTML report with expandable sections
- Detect sharp edges and self-intersections
- Pass real-world validation on 10+ SimJEB/GrabCAD models
- Display 3D colored model in Streamlit web UI
- All existing tests still pass + new tests for ML and report modules

---

## Blunt Summary

Phase 1 proved the core loop works. Phase 2 adds the "AI" that makes this a portfolio differentiator. ML layer is the priority — without it, this is a Python script. With it, this is a domain-specific AI system for CAD geometry analysis. Build ML first, make it readable second, make it visual third.
