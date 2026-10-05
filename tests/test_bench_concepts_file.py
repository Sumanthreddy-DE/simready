"""The shipped concept file: schema, IDs, vocabulary limits. No OCC."""

from __future__ import annotations

from simready.bench.concepts import CONCEPTS_V1, load_concepts
from simready.gen.spec import PartSpec


def test_concepts_v1_parses_with_50_sequential_ids():
    concepts = load_concepts(CONCEPTS_V1)
    assert [c.concept_id for c in concepts] == [f"c{i:03d}" for i in range(1, 51)]


def test_reference_specs_are_valid_dsl():
    for c in load_concepts(CONCEPTS_V1):
        if c.in_vocab:
            PartSpec.model_validate(c.reference_spec)  # raises with the concept's error


def test_every_phrasing_has_a_gradable_check():
    for c in load_concepts(CONCEPTS_V1):
        for phrasing in ("explicit", "engineer"):
            checks = getattr(c.checks, phrasing)
            assert any(ch.type != "not_checked" for ch in checks), (c.concept_id, phrasing)
