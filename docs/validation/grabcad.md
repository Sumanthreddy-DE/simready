# Real-World CAD Validation (GrabCAD)

**Purpose:** First real-world gate for SimReady. Three GrabCAD STEPs of increasing complexity, run through the same pipeline used for synthetic fixtures.

> **Refreshed 2026-05-27 to the 3-head leakage-free checkpoint (`a29e150`).** Model-dependent numbers below (Overall, ML aggregate, latency) are from `weights/metrics.json`. Rule-layer findings (severity counts, edges/solids, rule mean) are model-independent and carry over unchanged from the original 2-head run. Canonical metric set: `weights/metrics.json`.

**Pipeline:** post-merge `66e5123` + self-intersection guard; numbers refreshed against the 3-head retrain (`a29e150`). BRepSAGE checkpoint (`weights/brepnet.pt`) now trained on 1100 graphs (500 parametric + 600 degraded-synth) with refinement + complexity + non-circular defect heads. Heuristic backend used when `weights/brepnet.pt` is absent.

**Inputs (placed in `tests/data/grabcad/`):**
- `bracket_simple.STEP` — 198 KB
- `housing_moderate.stp` — 202 KB
- `manifold_complex.STEP` — 1.8 MB

## Results

| Fixture | Faces | Edges | Solids | Critical | Major | Minor | Info | Overall | Label | Tier | Rule mean | ML agg | Elapsed |
|---------|------:|------:|-------:|---------:|------:|------:|-----:|--------:|-------|------|----------:|-------:|--------:|
| bracket_simple | 87 | 432 | 1 | 0 | 3 | 2 | 0 | 37.5 | NotReady | moderate | 0.667 | 0.373 | 7.45 s |
| housing_moderate | 107 | 572 | 1 | 0 | 3 | 2 | 0 | 36.6 | NotReady | moderate | 0.722 | 0.418 | 2.22 s |
| manifold_complex | 161 | 912 | 1 | 0 | 1 | 2 | 1 | 61.0 | NeedsAttention | moderate | 0.882 | 0.449 | 2.87 s |

All three: `validation.is_valid=True`, `heal_applied=True`, `BRepSAGE` 3-head checkpoint loaded. Model-dependent cells (Overall, ML agg, Elapsed) are from the 3-head leakage-free retrain (`weights/metrics.json`, `a29e150`); geometry/rule cells (Faces, Edges, Solids, severity counts, Rule mean) are model-independent and carry over from the original run. The earlier `Combined mean` column is dropped — `weights/metrics.json` does not capture it for the 3-head run.

## Findings detail

### bracket_simple (87 faces)
- **Major** `DegenerateEdges` — 8 zero-length or collapsed edges
- **Major** `OpenBoundaries` — 8 open boundary edges (shell not watertight)
- **Major** `DegenerateTopology` — 8 degenerated edges per OCC
- **Minor** `SmallFeatures` — 62 small faces, 272 short local edges relative to part scale
- **Minor** `SmallFilletsOrHoles` — 42 cylindrical faces with radius below 9.0

### housing_moderate (107 faces)
- **Major** `DegenerateEdges` — 8 zero-length edges
- **Major** `OpenBoundaries` — 8 open boundary edges
- **Major** `DegenerateTopology` — 8 degenerated edges per OCC
- **Minor** `SmallFeatures` — 68 small faces, 420 short edges
- **Minor** `SmallFilletsOrHoles` — 36 small cylindrical faces

### manifold_complex (161 faces)
- **Major** `ShortEdges` — 144 edges shorter than 0.778 units
- **Minor** `SmallFeatures` — 144 small faces, 840 short local edges
- **Minor** `SmallFilletsOrHoles` — 73 cylindrical faces with radius below 4.67
- **Info** `SelfIntersectionSkipped` — 161 faces exceeds `SELF_INTERSECTION_FACE_LIMIT` (150). See "Pipeline hardening" below.

## Pipeline behaviour gate — pass with one new finding

- ✅ Loads all 3 real STEPs, none crash
- ✅ Validation passes, healing engages on all 3
- ✅ Scores reflect real degradation: 38–69 (real CAD imports have artifacts; synthetic fixtures all scored 81–95)
- ✅ BRepSAGE checkpoint engages on every fixture
- ✅ Real findings (DegenerateEdges, OpenBoundaries) surface — pipeline catches what synthetic data never produced
- ✅ `rule_face_mean` is a real [0,1] mean (regression of `ec4f33a`)
- ✅ `complexity_tier=moderate` for all three (face_count 87/107/161) — confidence "medium" is honest
- ⚠️ **`SelfIntersectionSkipped` on 161-face manifold** — BOPAlgo_ArgumentAnalyzer hung > 10 minutes on this part. New guard skips with an Info finding above 150 faces. See "Pipeline hardening" section.

## Pipeline hardening (added during this run)

`check_self_intersection` now has two safety guards:

1. **Face-count limit** `SELF_INTERSECTION_FACE_LIMIT = 150`. Above this, the check emits an Info `SelfIntersectionSkipped` finding and returns immediately. Empirically, BOPAlgo self-intersection scales badly with face count and is impractical on real CAD beyond a few hundred faces.
2. **30-second watchdog**. The analyzer runs in a daemon thread; the main thread joins with `SELF_INTERSECTION_TIMEOUT_SECONDS = 30`. On timeout, an Info `SelfIntersectionTimeout` finding is emitted and the analyzer thread continues in the background (daemon, dies on process exit).

Without these guards the manifold_complex run hung past 10 minutes; with them the same run completes in 6.3 seconds.

Regression test: `test_self_intersection_skipped_when_face_count_exceeds_limit` in `tests/test_pipeline.py`.

## Observations on the BRepSAGE learned model

Across all three fixtures the ML aggregate sits in 0.37–0.45 (up from 0.30–0.34 on the old 2-head checkpoint). The model stays consistently more conservative than rules (rule_mean 0.67–0.88 vs ML 0.37–0.45). The refinement head's val recall is **0.487** on a leakage-free source-grouped split — the 0.870 quoted in earlier docs was a leaky random split (see `weights/metrics.json` + `docs/validation/defect_classifier.md`). The new non-circular graph-level defect head reaches **0.756** val accuracy. The persistent gap on these GrabCAD parts is consistent with the honest caveat: synthetic parametric solids under-represent real CAD with open-shell artifacts, dense small-feature fields, and high face-density manifolds.

This is the diagnostic gate the validation step exists to surface. Done since: 600 augmented-with-defect synthetics were mixed into training (now 1100 graphs) and the model retrained on a leakage-free split (`a29e150`). Held-out fixtures recall lifted 0.23 → 0.69; the real-CAD gap above remains, motivating `real-cad-eval-set` (held-out real STEPs as the next generalization probe).

## What this proves (and what it does not)

Proves:
- Pipeline does not crash on real CAD across an order-of-magnitude size spread (87 → 161 faces).
- Rule layer catches real-world artifacts (DegenerateEdges, OpenBoundaries) that the parametric set never produces.
- Healing engages but does not fully repair these specific defects — useful signal for users.
- New self-intersection guards keep the pipeline responsive on large parts.

Does not prove:
- BRepSAGE generalizes well to real CAD complexity profiles (it doesn't, per the consistent low ML aggregate; recall is likely poor on real bracket faces that need refinement).
- Pipeline behaves correctly on assemblies (multi-part STEPs) — these were excluded by request.
- Behaviour on CAD with thousands of faces (everything in this batch is under 200 faces).

## Next gates

1. Larger real CAD: a 500-face and a 1500-face part to exercise the `complex` and `very_complex` tiers.
2. Assembly STEPs (multi-solid) to validate body-splitting and per-body reporting.
3. Real-CAD-augmented training: mix in a few hundred GrabCAD-style parts (or auto-degrade parametric solids: introduce zero-length edges, small open shells, dense small features) to lift BRepSAGE recall.
