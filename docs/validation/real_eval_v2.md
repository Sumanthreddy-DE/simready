# Real-CAD Out-of-Distribution Eval

**Checkpoint:** `weights\brepnet.pt`  
**Input:** `tests\data\real_eval` (11/12 analyzed, 1 skipped, 0 errored)  
**Max faces:** `800` (parts above this are skipped, not extracted/analyzed)  
**Nature:** UNLABELED real McMaster-Carr-style parts — generalization probe, not accuracy.

| File | Faces | Tier | Overall | Label | Rule mean | ML agg | Defect pred (conf) | Findings (sev) | s |
|---|--:|---|--:|---|--:|--:|---|---|--:|
| 33125T73_Wraparound 90 Degree Strut Channel Bracket.STEP | 34 | simple | 82.98 | ReviewRecommended | 0.0 | 0.601 | open_shell (1.0) | M1 | 0.32 |
| 43505K359_Low-Pressure 304 Stainless Steel Cast Flange.STEP | 58 | moderate | 59.46 | NeedsAttention | 0.0 | 0.777 | open_shell (1.0) | M1 M2 | 2.28 |
| 44685K321_Low-Pressure 304-304L Stainless Steel Forged Pipe Flange.STEP | 58 | moderate | 60.83 | NeedsAttention | 0.0 | 0.709 | open_shell (1.0) | M1 M2 | 2.74 |
| 7192K47_Ultra-Corrosion-Resistant Mounted 316 Stainless Steel Ball Bearing.STEP | 95 | moderate | 63.11 | NeedsAttention | 0.0 | 0.595 | open_shell (0.85) | M1 M2 I1 | 2.96 |
| 9734K17_Flange-Mounted Linear Bearing Housing.STEP | 131 | moderate | 0.71 | NotReady | 0.0 | 0.715 | open_shell (0.999) | M5 M2 I1 | 3.01 |
| 3710T9_Mounted Ball Bearing.STEP | 177 | moderate | 57.87 | NeedsAttention | 0.0 | 0.606 | sliver_face (0.596) | M1 M3 I1 | 3.2 |
| 9804K64_Linear Bearing Housing.STEP | 218 | complex | 5.56 | NotReady | 0.0 | 0.722 | open_shell (0.981) | M4 M4 I1 | 3.52 |
| 1483N211_Mounted Ball Bearing with Two-Bolt Flange.STEP | 267 | complex | 5.43 | NotReady | 0.0 | 0.729 | sliver_face (0.988) | M4 M4 I1 | 4.18 |
| 4519N11_Bracket for Composite T-Slotted Framing.STEP | 301 | complex | 4.44 | NotReady | 0.0 | 0.778 | sliver_face (1.0) | M4 M4 I1 | 23.47 |
| 1483N115_Mounted Ball Bearing with Two-Bolt Flange.STEP | 344 | complex | 6.84 | NotReady | 0.0 | 0.658 | open_shell (0.492) | M4 M4 I1 | 4.7 |
| 4519N12_Bracket for Composite T-Slotted Framing.STEP | 578 | complex | 5.12 | NotReady | 0.0 | 0.744 | sliver_face (1.0) | M4 M4 I1 | 8.82 |
| 4519N13_Bracket for Composite T-Slotted Framing.STEP | 854 | — | — | SKIPPED | — | — | too_large (854 faces) | — | — |

## Summary

- Analyzed 11/12 parts; 1 skipped (>800 faces); 0 errored.
- Defect head flagged a synthetic-defect class on 11/11 analyzed parts (these are presumed defect-free; flags = false positives / OOD behaviour).
- Analyzed face-count range: 34–578 (5 analyzed parts >200 faces).
- Skipped (too large): 4519N13_Bracket for Composite T-Slotted Framing.STEP (854 faces).

*(Interpretation written separately — these are raw outputs.)*
