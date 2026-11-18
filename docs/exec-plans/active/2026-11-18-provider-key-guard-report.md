# bench-provider-key-guard report
Branch: gpt/bench-provider-key-guard   Base: efe3f15cf7ce92fd2ad8bc85ef402c28091e8b50   Head: 1c91e1f29cf0f8bdaa75acf4f5cd69a4259b4f3a
## Result
DONE -- Known tool-envelope/root reason signatures are unscored without grading; independent defects retain F2/F3/F9, text/direct classification and positional compatibility are preserved.
## Commits
- 1c91e1f fix(bench): exclude known provider argument contamination -- verified by `/home/sumanth/.venvs/simready-ocp/bin/python /tmp/opencode/provider_key_check.py /home/sumanth/projects/Mech/SimReady/.worktrees/bench-provider-key-guard` -> PROVIDER_KEY_ACCEPTANCE_PASS
## Checks
- Commands below run in the assigned worktree; `python` denotes `/home/sumanth/.venvs/simready-ocp/bin/python`.
- behavior: PASS -- coordinator probe -> NEGATIVE_CONTROLS_PASS; PROVIDER_KEY_ACCEPTANCE_PASS (base: five contaminated cases failed, clean controls passed).
- regression: PASS -- `python -m pytest -q -p no:cacheprovider tests/test_bench_attempt.py -k provider_arguments && python -c 'print("PROVIDER_REGRESSION_PASS")'` -> 63 passed, 29 deselected; PROVIDER_REGRESSION_PASS.
- mutation (MANUAL): PASS -- disabled evaluate_reply guard with `if False and ...`; `python -m pytest -q -p no:cacheprovider tests/test_bench_attempt.py -k provider_arguments --tb=no` -> 28 failed, 35 passed, 29 deselected; restored guard -> 63 passed, 29 deselected.
- TDD (MANUAL): PASS -- new tests against unchanged implementation -> 28 failed, 35 passed, 29 deselected; baseline selection -> 29 deselected (no matching tests).
- attempt (MANUAL): PASS -- `python -m pytest -q -p no:cacheprovider tests/test_bench_attempt.py` -> 92 passed in 59.09s.
- bench (MANUAL): PASS -- `python -m pytest -q -p no:cacheprovider tests/test_bench*.py` -> 210 passed, 1 deselected in 67.63s.
- full: FAIL (same 20 baseline failures) -- `python -m pytest -q -p no:cacheprovider --ignore=tests/test_defect_head.py` -> 20 failed, 336 passed, 27 skipped, 6 deselected in 80.40s.
- Existing failures in tests/test_brepnet.py: test_brepnet_fallback_returns_per_face_scores_and_embeddings; test_brepsage_backend_engages_when_checkpoint_exists.
- Existing failures in tests/test_checks.py: test_small_feature_fixture_flags_small_geometry; test_duplicate_body_fixture_flags_duplicate_body_heuristic; test_duplicate_face_fixture_flags_duplicate_face_heuristic.
- Existing failures in tests/test_graph_extractor.py: test_extract_brep_graph_smoke_box; test_smoke_box_exact_counts; test_extract_brep_graph_multi_body_works; test_extract_brep_graph_node_features_include_phase2_fields; test_extract_brep_graph_edge_features_include_dihedral_metadata; test_extract_brep_graph_multi_body_per_body_extraction; test_uv_bounds_returns_nonzero_for_box_face.
- Existing failures in tests/test_pipeline.py: test_analyze_multi_body_file; test_analyze_small_feature_file; test_analyze_duplicate_body_file; test_analyze_duplicate_face_file; test_combined_per_face_scores_match_face_count; test_self_intersection_skipped_when_face_count_exceeds_limit; test_brepnet_inference_is_honestly_labelled_heuristic.
- Existing failure in tests/test_splitter.py: test_split_bodies_multi_body_fixture.
- diff: PASS -- `git diff --check` -> clean; self-review checked parse metadata, classification precedence, mixed wrapper keys, input immutability and unchanged classify_spec.
## Baseline
before: attempt 29 passed in 56.01s; full 20 failed, 273 passed, 27 skipped, 6 deselected in 78.00s   after: attempt 92 passed; full 20 failed, 336 passed, 27 skipped, 6 deselected.
## Deviations
- none
## Questions
- none
## Not verified
- pythonocc backend (unavailable on VPS); live provider calls (forbidden by contract).
