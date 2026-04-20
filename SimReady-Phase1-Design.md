# SimReady — AI-Assisted Simulation Pre-Processing Tool

## Phase 1 Design Document

Date: 2026-04-15
Updated: 2026-04-16 (v3 — incorporated third-party review findings)

---

## Simulation-Ready Definition

A **simulation-ready** CAD model for structural FEA means:
- **Watertight solid**: Closed, manifold solid with no open edges or gaps. Volumetric mesh can be generated.
- **No self-intersections or non-manifolds**: Geometrically valid solid (OCC `BRepCheck_Analyzer` passes).
- **No degenerate geometry**: No zero-area faces, zero-length edges, or collapsed topology.
- **Consistent orientation**: Face normals and shell orientations are consistent (no flipped faces).
- **Minimum feature size**: No features (walls, holes, fillets) below practical meshing limits.
- **Single body or cleanly split assembly**: Each body is a proper `TopoDS_Solid` with volume.

In short: *closed, non-self-intersecting solid, free of ill-shaped faces or tiny features, suitable for volumetric meshing.*

## What It Does

Upload a STEP file, get a simulation-readiness report with mesh recommendations — before you open your mesher.

- Input: STEP/IGES file (structural/mechanical parts)
- Output: CLI JSON report (primary) + optional 3D visualization with geometry health check, auto-heal summary, mesh density heatmap, complexity score
- Target user: FEM/CAE engineer who currently does this manually in 30-60 minutes per part
- Primary interface: CLI (`simready analyze input.stp --output report.json`)
- Optional interface: Streamlit + PyVista web UI (built on same pipeline)

## Why This Project Exists

- No open-source tool exists that takes a STEP file and outputs simulation-readiness assessment with ML
- Commercial tools (SimScale, Neural Concept) do parts of this behind paywalls
- Research repos (BRepNet, UV-Net, FeaGPT) solve individual pieces but nobody assembled them
- Portfolio project for job search targeting: AI-for-engineering startups/Mittelstand (Neural Concept, Monolith AI, SimScale, CADFEM), digital twin companies (Siemens, PTC, Hexagon), simulation software (Ansys, Altair, Dassault)

## User Flow

### CLI (Primary)
1. Engineer runs `simready analyze part.step`
2. Waits 10-30 seconds
3. Gets JSON report to stdout (or `--output report.json`)
4. Report contains: file validation, heal summary, geometry issues with severity + suggested actions, mesh recommendations, complexity score
5. Optional: `--export-healed` saves auto-healed geometry as `part_healed.step`
6. Optional: `--verbose` for detailed per-face scoring

### Web UI (Optional, built on same pipeline)
1. Engineer opens SimReady in browser (Streamlit)
2. Uploads STEP/IGES file
3. Waits 10-30 seconds
4. Gets interactive 3D view with colored overlays:
   - Auto-heal summary (what was fixed automatically)
   - Geometry health issues (red) — thin walls, tiny features, sharp edges, gaps
   - Mesh refinement zones (gradient: blue=coarse to orange=fine)
   - Complexity score (low/medium/high)
5. If multi-body file: per-body tabs with individual reports
6. Expands each finding for details and recommended actions
7. Downloads healed STEP (button) or exports report (PDF/JSON)

## Architecture

Six-layer pipeline with CLI-first architecture:

```
STEP/IGES file
     |
     v
Pre-Check: File Validation
  - Verify STEP read success (STEPControl_Reader status)
  - Check shape is not null
  - Run OCC BRepCheck_Analyzer global validation
  - If Critical failure → abort with error, skip all layers
     |
     v
Layer 0: Assembly Splitter
  - Detect multi-body / compound shapes
  - Split into individual bodies
  - Run pipeline per body
     |
     v
Layer 1: Parser (pythonocc / occwl)
  - STEP to B-Rep data
  - Unit/tolerance validation and normalization
  - Extract faces, edges, topology, curvatures, thicknesses, angles
     |
     v
Layer 1.5: Auto-Heal (OCC ShapeFix)
  - Topology repair only (Phase 1)
  - Fix gaps, bad wires, face stitching
  - Record before/after changes for report
  - Optionally export healed STEP (--export-healed)
  - Does NOT defeature (Phase 2)
     |
     +--------+--------+
     v                 v
Layer 2a: Rules     Layer 2b: ML (BRepNet / UV-Net)
  - 11 geometry        - Pre-trained on Fusion360 Gallery
    checks             - Per-face complexity scoring (0-1)
  - 4-tier severity    - Normalized 0-1 scale
    + suggested action
     |                 |
     v                 v
Layer 3: Combiner + Report Generator
  - Normalize all scores to 0-1 scale
  - Fuse rule findings + ML scores
  - Per-body reports + combined summary
  - Mesh size field recommendations
  - Export report (JSON primary, PDF optional)
     |
     v
Interface Layer
  - CLI (primary): pipeline.py orchestrates, cli.py exposes commands
  - Web UI (optional): Streamlit + PyVista calls same pipeline
```

Why this separation:
- Pre-Check catches unreadable files immediately — no wasted processing.
- Layer 0 handles multi-body files transparently. Pipeline always operates on single body.
- Layer 1 is pure geometry extraction. Reusable for Phase 2 and 3.
- Layer 1.5 fixes topology before analysis — reduces false positives from fixable defects.
- Layer 2a (rules) works on day one. Layer 2b (ML) adds value incrementally. Either works alone.
- Layer 3 is source-agnostic. Adding new analysis methods = plugging into this layer.
- CLI-first ensures clean pipeline separation. Streamlit is a thin wrapper, not the core.
- `pipeline.py` is the single orchestrator — both CLI and UI call it.

## Tech Stack

| Component | Library | Why |
|-----------|---------|-----|
| STEP parsing | pythonocc-core + occwl (Autodesk AI Lab) | occwl provides clean Python API, compatible with BRepNet data format |
| File validation | OCC BRepCheck_Analyzer | Built-in global geometry validation |
| Auto-healing | OCC ShapeFix (ShapeFix_Shape, ShapeFix_Wire, ShapeFix_Face) | Built-in topology repair, no extra dependencies |
| Healed STEP export | OCC STEPControl_Writer | Export auto-healed geometry as new STEP file |
| Rule engine | Custom Python | Geometry heuristics, threshold checks |
| ML model | BRepNet (pre-trained) | Works directly on B-Rep topology from STEP. No lossy point cloud conversion. **Note: CC BY-NC-SA 4.0 license — non-commercial use only** |
| ML enhancement | UV-Net (optional) | Surface-level geometry learning, complements BRepNet |
| Mesh recommendations | pygmsh | Programmatic mesh generation with size field control |
| Mesh I/O | meshio | Universal mesh format conversion |
| CLI framework | Click or argparse | Primary interface for SimReady |
| 3D visualization | PyVista | 3D rendering with scalar overlays |
| Web UI (optional) | Streamlit | Thin wrapper over pipeline, not the core |
| Synthetic test data | CadQuery | Parametric shape generation for test cases |
| Training data (later) | Fusion360 Gallery Dataset (648 stars) | Real CAD models with segmentation labels |

## Assembly / Multi-Body Handling

Detection:
- After STEP import, check if `TopoDS_Shape` is a `Compound` or contains multiple `Solid` entities
- Count bodies using OCC `TopExp_Explorer` with `TopAbs_SOLID`

Behavior:
- **Single body** → run pipeline directly
- **Multiple bodies** → split into individual solids, run full pipeline (heal → analyze → report) per body

Report format for multi-body:
```
FILE: assembly.step (3 bodies detected)

BODY 1 / 3: Bracket_Main
  HEAL: 1 gap fixed
  HEALTH: 1 issue (thin wall at face 8)
  MESH: ~32,000 elements (2 refinement zones)
  COMPLEXITY: Medium

BODY 2 / 3: Mounting_Plate
  HEAL: No issues
  HEALTH: No issues
  MESH: ~8,000 elements
  COMPLEXITY: Low

BODY 3 / 3: Stiffener_Rib
  HEAL: No issues
  HEALTH: 2 issues (short edge, small fillet)
  MESH: ~12,000 elements (1 refinement zone)
  COMPLEXITY: Medium

OVERALL: 3 bodies, 3 issues total, ~52,000 elements
```

Scope limits (Phase 1):
- No contact analysis between bodies
- No symmetry detection across bodies
- No assembly-level checks (interference, clearance)
- Just individual body analysis, combined reporting

## Unit / Tolerance Handling

- Read unit information from STEP file header (AP203/AP214/AP242 all store this)
- Normalize all internal geometry to **millimeters** (standard for FEA)
- Log unit conversion in report: "Original units: inches → converted to mm"
- If unit info is missing/ambiguous, warn user and assume mm (most common in mechanical CAD)
- Read precision/tolerance from file, apply OCC's tolerance settings accordingly
- All rule thresholds defined in mm — work correctly regardless of input file units

## Auto-Healing (Layer 1.5)

What it does (topology repair):
- Gap stitching — close small gaps between adjacent faces using `ShapeFix_Shape`
- Wire repair — fix open/self-intersecting wires via `ShapeFix_Wire`
- Face fixes — correct face orientations, remove degenerate faces via `ShapeFix_Face`
- Tolerance tightening — normalize edge/vertex tolerances across the model
- Edge continuity — fix edges that don't connect properly

What it does NOT do (Phase 2 — defeaturing):
- Remove small fillets
- Fill small holes
- Suppress cosmetic features
- Simplify complex surfaces

Report output:
```
AUTO-HEAL SUMMARY:
  Issues found:     5
  Auto-fixed:       3
    - 2 gaps stitched (faces 12-13, faces 27-28)
    - 1 degenerate wire removed (edge 41)
  Remaining:        2
    - Non-manifold edge at edge 7 (requires manual fix)
    - Self-intersection at faces 15-16 (requires manual fix)
```

Healed geometry export:
- CLI: `simready analyze part.step --export-healed` → writes `part_healed.step`
- Web UI: "Download Healed STEP" button
- Uses OCC `STEPControl_Writer` to export the in-memory healed shape
- Original file never modified

Behavior:
- Runs automatically after parsing, before analysis
- Never modifies original file — works on in-memory copy
- All changes logged for transparency
- If healing fails on any item, continues with rest, flags failures
- Analysis runs on healed geometry (so rule engine doesn't re-flag already-fixed issues)

## Severity Taxonomy

4-tier severity system:

| Severity | Meaning | Action |
|----------|---------|--------|
| **Critical** | File cannot be read, no valid solid, or global geometry failure | Abort pipeline, reject input |
| **Major** | Topology or geometry defect that blocks meshing | Must fix before simulation |
| **Minor** | Small features or quality issues that degrade mesh but don't block it | Warning with suggestion, can proceed |
| **Info** | Model is clean in this area, or optimization suggestion | No action required |

## Rule Engine — Geometry Health Checks (11 checks + pre-validation)

**Pre-validation (before pipeline):**

| Check | Method | Severity | Suggested Action |
|-------|--------|----------|-----------------|
| File load failure | `STEPControl_Reader` status check | Critical | Reject input, ask user to repair STEP externally |
| Null/empty shape | `shape.IsNull()` after transfer | Critical | Reject input, file contains no geometry |
| Global geometry failure | OCC `BRepCheck_Analyzer` | Critical | Report specific OCC errors, abort |

**Rule engine checks (on parsed + healed geometry):**

| # | Check | Method | Threshold | Severity | Suggested Action |
|---|-------|--------|-----------|----------|-----------------|
| 1 | Thin walls | Face-pair distance comparison | < 2mm (configurable) | Major | Thicken wall or add support elements |
| 2 | Small features | Face/edge area vs total part size | < 1% of bounding box | Minor | Remove or enlarge feature |
| 3 | Sharp edges | Dihedral angle between adjacent faces | < 15 degrees | Minor | Add fillet or ignore if intentional |
| 4 | Small fillets | Fillet radius detection | < 1mm | Minor | Increase radius or remove fillet |
| 5 | Short edges | Edge length vs part size | < 0.5% of max dimension | Minor | Remove or merge edges |
| 6 | Non-manifold edges | Topological check (edge shared by >2 faces) | Any occurrence | Major | Merge faces or remove extra edges |
| 7 | Gaps/overlaps | Face adjacency analysis | Tolerance-based | Major | Fill gap or rebuild surface closure |
| 8 | Self-intersecting geometry | Boolean self-intersection test | Any occurrence | Major | Rebuild intersecting regions |
| 9 | Duplicate/overlapping faces | Face-pair coincidence detection | Within tolerance | Major | Remove duplicates or Boolean fuse |
| 10 | Face orientation / flipped normals | Normal consistency check via `BRepCheck_Analyzer` | Any inconsistency | Minor | Reorient faces (auto-heal may fix) |
| 11 | Degenerate faces / zero-length edges | `face.Area() <= 0` or `edge.Length() == 0` | Any occurrence | Major | Remove degenerate geometry |

All thresholds configurable by the user. Major checks (1, 6-9, 11) indicate geometry that blocks or severely degrades meshing. Minor checks (2-5, 10) are warnings with suggestions.

## Rule Engine — Mesh Recommendations

| Recommendation | Logic |
|----------------|-------|
| Global element size | Bounding box / smallest feature ratio |
| Fillet refinement | Element size = fillet radius / 3 |
| Hole edge refinement | 8-12 elements around circumference |
| Stress riser zones | High curvature = smaller elements |
| Flat/simple regions | Low curvature = larger elements |
| Estimated element count | Surface area / avg element size squared |

## Score Normalization & Fusion

Rule score normalization (per face):
- Each rule outputs binary (pass/fail) or continuous value
- Normalize to 0-1: `0.0` = no issue, `1.0` = worst violation
- Multiple rules on same face → take max score

ML score (per face):
- BRepNet outputs per-face complexity score, already 0-1 (softmax output)

Fusion logic:
| Rule Score | ML Score | Combined | Interpretation |
|-----------|----------|----------|----------------|
| High (>0.7) | High (>0.7) | Strong | Definite refinement zone |
| High (>0.7) | Low (<0.3) | Standard | Rule-based recommendation |
| Low (<0.3) | High (>0.7) | Suggested | "Area of interest" — ML sees complexity rules missed |
| Low (<0.3) | Low (<0.3) | None | No action needed |

Combined score formula:
```
combined = max(rule_score, ml_score) * 0.6 + min(rule_score, ml_score) * 0.4
```

Weights rule and ML agreement. When both agree → score near max. When they disagree → moderate score. Weights tunable later. Feeds directly into mesh density heatmap.

## Complexity Score

```
Low:    < 5 flagged features, no Major/Critical issues, < 50K estimated elements
Medium: 5-15 flagged features, or 50K-200K estimated elements
High:   > 15 flagged features, or Major/Critical issues present, or > 200K estimated elements
```

All thresholds configurable by the user.

## ML Layer — BRepNet Integration

Why BRepNet over PointNet:
- Works directly on B-Rep topology (faces, edges, coedges) — what STEP files contain natively
- Pre-trained weights available on Fusion360 Gallery Dataset
- occwl extracts data in the exact format BRepNet expects
- No lossy point cloud conversion needed

What ML adds over rules:
- Catches geometrically complex regions that don't match simple rule patterns
- Per-face continuous complexity score (0.0 simple to 1.0 complex) for smooth heatmap
- Gets smarter as you add training data later

Build timeline:
- Week 1: Rules only. ML interface exists but returns neutral scores (0.5).
- Week 2-3: Plug in BRepNet pre-trained weights. ML scores contribute to heatmap.

## Key GitHub Repos (Foundation)

Must-use:
- AutodeskAILab/occwl (84 stars) — STEP parsing, B-Rep extraction
- AutodeskAILab/BRepNet (222 stars) — ML on CAD topology
- tpaviot/pythonocc-core (1863 stars) — OpenCASCADE Python bindings
- nschloe/pygmsh (959 stars) — Programmatic meshing
- nschloe/meshio (2281 stars) — Mesh format I/O
- CadQuery/cadquery (Apache 2.0) — Synthetic test case generation

Study for reference:
- AutodeskAILab/UV-Net (183 stars) — Surface geometry learning
- AutodeskAILab/Fusion360GalleryDataset (648 stars) — Training data
- ranahanocka/MeshCNN (1725 stars) — CNN on mesh edges
- BRepMaster/3DModel-Processor (7 stars) — STEP to ML-ready pipeline
- Gwen1220/Deep-Learning-Based-Mesh-Quality-Prediction — Most directly relevant existing work
- spacether/pycalculix (185 stars) — Full Python FEA automation
- rdevaul/yapCAD (24 stars) — STEP validation script using OCC global checks (pyocc-validate.py)
- whjdark/AAGNet (15 stars) — STEP parsing + per-face point sampling example
- FlynnHHH/grabcad — GrabCAD model scraper (useful for building test datasets, Phase 2)

## Competitive Landscape

| Tool | What they do | SimReady's angle |
|------|-------------|-----------------|
| SimScale | Agentic AI for full simulation setup (cloud, proprietary) | Open-source, STEP-agnostic, no solver lock-in |
| Neural Concept | Geometric DL for performance prediction ($100M raised) | Similar ML tech but for pre-processing, not prediction |
| FeaGPT (Stuttgart/Exeter) | Natural language to FEA pipeline | Different scope — they generate geometry from text, we analyze existing |
| CADFEM | PyAnsys automation scripts (services) | Standalone tool, not Ansys-dependent |
| Altair HyperMesh | Industry-standard pre-processor with AI features | Commercial, expensive, not accessible to smaller teams |
| CADfix | Geometry healing and cleanup (commercial) | SimReady does healing + analysis + ML, open-source |

## Validation Strategy

Test data sources (3 tiers):

| Tier | Source | License | In Repo? | Purpose |
|------|--------|---------|----------|---------|
| Primary | SimJEB (GE Bracket Challenge, Harvard Dataverse) | ODC-By (open) | No — document links + download script | 381 brackets with FEA ground truth |
| Secondary | GrabCAD bracket models | GrabCAD ToS (free, non-commercial) | No — document model names + links | Automotive-relevant test cases |
| In-repo | Synthetic via CadQuery/OCC | MIT (our own) | Yes — `tests/data/` | 3-5 parametric shapes with known defects |

Synthetic test cases (committed to repo):

| Test Case | Known Defects | What It Validates |
|-----------|--------------|-------------------|
| `box_with_thin_wall.step` | One wall < 2mm | Thin wall detection |
| `plate_with_holes.step` | 3 holes (1 tiny), 2 fillets (1 small) | Small feature + fillet detection |
| `bracket_with_gap.step` | Intentional gap between two faces | Gap detection + auto-heal |
| `multi_body_assembly.step` | 2 solids in one file | Assembly splitter |
| `clean_bracket.step` | No defects | False positive check (should report zero issues) |

Success criteria (qualitative):
- For each SimJEB model tested, document: "SimReady found X, manual review found Y"
- Side-by-side comparison on 5-10 models tells portfolio story
- No hard % targets in Phase 1
- Target: zero false positives on clean models, catch all Critical issues

Performance targets:
- Simple parts (< 50 faces): < 10 seconds
- Medium parts (50-500 faces): < 30 seconds
- Complex parts (500+ faces): best effort, log time

## Target Test Part

- Primary: **Automotive mounting bracket** — bolt holes, fillets, sharp transitions, stress risers. Common FEA target, easy to source STEP files, demonstrates all 11 checks.
- Stretch: **Suspension control arm** — more complex geometry, mix of thick/thin sections. Attempt after bracket works.

Sources: SimJEB GE Bracket Challenge (open), GrabCAD engine mount brackets (local testing).

## Repo Structure (Reference)

For planner to scaffold — not created yet.

```
SimReady/
├─ simready/                  # core package
│   ├─ __init__.py
│   ├─ cli.py                 # Click/argparse CLI entry point (PRIMARY interface)
│   ├─ pipeline.py            # Orchestrator: validate → split → parse → heal → check → score → report
│   ├─ validator.py           # Pre-check: file load, null shape, BRepCheck_Analyzer
│   ├─ parser.py              # STEP/IGES loading, unit normalization
│   ├─ healer.py              # OCC ShapeFix auto-healing + STEP export
│   ├─ splitter.py            # Multi-body detection and splitting
│   ├─ checks/                # rule engine modules (one file per check)
│   │   ├─ __init__.py
│   │   ├─ thin_walls.py
│   │   ├─ small_features.py
│   │   ├─ sharp_edges.py
│   │   ├─ small_fillets.py
│   │   ├─ short_edges.py
│   │   ├─ non_manifold.py
│   │   ├─ gaps.py
│   │   ├─ self_intersection.py
│   │   ├─ duplicate_faces.py
│   │   ├─ face_orientation.py
│   │   └─ degenerate.py
│   ├─ ml/                    # ML layer
│   │   ├─ __init__.py
│   │   └─ brepnet.py         # BRepNet integration, returns 0-1 scores
│   ├─ combiner.py            # Score normalization + fusion
│   ├─ mesh_recommender.py    # Mesh size field recommendations
│   └─ report.py              # Report generation (JSON primary, PDF optional)
├─ ui/                        # Optional web UI (built on same pipeline)
│   ├─ app.py                 # Streamlit application
│   └─ viz.py                 # PyVista visualization helpers
├─ tests/
│   ├─ data/                  # Synthetic STEP test files
│   ├─ test_validator.py
│   ├─ test_parser.py
│   ├─ test_healer.py
│   ├─ test_checks.py
│   ├─ test_combiner.py
│   └─ test_splitter.py
├─ scripts/
│   └─ download_simjeb.py     # Script to fetch SimJEB test data
├─ docs/
│   └─ validation_results/    # Side-by-side comparison screenshots
├─ report_schema.json         # JSON schema for output report format
├─ environment.yml            # Conda environment (pythonocc needs conda)
├─ requirements.txt
├─ README.md
└─ LICENSE                    # MIT or Apache 2.0
```

## Future Phases (Not in Phase 1)

| Phase | What | Adds to SimReady |
|-------|------|-----------------|
| Phase 1.5 | Synthetic training data pipeline — parametric shapes, auto-mesh, auto-solve, label | Improves ML layer accuracy |
| Phase 2 | Defeaturing suggestions + auto-defeaturing via healing — flag and optionally remove small features | Builds on geometry analysis and healing from Phase 1 |
| Phase 2 | Sliver face detection (long thin faces near zero width) | More precise than small-feature check, useful for defeaturing |
| Phase 2 | Wall thickness uniformity analysis (ray casting / offset surfaces) | Distribution-level thickness analysis |
| Phase 2 | GrabCAD scraper integration (FlynnHHH/grabcad) | Automate test model collection |
| Phase 3 | Boundary condition suggestions — identify fixed supports, load faces, symmetry planes | Hardest — needs engineering intent understanding |
| Future | Thermal/CFD support | Different meshing strategies per physics type |
| Future | React frontend upgrade | Polished UI, better 3D interaction |
| Future | REST API | Enable integration with external tools |

## Separate Project (Not SimReady)

Project 2: Surrogate prediction tool (Neural Concept style)
- Train on existing FEM results, predict stress/displacement fields on new geometry
- Completely separate codebase and scope
- Together with SimReady, tells a complete portfolio story: pre-processing + prediction

## Output Report Format

### CLI Output (JSON — primary)
```json
{
  "file": "bracket.step",
  "status": "NeedsCleaning",
  "units": {"original": "inches", "normalized": "mm"},
  "bodies": 1,
  "heal_summary": {
    "issues_found": 3,
    "auto_fixed": 2,
    "remaining": 1,
    "details": [
      {"type": "GapStitched", "faces": [12, 13]},
      {"type": "DegenerateWireRemoved", "edge": 41}
    ]
  },
  "issues": [
    {"check": "ThinWall", "severity": "Major", "face_id": 23,
     "detail": "Wall thickness 0.8 mm < 2.0 mm threshold",
     "suggestion": "Thicken wall or add support elements"},
    {"check": "SmallFillet", "severity": "Minor", "face_id": 7,
     "detail": "Fillet radius 0.3 mm < 1.0 mm threshold",
     "suggestion": "Increase radius or remove fillet"}
  ],
  "mesh_recommendation": {
    "global_element_size_mm": 3.5,
    "refinement_zones": 2,
    "estimated_elements": 45000
  },
  "complexity": "Medium",
  "ml_scores": {"available": false, "reason": "BRepNet not loaded"},
  "healed_file": null
}
```

Schema defined in `report_schema.json` at repo root.

### Web UI Output (visual)
One screen, not a document. Expandable sections:

```
[3D model with colored regions]

AUTO-HEAL:        3 issues fixed, 2 remaining
GEOMETRY HEALTH:  2 issues found
MESH SUGGESTION:  ~45,000 elements (3 refinement zones)
COMPLEXITY:       Medium

[Expandable details below]
[Download Healed STEP]  [Export JSON]  [Export PDF]
```

Short, visual, actionable.

## Public Repo

- Name: SimReady
- Public from day one on GitHub
- Open-source (MIT or Apache 2.0)
- README should explain the problem, show a demo screenshot/gif, and have clear install instructions
- Deployment: GitHub repo + conda environment.yml + requirements.txt only. No Docker/cloud/pip packaging in Phase 1.

## Decision Log

Decisions made during brainstorming:

1. Structural/stress analysis first (not thermal, CFD, or multi-physics)
2. STEP/IGES input (not locked to any CAD tool, avoided Siemens NX)
3. Hybrid approach: rule-based + ML (not pure rules, not pure ML)
4. BRepNet as ML backbone (not PointNet — avoids lossy point cloud conversion)
5. Pre-trained weights first, custom training data later
6. Streamlit + PyVista frontend (not React — focus on engineering logic, not UI polish)
7. Surrogate prediction is a separate project, not part of SimReady
8. React frontend considered for future upgrade — revisit after Phase 1
9. Auto-healing added to pipeline — OCC ShapeFix, topology-only in Phase 1, defeaturing in Phase 2
10. Assembly handling — per-body split and individual analysis, no contact/interference checks
11. Self-intersection and duplicate face checks added (both Critical severity)
12. Severity-to-action mapping — every rule outputs suggested fix action
13. Score normalization — both rules and ML normalized to 0-1, fused via weighted formula
14. Unit normalization — all geometry converted to mm internally
15. Deployment — GitHub repo + conda environment.yml only, no Docker/cloud/pip packaging
16. Test data — SimJEB (primary, open license), GrabCAD (local only), synthetic CadQuery (in-repo)
17. Success metrics — qualitative side-by-side comparison, no hard % targets in Phase 1
18. Target test part — automotive mounting bracket, control arm as stretch goal
19. Decorative detail detection — skipped for Phase 1
20. CLI-first architecture — CLI is primary interface, Streamlit is optional wrapper on same pipeline
21. File load validation added as pre-pipeline check (Critical abort on failure)
22. Face orientation and degenerate geometry checks added (checks #10, #11)
23. 4-tier severity system adopted: Critical / Major / Minor / Info (replacing Critical / High / Medium)
24. Healed STEP export via `--export-healed` CLI flag and UI button
25. JSON report schema (`report_schema.json`) added to repo
26. BRepNet CC BY-NC-SA 4.0 license acknowledged — non-commercial use only, not bundled in MIT repo
27. OCC `BRepCheck_Analyzer` used as global pre-scan before individual rule checks
28. Sliver faces, wall thickness uniformity, GrabCAD scraper deferred to Phase 2
29. Undercut detection and REST API skipped (different domain / no demand)

## Known Risks

1. BRepNet pre-trained weights may not directly apply to the face complexity scoring task — may need a small fine-tuning step
2. pythonocc installation can be tricky on Windows (conda recommended)
3. STEP file variability — different CAD tools export slightly different STEP flavors
4. PyVista in Streamlit has known rendering limitations — may need stpyvista wrapper
5. No large-scale "CAD + FEM results" public dataset exists — limits ML validation
6. Auto-heal may over-fix — closing a gap that was intentional (e.g., split line). Mitigated by before/after report transparency.
7. Multi-body splitting may lose assembly context (mates, constraints). Acceptable for Phase 1 scope.
8. Synthetic test cases may not represent real-world CAD complexity. Mitigated by also testing on SimJEB/GrabCAD models.
9. BRepNet license (CC BY-NC-SA 4.0) conflicts with MIT/Apache repo license. Mitigated: weights not bundled in repo, used for personal demo only. Core rule engine works independently under MIT.
10. OCC `BRepCheck_Analyzer` may flag issues that are tolerable for some use cases (false positives on complex geometry). Mitigated: pre-scan results are informational, individual rules make the final call.
