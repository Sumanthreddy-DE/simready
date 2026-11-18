# sp1-task3-geometry report

**Status:** done
**Last verified:** 2026-11-18
**Status evidence:** 5f8681e, b9804bb, 96747fd are ancestors of main (verified 2026-11-18)

Branch: gpt/sp1-task3-geometry   Base: 58a6906   Head: 3716151
## Result
DONE -- Task 3 and a pythonocc-first/OCP shim run under OCP, with exact-nominal benchmark extents and no lost baseline passes.
## Commits
- 5f8681e shim, shared/build/validator imports, adapter tests -- verified by `python -m pytest -q -p no:cacheprovider tests/test_occ_compat.py tests/test_gen_build.py` -> 17 passed in 8.33s
- b9804bb geometry and 14 tests -- verified by `python -m pytest -q -p no:cacheprovider tests/test_bench_geometry.py` -> 14 passed in 2.72s
- 96747fd plan/spec deviations and Task 3 checkboxes -- verified by `git diff --check` -> no output
- 906868d AttributeError backend fallback -- verified by `python -m pytest -q -p no:cacheprovider tests/test_occ_compat.py` -> 5 passed in 2.32s; new missing-attribute test first failed with AttributeError on Bnd_Box.
- 3716151 restore plan comments/docstrings -- verified by `python -m pytest -q -p no:cacheprovider tests/test_bench_geometry.py` -> 14 passed in 2.80s; tokenize/AST-assisted unified diff of non-comment lines (imports, docstrings, sorted_extents excluded) -> empty diff.
## Checks
- G1: PASS -- rerun after both review commits, corrected coordinator-approved summary-filter command -> 32 passed in 8.65s (14 geometry, 13 unchanged build, 5 shim).
- G2: PASS -- specified direct-import grep -> no output; same regex on base occ_utils positive control -> 10 import lines.
- G3: PASS -- specified Python nominal-cylinder/plate command, plus BACKEND assertion -> OK; BACKEND == 'ocp'.
- G4: PASS -- archive sp1-bench, pytest -rA in archive and worktree, compare PASSED node IDs -> positive control: 112 baseline passes; regressions: 0.
- G5: PASS -- `python -m pytest -q -p no:cacheprovider tests/test_bench_geometry.py -k nominal` with Add restored temporarily -> 2 failed, 12 deselected (20.0000002 > 20.0; 2.0000001999999997 > 2.0); restored AddOptimal -> G1 31 passed.
- G6: PASS -- complete pythonocc source-name map below; `_MODULE_NAMES` plus adapter-loading blocks in occ_compat.py provide the executable map.
- G6 map (all modules prefixed OCC.Core): Bnd: Bnd_Box; BRep: BRep_Builder; BRepAdaptor: BRepAdaptor_Curve, BRepAdaptor_Surface; BRepAlgoAPI: BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse; BRepCheck: BRepCheck_Analyzer; BRepClass3d: BRepClass3d_SolidClassifier.
- G6 map: BRepGProp: BRepGProp_Face, brepgprop (VolumeProperties, SurfaceProperties); BRepBndLib: brepbndlib (Add, AddOptimal); BRepPrimAPI: BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder; BRepTools: breptools (UVBounds), breptools_UVBounds (optional legacy fallback).
- G6 map: GCPnts: GCPnts_AbscissaPoint (Length); GeomAbs: GeomAbs_Cylinder; GProp: GProp_GProps; IFSelect: IFSelect_RetDone; ShapeAnalysis: ShapeAnalysis_FreeBounds; STEPControl: STEPControl_AsIs, STEPControl_Reader, STEPControl_Writer.
- G6 map: TopAbs: TopAbs_EDGE, TopAbs_FACE, TopAbs_SOLID, TopAbs_OUT; TopExp: TopExp_Explorer, topexp (MapShapesAndAncestors); TopoDS: TopoDS_Shell, topods (Face, Solid, Edge); TopTools: TopTools_IndexedDataMapOfShapeListOfShape; gp: gp_Ax2, gp_Dir, gp_Pnt, gp_Vec.
- Additional: PASS -- import blocker for OCC/OCP -> no-bindings fallback OK (all geometry exports None; validator IFSelect_RetDone stays 1); author self-review and `git diff --check` clean.
## Baseline
before: 27 failed, 112 passed, 29 skipped in 2.42s   after: 20 failed, 151 passed, 28 skipped in 15.19s
## Deviations
- Coordinator approved validator.py import-block-only migration: unchanged build STEP round-trip test otherwise fails without pythonocc; function bodies are unchanged.
- OCP 8 maps indexed shape maps through OCP.collections.IndexedDataMap_TopoDS_Shape_List_TopoDS_Shape_TopTools_ShapeMapHasher and GCPnts length through Length_s; executed box topology/edge-length tests verify both.
- Coordinator corrected G1 to filter pytest summary before tail: buffered OCP C++ STEP logs appear after pytest's summary. G4 used identical archive/pass-set logic with Python comparison and scratch under /tmp/opencode-sp1-task3-geometry, avoiding the original command's scratch outside the permitted directory.
- Recorded requested spec deviations 5 (gap-free extents) and 6 (shim); all 12 original geometry expectations pass unchanged. Contract-specific report/scratch replaces skill workspace and no helper reviewer was dispatched, as requested.
## Questions
- none
## Not verified
- Actual pythonocc runtime on laptop sr; no pythonocc installation here. Other OCC importers remain outside compatibility scope; full suite retains 20 pre-existing failures in brepnet/checks/graph_extractor/pipeline/splitter (full node IDs and tracebacks: /tmp/opencode-sp1-task3-geometry/review-after.log).
