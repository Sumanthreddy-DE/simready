"""Positive controls: every in-vocab concept's reference spec passes all of its
own checks, in all three phrasings (spec done-criterion 1, §1 rule 7)."""

from __future__ import annotations

import pytest

from simready.occ_compat import OCC_AVAILABLE

if not OCC_AVAILABLE:
    pytest.skip("OCC bindings not available", allow_module_level=True)

from simready.bench.checker import grade_shape  # noqa: E402
from simready.bench.concepts import CONCEPTS_V1, PHRASINGS, load_concepts  # noqa: E402
from simready.gen.build import build_shape  # noqa: E402
from simready.gen.spec import PartSpec  # noqa: E402

IN_VOCAB = [c for c in load_concepts(CONCEPTS_V1) if c.in_vocab]


@pytest.mark.parametrize("concept", IN_VOCAB, ids=[c.concept_id for c in IN_VOCAB])
def test_reference_spec_passes_own_checks(concept):
    shape = build_shape(PartSpec.model_validate(concept.reference_spec))
    for phrasing in PHRASINGS:
        report = grade_shape(shape, getattr(concept.checks, phrasing), concept.solids)
        failed = [c for c in report["checks"] if c["status"] == "fail"]
        assert report["gate"]["passed"], (phrasing, report["gate"])
        assert not failed, (phrasing, failed)
