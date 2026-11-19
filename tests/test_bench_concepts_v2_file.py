"""The SP2 held-out concept file: schema, IDs, vocabulary limits. No OCC.

Geometry controls (positive, negative, reference specs) run in
scripts/bench_concepts_v2.py, which also writes the file.
"""

from __future__ import annotations

from simready.bench.concepts import BENCH_DIR, load_concepts
from simready.gen.spec import PartSpec

CONCEPTS_V2 = BENCH_DIR / "prompts" / "concepts_v2.jsonl"


def test_concepts_v2_parses_with_ids_after_v1():
    concepts = load_concepts(CONCEPTS_V2)
    assert [c.concept_id for c in concepts] == [f"c{i:03d}" for i in range(51, 66)]


def test_reference_specs_are_valid_dsl():
    for c in load_concepts(CONCEPTS_V2):
        if c.in_vocab:
            PartSpec.model_validate(c.reference_spec)


def test_every_phrasing_has_a_gradable_check():
    for c in load_concepts(CONCEPTS_V2):
        for phrasing in ("explicit", "engineer"):
            checks = getattr(c.checks, phrasing)
            assert any(ch.type != "not_checked" for ch in checks), (c.concept_id, phrasing)
