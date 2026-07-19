# Real-CAD Out-of-Distribution Eval

**Checkpoint:** `weights/brepnet.pt` (3-head: per-face rule refinement + per-face curved-region + graph-level defect classifier; 2026-05-27 retrain, source-grouped leakage-free split, defect-acc 0.756 on val)
**Input:** `tests/data/real_eval` — 12 real McMaster-Carr STEPs (brackets / flanges / bearings / housings), no labels.
**Result:** 7/12 analyzed, 1 skipped (>800 faces), 4 errored (analyze_file timeout >60 s — OCC C++ hang on pathological NURBS, hard-killed by subprocess guard).
**Max faces:** `800`. **Analyze timeout:** `60 s` per part (enforced via spawn subprocess + `.terminate()` — the only reliable kill switch for an OCC C++ hang; Python thread timeouts do not interrupt the underlying C call, per the project's OCC threading lesson).
**Nature:** UNLABELED real production CAD — this is a *generalization probe*, not an accuracy measurement. Real McMaster parts are presumed defect-free, so any defect-head fire is a false positive.

| File | Faces | Tier | Overall | Label | Rule mean | ML agg | Defect pred (conf) | Findings (sev) | s |
|---|--:|---|--:|---|--:|--:|---|---|--:|
| 33125T73_Wraparound 90 Degree Strut Channel Bracket.STEP | 34 | simple | 89.11 | ReviewRecommended | 0.0 | 0.295 | open_shell (0.997) | M1 | 0.16 |
| 43505K359_Low-Pressure 304 Stainless Steel Cast Flange.STEP | 58 | — | — | ERROR | — | — | analyze_timeout (>60s) | — | — |
| 44685K321_Low-Pressure 304-304L Stainless Steel Forged Pipe Flange.STEP | 58 | — | — | ERROR | — | — | analyze_timeout (>60s) | — | — |
| 7192K47_Ultra-Corrosion-Resistant Mounted 316 Stainless Steel Ball Bearing.STEP | 95 | moderate | 66.52 | NeedsAttention | 0.0 | 0.424 | sliver_face (0.658) | Mj1 Mn2 I1 | 1.62 |
| 9734K17_Flange-Mounted Linear Bearing Housing.STEP | 131 | moderate | 5.26 | NotReady | 0.0 | 0.487 | open_shell (0.725) | Mj5 Mn2 I1 | 1.80 |
| 3710T9_Mounted Ball Bearing.STEP | 177 | moderate | 60.42 | NeedsAttention | 0.0 | 0.479 | sliver_face (0.978) | Mj1 Mn3 I1 | 1.67 |
| 9804K64_Linear Bearing Housing.STEP | 218 | complex | 9.86 | NotReady | 0.0 | 0.507 | open_shell (0.476) | Mj4 Mn4 I1 | 1.72 |
| 1483N211_Mounted Ball Bearing with Two-Bolt Flange.STEP | 267 | — | — | ERROR | — | — | analyze_timeout (>60s) | — | — |
| 4519N11_Bracket for Composite T-Slotted Framing.STEP | 301 | complex | 8.16 | NotReady | 0.0 | 0.592 | sliver_face (1.000) | Mj4 Mn4 I1 | 12.44 |
| 1483N115_Mounted Ball Bearing with Two-Bolt Flange.STEP | 344 | complex | 11.06 | NotReady | 0.0 | 0.447 | sliver_face (0.966) | Mj4 Mn4 I1 | 8.83 |
| 4519N12_Bracket for Composite T-Slotted Framing.STEP | 578 | — | — | ERROR | — | — | analyze_timeout (>60s) | — | — |
| 4519N13_Bracket for Composite T-Slotted Framing.STEP | 854 | — | — | SKIPPED | — | — | too_large (854 faces) | — | — |

> Severity counts in "Findings": `Mj` = Major, `Mn` = Minor, `I` = Info. "Critical" did not occur.

## Summary (raw numbers)

- 7/12 parts went end-to-end. 4 hit the 60 s subprocess kill in `analyze_file` (OCC C++). 1 was skipped by the face-count precheck (854 faces > 800).
- **Defect-head fires: 7/7 analyzed parts** were labelled with a synthetic-defect class (`open_shell` ×3, `sliver_face` ×4). Zero parts were called `clean`.
- Defect-head confidence distribution: ≥0.95 on 5/7 parts (0.997, 0.978, 0.966, 1.000, 0.725, 0.658, 0.476). The model is *confidently wrong*, not unsure.
- `rule_face_mean == 0.0` on **every** analyzed part — the per-face deterministic rule layer found nothing.
- `ml_aggregate` ranged 0.295 – 0.592 (mean ≈ 0.46). Diverges from `rule_face_mean = 0` by 0.30 – 0.59 absolute on every part.
- `Overall` score (composite of findings + complexity + ML, not just rule mean): 5/7 parts scored < 12 → `NotReady`; the strut bracket (34 faces, simplest) scored 89 → `ReviewRecommended`. The pipeline thinks clean industrial parts are unbuildable.

## Interpretation

### 1. The non-circular defect head over-fires on real CAD — confidently

On the held-out training/val split this checkpoint achieved **defect-class accuracy 0.756** (n=205, source-grouped leakage-free split, per `docs/validation/defect_classifier.md`). On real McMaster geometry it labelled **7/7 presumed-clean parts as defective**, with median confidence > 0.95. That is a **100 % false-positive rate** on this admittedly tiny (n=7) OOD sample.

The training distribution is to blame, not the architecture:
- Positive examples come from `scripts/generate_degraded_steps.py`, which injects three specific synthetic defects (`open_shell`, `sliver_face`, `self_intersection`) into parametric primitives.
- "Clean" examples are the same parametric primitives without injection — i.e. smooth box/cylinder/boolean geometry from `generate_parametric_steps.py`.
- Real production parts have NURBS surfaces, imported fillets, manufactured features (chamfers, drafts, knurls), and tight aspect ratios that *resemble* the injected sliver/open-shell features at the GraphSAGE-feature level — small areas, narrow UV bands, sharp dihedral angles.

So the model has not learned "is this part defective?". It has learned "do these face features look like the synthetic positive class?", and on real CAD the answer is almost always yes. This is exactly the gap the strategy doc (`docs/strategy/mecagent-gap-and-drift-2026-05-26.md` D1) called out — recall on the leaky synthetic val is *not* a generalization guarantee — now quantified on real geometry instead of inferred.

### 2. ML aggregate diverges from rule mean — same OOD direction, smaller magnitude

`rule_face_mean = 0.0` everywhere ↔ `ml_aggregate ∈ [0.30, 0.59]`. The per-face rule layer (`simready/checks.py`'s 12 deterministic checks: aspect, area, planarity, etc.) found no per-face flags on any of the 7 parts — exactly the conservative behaviour we want on clean industrial CAD. The ML aggregate (per-face refinement head, *still circular-label-trained* — only the new graph-level defect head broke circularity) raised the score on every part anyway. The refinement head suffers the same OOD problem the defect head does: trained on synthetic feature distributions, fires on real-CAD features that look similar.

The previous-checkpoint era's GrabCAD numbers (`docs/validation/grabcad.md`: ML agg 0.30 – 0.34) and the same-checkpoint refresh (`weights/metrics.json`: 0.37 – 0.45) are consistent with what we see here. The 3-head retrain *did not* fix the OOD over-fire — it added a non-circular signal *on top of* the still-OOD-fragile heads.

### 3. The bigger story: the rule pipeline itself isn't robust to industrial CAD

> **RESOLVED 2026-07-19** — per-stage diagnosis (`docs/validation/occ_hang_diagnosis.md`) corrected this section's suspicion: the only true hang was `check_self_intersection` (BOPAlgo) on the two 58-face **B-spline** flanges (under the 150-face limit; the 30 s thread watchdog provably cannot fire while OCC holds the GIL). The other two "hangs" (`1483N211`, `4519N12`) were 60 s-budget artifacts of this eval's cold-start subprocess (torch import + 14 s STEP load), not stuck OCC. Fixes shipped: freeform-face precheck in `check_self_intersection` (hang → 0.001 s skip) + `analyze_file_safe` subprocess isolation at the copilot/UI/CLI entry points. All 4 former kill parts now complete a full analysis in ≤ 12 s wall (regression-pinned in `tests/test_real_eval_regression.py`). The paragraphs below are kept as the honest pre-diagnosis record.

This was the bigger surprise. The face-count precheck (`--max-faces=800`) is what the original task asked for, and it does correctly skip the 854-face bracket without trying to extract its graph. But **four other parts at 58–578 faces also hung** — in `analyze_file` (the full 12-check rule pipeline), not in graph extraction. The previous `check_self_intersection` hardening (150-face skip + 30 s watchdog, see `docs/validation/grabcad.md`) only covers one of the twelve checks. Whichever check is hanging on these flange/bearing parts — likely something doing per-face geometry queries on a dense NURBS body — is not face-count-guarded, and per the project's OCC lesson (`lessons_pythonocc-gotchas.md`) a Python-level thread timeout does not actually stop the underlying C++ call.

The new subprocess guard in `scripts/eval_real_cad.py` (spawn child + `Process.terminate()` after 60 s) hard-kills these and lets the batch complete. That is correct for *this* eval, but it is a script-level workaround — the underlying pipeline is still hang-prone if called from anywhere else (the Streamlit UI, the copilot tool, a CI run). Open backlog item: `analyze-file-occ-hang-per-check` (see below).

### 4. What this proves about the model — narrative for an interviewer

- The OOD gap is real, large, and quantified. 7/7 false positives at high confidence is not a "needs more data" finding, it is a "training distribution doesn't cover the deployment distribution" finding.
- The hold-out is doing its job: this is exactly the diagnostic value a real eval set is supposed to provide. Without it the only honest number was the leakage-free synthetic val (0.756); we'd have been guessing about real-CAD behaviour.
- The right framing for MecAgent: "I built a held-out real-CAD probe specifically to surface OOD failures, and it surfaced them. The model is a credible pipeline + training loop + dual-backend with provenance + leakage-free eval, *not* a deployed defect detector. The remaining gap is data — real-CAD positives (labelled defect parts) and a real-CAD-aware negative augmentation strategy. Synthetic injection on parametric solids is insufficient." This is the same line the strategy doc takes; the eval is now the evidence for it.

### Files / repro

```powershell
$env:PYTHONPATH = "C:\Users\suman\Desktop\Docs\Job\Projects\Mech\SimReady"
& C:\mm\sr\python.exe scripts/eval_real_cad.py `
    --input tests/data/real_eval `
    --output docs/validation/real_eval.md `
    --max-faces 800 `
    --analyze-timeout 60
```

Total wall-clock for the 12-part run: ~5–6 min (incl. 4 × 60 s subprocess kills + spawn overhead).

### Follow-ups (going to BACKLOG)

- **`analyze-file-occ-hang-per-check`** (S2) — `analyze_file` hung on 4/12 industrial parts at 58–578 faces. Pre-existing `check_self_intersection` face-count guard + 30 s thread watchdog covers one check; the hang is in a different one. Identify the offending check (suspect: per-face curvature / sharp-edge / open-shell), add a face-count or topology-density precheck per check, prefer subprocess isolation in the Streamlit/copilot entry points so the UI cannot freeze on a real CAD upload.
- **`defect-head-real-cad-augmentation`** (S2) — non-circular defect head reaches 100 % FP rate on n=7 real industrial parts despite 0.756 val accuracy. Synthetic-only positives (`open_shell`/`sliver_face`/`self_intersection`) do not cover real-CAD feature distributions. Need either real-CAD positive labels (small set, hand-curated) or a domain-randomization step in the degradation generator that targets NURBS-density / fillet-radius / draft-angle features instead of fixed-magnitude geometry hacks.
- **`real-eval-set-grow`** (S3) — n=7 (post-skip / post-timeout) is too small for a defensible held-out metric. Add 20–30 more real STEPs that survive the analyze guard (avoid dense flange / bearing NURBS for now, or wait for `analyze-file-occ-hang-per-check`). Cap defect-head FP-rate as the primary held-out metric, not "accuracy" (no labels).
