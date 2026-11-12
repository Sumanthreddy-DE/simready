# SP1 Task 2 review: concepts_v1 draft

**Status:** done
**Last verified:** 2026-11-12

Review of the Task 2 draft (`45a43f5`): `simready/bench/prompts/concepts_v1.jsonl` and
`tests/test_bench_concepts_file.py`. Plan: `2026-10-04-sp1-bench-implementation.md` Task 2
(authoring rules 1-9). Design: `2026-09-25-sp1-cad-benchmark-design.md` (D2, D4, §1).
Branch `sp1-bench`, base `c8b2cec`.

Two points are left to the user: (b) whether engineer ranges may exclude the nominal size, and
(c) the user's own proofread. This document lists the facts for both and decides neither.

## Method

1. **Rules 1-9.** Checked by hand for every concept. Rule 5 (one reference spec passes all three
   check lists) was checked by script for in-vocab concepts and by hand for out-of-vocab ones.
2. **Reference specs.** Task 3/4 do not exist yet. A scratch evaluator copied the plan's Task 3
   `geometry.py` and Task 4 `checker.py` code verbatim, built every in-vocab `reference_spec` with
   `simready.gen.build.build_shape`, and graded it against all three check lists.
   - Result before the fixes: 111/111 phrasing checks pass (37 in-vocab × 3).
   - Result after the fixes: 111/111 pass.
   - Negative control: three deliberately broken specs fail as expected, all 9 phrasings. The
     broken specs were c001 with one 3.0 mm hole, c003 with a 6 mm deep seat, and c039 with
     square corners.
   - Not evaluable by script: out-of-vocab concepts, because they have no reference spec. Their
     rule 5 status was checked by hand (see c045).
3. **Sources.** Checked against fetched primary or secondary documents (URLs below). Verdicts:
   verified / mismatch / unverifiable.

## Fixes (commit `bd50c0d`)

| id | change | reason |
|---|---|---|
| c020 | engineer gland-hole `bore` 16.0-16.2 → **16.1-16.3**; source line rewritten | Lapp T21 gives the M16x1.5 bore as 16.3 −0.2, not 16.0 +0.2. Explicit 16.2 and the reference (16.15) stay inside. |
| c017 | source line only, checks unchanged | Same T21 table: M20x1.5 bore 20.3 −0.2 (20.1-20.3). The body range 19.5-20.0 stays below the 20.1 minimum hole, so it still fits. |
| c031 | engineer thickness 1.9-2.1 → **1.95-2.0** (bbox and boss `height_min`); "unverified" source replaced; reference thickness 2 → 1.975 | DIN 988 table (fasteners.eu): h = 2.0 has max 2.0, min 1.95. The reference moved to the midpoint because a 2.0 mm part measures 2.0000002 (see the checker finding). |

`.gitattributes` (open point (a), commit `e6193ea`): `*.jsonl text eol=lf`, `*.sha256 text eol=lf`.
The concept file already had LF endings in the index and working tree, so it needed no
renormalisation.

The test file is unchanged: no asserted count moved.

## Checker finding for Task 3 (not a concept defect)

The plan's `sorted_extents` uses `brepbndlib.Add`. That call adds a 1e-7 mm gap on each side,
so a 2 mm plate measures 2.0000002. Any `bbox_sorted` range whose upper bound equals the nominal
therefore fails an exact-nominal answer. 15 engineer-phrasing ranges in 8 concepts are affected:
c006, c011, c012, c031, c034, c038, c042 and c047. The reference specs pass only because they use mid-tolerance values (for example c006
r = 9.975).

Fix this in Task 3, not in the concepts. Options:
- Subtract `Bnd_Box.GetGap()`.
- Use `brepbndlib.AddOptimal(shape, box, False, False)`.
- Compare with a 1e-6 epsilon in `in_range` for extents.

Add a Task 3 test case: a 20 mm cylinder must pass `[19.987, 20.0]`.

## Per-concept table

In-vocab steps: every plate with n holes has 1 + 2n steps, and every spec is within 16 steps
(PartSpec-validated). "Rule issues" lists only real findings. Source abbreviations are defined in
the next section.

| id | in_vocab | steps | rule issues | source verdict | fix |
|---|---|---|---|---|---|
| c001 | yes | 11 | none | NEMA17 verified; ISO273 verified | — |
| c002 | yes | 11 | none | NEMA23 verified (AutomationDirect drawing; cited Omega drawing not fetched); ISO273 verified | — |
| c003 | yes | 5 | none | 608 verified (distributor listings); ISO286 H7 unverifiable | — |
| c004 | yes | 3 | none | ISO273 verified | — |
| c005 | yes | 3 | none | ISO273 verified | — |
| c006 | yes | 3 | bbox gap (Task 3) | DIN705 verified; ISO286 H8/h13/js14 unverifiable | — |
| c007 | yes | 13 | none | ISO273 verified; ISO286 H7 unverifiable | — |
| c008 | yes | 15 | none | ISO273 verified | — |
| c009 | yes | 9 | none | ISO273 verified | — |
| c010 | yes | 13 | weak intent: a blank plate passes | ISO273 verified | — |
| c011 | yes | 3 | bbox gap | DIN125 verified | — |
| c012 | yes | 3 | bbox gap | ISO7089 verified | — |
| c013 | yes | 13 | none | 608 verified; ISO273 verified; ISO286 unverifiable | — |
| c014 | yes | 9 | none | ARDUINO verified (4th hole x = 550 mil is not dimensioned; scaled ≈550 from the drawing); ISO273 verified | — |
| c015 | yes | 9 | none | RPI4 verified; ISO273 verified | — |
| c016 | yes | 3 | none | ISO273 verified; MISUMI unverifiable (403; centre-hole value unused) | — |
| c017 | yes | 5 | none | T21 **mismatch** (text only) | source line |
| c018 | yes | 7 | none | ISO286 H7 unverifiable | — |
| c019 | yes | 3 | none | ISO286 H8 unverifiable | — |
| c020 | yes | 11 | none | T21 **mismatch** | engineer bore 16.1-16.3 |
| c021 | yes | 9 | none | RUTHEX verified (retailer copy of the ruthex table: D3 4.0, L 5.7, W min 1.6) | — |
| c022 | no | — | fake (plain holes) passes; countersink not gradable | ISO273 verified | — |
| c023 | yes | 5 | weak intent: any block with one 30 mm extent passes | no standard | — |
| c024 | yes | 7 | none | ISO273 verified | — |
| c025 | yes | 3 | none | no standard | — |
| c026 | no | — | none | ISO273 verified | — |
| c027 | yes | 7 | none | ISO273 verified | — |
| c028 | yes | 5 | none | 965-6H verified; ISO 2306 tap drill 3.3 unverifiable (lies inside the verified 6H band) | — |
| c029 | yes | 5 | none | ISO286 H7 unverifiable | — |
| c030 | yes | 3 | point (b) | ISO4379 Table 1 verified; Table 3 classes (E6/s6/h13) unverifiable | — |
| c031 | yes | 3 | point (b); bbox gap | DIN988 verified (d1, d2, thickness) | thickness 1.95-2.0 |
| c032 | yes | 15 | none | NEMA17 verified; ISO273 verified | — |
| c033 | no | — | intent says "about 10 mm" but has no length check | 965-6H verified; ISO 2306 unverifiable | — |
| c034 | no | — | bbox gap; bore 6.6-8.0 is wider than c044's 6H band 6.647-6.912 | ISO4032 verified (s 12.73-13.00, m 6.44-6.80, e min 14.38) | — |
| c035 | yes | 11 | none | ISO273 verified | — |
| c036 | yes | 3 | none | no standard | — |
| c037 | no | — | none | ISO273 verified | — |
| c038 | yes | 5 | bbox gap | ISO286 h6 unverifiable | — |
| c039 | yes | 11 | intent states every dimension except R | no standard (volume formula re-derived: 11570.8) | — |
| c040 | no | — | none (19 steps > 16) | ISO273 verified | — |
| c041 | no | — | `sources` empty (no standard values used) | — | — |
| c042 | no | — | bbox gap; intent has no length check | ISO286 h6 unverifiable | — |
| c043 | no | — | none | no standard | — |
| c044 | no | — | point (b) | 965-6H verified | — |
| c045 | no | — | **rule 5**: explicit 6.0 lies outside engineer 5.794-5.974 (point (b)) | 6g-M6 verified | — |
| c046 | no | — | none | tip diameter m(z+2) = 44 by definition; ISO286 unverifiable | — |
| c047 | no | — | bbox gap; fake (axial hole) passes all three phrasings | ISO286 unverifiable | — |
| c048 | yes | 3 | weak intent: zero gradable checks, so any valid solid passes | no standard | — |
| c049 | yes | 11 | airflow 30-40 is a design range | NOCTUA verified only via a search snippet of noctua.at (page returned 429); ISO273 verified | — |
| c050 | yes | 13 | none | HIWIN verified (B 20, C 20, W 27, L 45.4, M3×3.5); ISO273 verified | — |

Counts:
- 37 in-vocab, 13 out-of-vocab. This matches the plan table's own yes/no column. The plan's
  "38 / 12" sentence miscounts its own table.
- Rule 1 (IDs), rule 6 (step counts) and rule 9 (no template) hold. The plate explicit prompts
  share a shape ("A W x D x T mm plate with …"), but the wording varies; there is no slot-filled
  template.

## Sources

| key | document | verdict |
|---|---|---|
| ISO273 | IS 1821:1987 = identical adoption of ISO 273:1979, p.6 table, <https://law.resource.org/pub/in/bis/S01/is.1821.1987.pdf>: M2.5 2.7/2.9/3.1, M3 3.2/3.4/3.6, M4 4.3/4.5/4.8, M5 5.3/5.5/5.8, M6 6.4/6.6/7, M8 8.4/9/10 | verified |
| ISO7089 | <https://www.fasteners.eu/standards/ISO/7089/>: M6 6.4-6.62 / 11.57-12 / 1.4-1.8; M10 10.5-10.77 / 19.48-20 / 1.8-2.2 | verified |
| DIN125 | <https://www.fasteners.eu/standards/DIN/125-A/>: M6 same as ISO 7089 | verified |
| DIN705 | <https://www.fasteners.eu/standards/DIN/705-A/>: d1 10 (H8), b 10 (js14), d2 20 (h13), M5 | verified |
| DIN988 | <https://www.fasteners.eu/standards/DIN/988/>: d1 10 → 10.04-10.19 (D12), d2 16 → 15.77-15.95 (d12); h 2.0 → 1.95-2.0 | verified |
| ISO4032 | <https://www.fasteners.eu/standards/ISO/4032/>: M8 s 12.73-13.00, m 6.44-6.80, e min 14.38 | verified |
| NEMA17 | IMS/Schneider NEMA 17 drawing, <https://people.ece.cornell.edu/land/courses/ece4760/FinalProjects/f2017/kmv48_rp625/kmv48_rp625/kmv48_rp625/NEMA17steppermotor.pdf>: holes 1.22 in (30.99) square, 4X M3, pilot Ø22.0 +0/−0.052 | verified |
| NEMA23 | AutomationDirect STP-MTRAC-23078D drawing, <https://cdn.automationdirect.com/static/drawings/STP-MTRAC-23078D.pdf>: holes 1.86 in (47.1/47.2), pilot 1.50 in (38.1), 4X 0.20 in (5.0) | verified (a different vendor than the cited Omega drawing) |
| 608 | distributor listings of SKF 608, e.g. <https://ie.rs-online.com/web/p/ball-bearings/2867530> (via search results): 8 × 22 × 7 | verified (secondary; skf.com renders client-side and returned no data) |
| ARDUINO | A000066 datasheet §5.4, <https://docs.arduino.cc/resources/datasheets/A000066-datasheet.pdf> p.11: 4 × Ø3.20; 600/2600 mil from the left edge, 100/700/1800/2000 mil from the top edge | verified; the bottom-left hole x is not dimensioned (scaled ≈550 mil) |
| RPI4 | <https://datasheets.raspberrypi.com/rpi4/raspberry-pi-4-mechanical-drawing.pdf>: 85 × 56, holes 58 × 49, 3.5 from the edges, Ø2.7 | verified |
| HIWIN | HIWIN MGN/MGW catalogue 2023, Table 3.79, <https://damencnc.com/userdata/file/3455-3_HIWIN_MGN_and_MGW_Product_Catalog_2023.pdf> | verified |
| RUTHEX | <https://www.3djake.com/ruthex/threaded-insert-m3-100-pieces>: M3 D1 4.6, D2 3.9, D3 4.0, L 5.7, W min 1.6 | verified (retailer copy; ruthex.de not fetched) |
| NOCTUA | <https://noctua.at/en/nf-a4x10-flx/specification>: 32 × 32 mm per search snippet | unverifiable directly (HTTP 429 on every fetch) |
| T21 | Lapp T21, <https://t3.lappcdn.com/fileadmin/DAM/Miltronic_LV_LT_EE/testfolder/FAQ/T21_Thread_Dimensions_Tightening_Torque_Values_and_Dimensions_for_Cable_Glands.pdf>: bore D3 M16x1.5 16.3 −0.2, M20x1.5 20.3 −0.2 | **mismatch** with the draft's 16.0 +0.2 / 20.0 +0.2 (fixed) |
| ISO4379 | ISO 4379:2018 preview, Table 1, <https://cdn.standards.iteh.ai/samples/75584/47805f3148794c38b030fc1793d01ff6/ISO-4379-2018.pdf>: d1 10 → d2 12/14/16, b1 6/10 | Table 1 verified; Table 3 (E6, s6, h13) not in the preview, unverifiable. ISO 4379:2024 supersedes 2018; not checked for changes |
| 965-6H | CDE chart (DIN 13 / ISO 6H), <https://cdefasteners.com/sites/default/files/product-specs/metintthread.pdf>: minor M3 2.459-2.599, M4 3.242-3.422, M8 6.647-6.912 | verified (secondary) |
| 6g-M6 | <https://amesweb.info/Screws/metric-external-thread-dimensions-chart.aspx>: M6x1 6g major 5.794-5.974 | verified (secondary) |
| ISO286 | no free ISO 286-2 table fetched | unverifiable. Indirect cross-checks: DIN 988's D12 (6-10) and d12 (10-18) limits match ISO 286 arithmetic, and ISO 7089's d1/d2 spans match IT13/IT14. H7, H8, E6, s6, h6, h13, js14 are not independently checked |
| MISUMI | HFS5-2020 page returned 403 | unverifiable (only "20 × 20" is used, and it is generic) |
| ISO 2306 | tap drills 2.5 / 3.3 / 6.8 | unverifiable (not fetched); each lies inside its verified 6H minor-diameter band, so no check depends on it |

Verdict count by source document: 16 verified, 1 mismatch (Lapp T21, two concepts),
5 unverifiable or partial (NOCTUA, ISO 4379 Table 3, ISO 286, MISUMI, ISO 2306).

## Point (b): engineer ranges that exclude the nominal size (facts only)

| id | engineer range | nominal | effect on a nominal answer | source status |
|---|---|---|---|---|
| c030 | bore E6 10.025-10.034; OD s6 16.028-16.039; length h13 9.78-10.0 | 10 / 16 / 10 | "10 × 16 × 10" fails the bore and OD checks; the length passes only after the Task 3 bbox fix | E6/s6/h13 unverifiable (ISO 4379 Table 3 not available). The explicit prompt uses 10.03 / 16.035 / 9.9 to stay inside, which reads unnaturally |
| c031 | bore D12 10.04-10.19; OD d12 15.77-15.95 | 10 / 16 | "10 × 16 × 2" fails the bore and OD checks | verified (fasteners.eu DIN 988). Explicit 10.1 / 15.9 lie inside |
| c044 | bore = 6H minor diameter 6.647-6.912 | M8 (8) | an 8 mm bore fails, which is intended (the prompt asks for the tap-drill bore); tap drill 6.8 lies inside | verified (CDE chart) |
| c045 | major diameter 6g 5.794-5.974 | 6.0 | a 6.0 rod fails engineer; **the explicit prompt states 6 mm, so rule 5 is broken** | verified (Ames) |

Choices for one line each: keep the standard zones (they test fit knowledge, and a nominal
answer fails), widen the zones to include the nominal, or for c045 change the explicit prompt to
a 6g size (for example 5.9) or widen the engineer range to 6.0.

## Point (c): proofread pointers (facts only)

- Fixed lines to re-read: c017, c020, c031.
- Weak intent checks:
  - c010: a blank plate passes (slots are partial cylinders; no check type sees them).
  - c023: any block with one 30 mm extent passes.
  - c048: no gradable intent check at all.
  - c047: an axial-hole fake passes all three phrasings. A `volume` check on explicit and
    engineer would separate the fake (axial hole ≈ 350 mm³ removed vs cross hole ≈ 70 mm³), but
    no range has been computed for it.
  - All need either a new check type (slot / step / cavity) or accepting them as is.
- c022 (countersink) cannot be separated from a plain-hole fake by volume within ±0.1 on the
  plate dimensions (≈143 mm³ difference vs ≈400 mm³ tolerance band).
- c034 bore 6.6-8.0 vs c044's 6H band 6.647-6.912: same thread type, different strictness.
- c033 and c042: the intent prompt names a length, but there is no length check.
- c039 intent gives every dimension except the radius.
- c049 airflow 30-40 mm and every "pattern tolerance ±0.15 / ±0.2 / ±0.3" are design choices,
  not standard values.

## Not verifiable in this session

- **Not checked against a fetched table:** ISO 286-2 tolerance classes (except the D12/d12
  cross-check), ISO 4379 Table 3, ISO 2306 tap drills, the MISUMI HFS5-2020 page, and the Noctua
  page (429).
- **Secondary sources only:** the SKF 608 dimensions (distributor listings) and the ruthex insert
  (retailer copy).
- **Out-of-vocab concepts:** no geometry check (no reference spec). Their rule 5 status was
  checked by hand.
- **Checker:** the evaluator is the plan's Task 3/4 code, not a shipped module. Results will need
  re-confirming once Task 3/4 land (`tests/test_bench_reference_specs.py`).
