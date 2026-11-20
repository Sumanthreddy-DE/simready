"""Positive controls for DSL v2: every v2 in-vocab concept has a v2 spec that
passes all three phrasings' checks under the v2 executor (design E2)."""

from __future__ import annotations

import pytest

from simready.occ_compat import OCC_AVAILABLE

if not OCC_AVAILABLE:
    pytest.skip("OCC bindings not available", allow_module_level=True)

from simready.bench.checker import grade_shape  # noqa: E402
from simready.bench.concepts import (  # noqa: E402
    CONCEPTS_V1,
    CONCEPTS_V2,
    PHRASINGS,
    load_concepts,
    load_v2_reference_specs,
)
from simready.gen.dsl import build  # noqa: E402

# c044, c045, c046 stay out of v2 vocab (c044: frozen bbox check unreachable with an axis-aligned hole).
V2_ONLY = ["c022", "c026", "c033", "c034", "c037", "c040", "c041", "c042", "c043", "c047",
           "c051", "c054", "c055", "c056", "c059", "c060", "c061", "c062", "c063", "c064", "c065"]
CONCEPTS = {c.concept_id: c for c in load_concepts(CONCEPTS_V1) + load_concepts(CONCEPTS_V2)}
FALLBACK = sorted(cid for cid, c in CONCEPTS.items() if c.in_vocab)  # 37 v1 + 4 concepts_v2 = 41


def _spec_for(entry: dict, phrasing: str) -> dict:
    """An entry is one spec, or one spec per phrasing where the phrasings' ranges are disjoint (c060)."""
    return entry if "steps" in entry else entry[phrasing]


def _assert_passes(concept, entry):
    for phrasing in PHRASINGS:
        shape = build("v2", _spec_for(entry, phrasing))
        report = grade_shape(shape, getattr(concept.checks, phrasing), concept.solids)
        assert report["gate"]["passed"], (phrasing, report["gate"])
        assert not [c for c in report["checks"] if c["status"] == "fail"], (phrasing, report["checks"])


def test_reference_file_covers_exactly_the_v2_only_concepts():
    assert sorted(load_v2_reference_specs()) == V2_ONLY


def test_v2_in_vocab_is_62_concepts():
    assert len(FALLBACK) == 41 and len(set(FALLBACK) | set(V2_ONLY)) == 62


@pytest.mark.parametrize("cid", V2_ONLY)
def test_v2_reference_spec_passes_all_phrasings(cid):
    _assert_passes(CONCEPTS[cid], load_v2_reference_specs()[cid])


@pytest.mark.parametrize("cid", FALLBACK)
def test_v1_reference_spec_passes_under_the_v2_executor(cid):
    _assert_passes(CONCEPTS[cid], CONCEPTS[cid].reference_spec)
