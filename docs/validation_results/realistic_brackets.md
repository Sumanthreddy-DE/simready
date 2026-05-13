# Realistic Brackets Validation (Synthetic Harder Fixtures)

**Purpose:** Sanity-gate the SimReady pipeline on fixtures topologically harder than the parametric training set, before bringing in real GrabCAD STEPs. Five single-body solids generated via `scripts/generate_realistic_brackets.py` using pythonocc primitives, boolean ops, fillets, and chamfers.

**Caveat:** These are still synthetic. Real-world CAD validation (GrabCAD / SimJEB / Fusion 360 Gallery) lives in a separate doc. Use this as a "doesn't catastrophically misjudge" smoke check.

**Pipeline:** commit `66e5123`, BRepSAGE multitask checkpoint (`weights/brepnet.pt`), trained on 500 parametric STEPs.

## Results

| Fixture | Faces | Edges | Solids | Major | Minor | Overall | Label | Rule mean | Combined mean | ML agg | Tier | Elapsed |
|---------|------:|------:|-------:|------:|------:|--------:|-------|----------:|--------------:|-------:|------|--------:|
| boxed_beam_with_holes | 20 | 96 | 1 | 0 | 2 | 85.9 | ReviewRecommended | 0.607 | 0.249 | 0.204 | simple | 2.44s |
| ribbed_plate | 24 | 108 | 1 | 0 | 1 | 81.9 | ReviewRecommended | 0.589 | 0.508 | 0.653 | simple | 0.09s |
| l_bracket_with_fillet | 16 | 66 | 1 | 0 | 1 | 90.5 | SimulationReady | 0.518 | 0.181 | 0.227 | simple | 0.08s |
| t_junction | 12 | 52 | 1 | 0 | 1 | 90.8 | SimulationReady | 0.000 | 0.127 | 0.212 | simple | 0.06s |
| complex_bracket | 19 | 84 | 1 | 0 | 1 | 90.5 | SimulationReady | 0.518 | 0.172 | 0.224 | simple | 0.08s |

## Findings detail

- **boxed_beam_with_holes** — `SmallFeatures` (Minor), `SmallFilletsOrHoles` (Minor). Expected: 4 × 3 mm holes are small relative to the 120 × 40 × 40 outer envelope; the inner hollow cavity wall contributes more small faces.
- **ribbed_plate** — `SmallFeatures` (Minor). 3 narrow ribs trip the small-feature heuristic; ML aggregate is the highest of the batch (0.653) because ribbed topology has more high-degree faces.
- **l_bracket_with_fillet** — `SmallFeatures` (Minor). The 3 mm fillet at the inside corner counts as a small feature relative to the 70 × 60 envelope; correctly flagged.
- **t_junction** — `SmallFeatures` (Minor). Rule mean is 0 (no per-face rule scores fire); ML still picks up junction faces as mildly complex. No findings beyond the small-feature heuristic — pipeline correctly treats this as clean.
- **complex_bracket** — `SmallFeatures` (Minor). Same as `l_bracket_with_fillet` plus three mounting holes and a chamfer; pipeline still rates it `SimulationReady`.

## Pipeline behaviour gate — pass

- ✅ No false-positive `SelfIntersection` on any clean solid (regression of bug fix `ec4f33a`).
- ✅ No Critical findings on well-formed geometry.
- ✅ Score range 81.9–90.8 makes sense given Minor-only findings.
- ✅ `rule_face_mean` is a real [0,1] mean, not a count (regression of bug fix `ec4f33a`).
- ✅ BRepSAGE checkpoint engages on all five fixtures (`weights_loaded=True`).
- ✅ `complexity_tier=simple` on all (face_count ≤ 50) — sensible.
- ✅ Per-face index union has exactly `face_count` entries (regression of bug fix `ec4f33a`).
- ✅ Worst case elapsed is 2.44 s (boxed beam with 4 boolean cuts); rest under 0.1 s. Well under the 120 s pipeline timeout.

## What this does NOT prove

- Held-out generalization on real CAD topology (open shells, complex assemblies, BSpline-heavy parts).
- Behaviour on geometry the pipeline currently rejects (Critical findings) — none in this batch.
- BRepSAGE recall on real bracket faces that need refinement — earlier eval on the original smoke fixtures showed precision 1.0 but recall 0.23.

## Next gate

Add 3 real GrabCAD STEPs to `tests/data/grabcad/` (instructions in `scripts/download_grabcad_samples.py`). Re-run pipeline. Compare against this baseline to spot real-world deltas.
