# OCC Hang Diagnosis — per-stage attribution

**Date:** 2026-07-19 · **Tool:** `scripts/diagnose_occ_hang.py` · **Backlog:** `analyze-file-occ-hang-per-check` (S2)
**Subjects:** the 4 parts `analyze_file` "hung" on during the real-CAD eval (`real_eval.md` §3). Control part `33125T73` (34 f): all stages < 0.1 s (ml ~3 s warm).

Per-(part, stage) spawn-subprocess probes, hard timeout 90 s.
Cells: seconds, **TIMEOUT** (culprit), blocked (prereq hung), or err.

| Stage | 1483N211 | 43505K359 | 44685K321 | 4519N12 |
|---|---|---|---|---|
| load | 14.44 | 0.72 | 0.61 | 1.57 |
| validate | 0.08 | 0.06 | 0.15 | 0.20 |
| heal | 0.33 | 0.22 | 0.45 | 0.73 |
| parse | 0.00 | 0.00 | 0.00 | 0.01 |
| check_degenerate_geometry | 0.02 | 0.01 | 0.01 | 0.04 |
| check_non_manifold_edges | 0.01 | 0.00 | 0.00 | 0.01 |
| check_open_boundaries | 0.01 | 0.00 | 0.00 | 0.01 |
| check_short_edges | 0.02 | 0.01 | 0.01 | 0.04 |
| check_thin_walls | 0.00 | 0.00 | 0.00 | 0.00 |
| check_small_features | 0.14 | 0.04 | 0.06 | 0.39 |
| check_small_fillets | 0.01 | 0.00 | 0.00 | 0.02 |
| check_duplicate_body_heuristic | 0.00 | 0.00 | 0.00 | 0.01 |
| check_thin_solid | 0.00 | 0.00 | 0.00 | 0.01 |
| check_duplicate_face_heuristic | 0.01 | 0.00 | 0.00 | 0.01 |
| check_orientation_nuance | 0.00 | 0.00 | 0.00 | 0.00 |
| check_sharp_edges | 0.01 | 0.00 | 0.00 | 0.01 |
| check_self_intersection | 0.00 | **TIMEOUT** | **TIMEOUT** | 0.00 |
| graph | 0.29 | 0.09 | 0.09 | 0.80 |
| ml | 2.95 | 3.84 | 3.12 | 3.12 |

## Findings

1. **The only true OCC hang is `check_self_intersection`**, and only on the two 58-face flanges (`43505K359` cast, `44685K321` forged). Both pass the 150-face limit (58 < 150), so BOPAlgo_ArgumentAnalyzer actually ran — and did not return within 90 s. Surface-type probe: both flanges carry 3–4 **B-spline faces** (plus 29–31 cones); every part that analyzed fine in the eval (`33125T73`, `3710T9`, `9734K17`, `9804K64`, `4519N11`, `1483N115`) has **zero** freeform faces. Face count is the wrong hang predictor; freeform-surface presence is the separating variable on this set.

2. **The in-check 30 s thread watchdog demonstrably does not fire.** The probe timed out at 90 s — three times its cap. Mechanism: pythonocc does not release the GIL during the long C++ `Perform()` call, so the watchdog's `join(timeout=30)` cannot even wake. Every thread-based timeout in the codebase (including `analyze_file`'s own 120 s guard) is inert while OCC C++ runs. This is why the original eval once lost 12 h to a "guarded" call. Hard kill = subprocess only (`analyze_file_safe`).

3. **Two of the four "hangs" were never hangs.** `1483N211` (267 f) and `4519N12` (578 f) complete every stage in ≤ 14.4 s / ≤ 1.6 s respectively (self-intersection face-limit skip covers 4519N12 at 578 f). Their eval kills were budget artifacts: the eval's 60 s cap includes ~20–25 s cold torch import in each spawn child plus a 14.4 s STEP load (1483N211) — cumulative, not stuck. `real_eval.md` §3's "four parts hung" claim is corrected accordingly.

## Fixes shipped (same session)

- `check_self_intersection`: freeform-face precheck (`SELF_INTERSECTION_FREEFORM_LIMIT = 0`) — both flanges now skip in **0.001 s** with a Minor `SelfIntersectionSkipped` finding instead of hanging. Watchdog docstring rewritten to state its best-effort-only reality.
- `simready.pipeline.analyze_file_safe`: spawn-subprocess + `terminate()` wrapper with the standard `AnalysisTimeout` report; wired into the copilot `analyze_geometry` tool, both Streamlit entry points, and the CLI. The in-process `analyze_file` remains for batch callers that manage their own guards.
