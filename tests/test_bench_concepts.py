"""Concept-file schema tests. No OCC, no network."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from simready.bench.concepts import (
    CHECK_LIST,
    Concept,
    HoleSet,
    file_sha256,
    in_range,
    load_concepts,
)

PLATE_SPEC = {
    "steps": [
        {"op": "box", "dx": 40, "dy": 30, "dz": 5},
        {"op": "cyl", "r": 3, "h": 5, "at": [20, 15, 0]},
        {"op": "cut", "a": 0, "b": 1},
    ]
}


def _concept(**over):
    base = {
        "concept_id": "c900",
        "name": "test plate",
        "in_vocab": True,
        "prompts": {
            "explicit": "A 40 x 30 x 5 mm plate with a 6 mm through hole in the centre.",
            "engineer": "Small 5 mm cover plate with an M5 clearance hole.",
            "intent": "A little plate with a hole for a screw.",
        },
        "checks": {
            "explicit": [{"type": "bbox_sorted", "ranges": [[4.9, 5.1], [29.9, 30.1], [39.9, 40.1]]}],
            "engineer": [{"type": "hole_set", "diameter": [5.3, 5.8], "count": [1, 1], "through": True}],
            "intent": [{"type": "not_checked", "what": "outline"}],
        },
        "sources": ["ISO 273 M5 clearance 5.3-5.8"],
        "reference_spec": PLATE_SPEC,
    }
    base.update(over)
    return base


def test_in_range_open_and_closed_bounds():
    assert in_range(5.0, (4.9, 5.1))
    assert not in_range(5.2, (4.9, 5.1))
    assert in_range(1e6, (3.0, None))
    assert in_range(-1.0, (None, 0.0))


def test_valid_concept_parses_with_discriminated_checks():
    c = Concept.model_validate(_concept())
    assert isinstance(c.checks.engineer[0], HoleSet)
    assert c.solids == 1


def test_in_vocab_requires_reference_spec_and_vice_versa():
    with pytest.raises(ValidationError, match="needs reference_spec"):
        Concept.model_validate(_concept(reference_spec=None))
    with pytest.raises(ValidationError, match="must not carry"):
        Concept.model_validate(_concept(in_vocab=False))


def test_bad_concept_id_and_unknown_field_rejected():
    with pytest.raises(ValidationError):
        Concept.model_validate(_concept(concept_id="plate1"))
    with pytest.raises(ValidationError):
        Concept.model_validate(_concept(extra_field=1))


def test_hole_pattern_needs_exact_count_and_pair_count():
    ok = {"type": "hole_set", "diameter": [3.3, 3.5], "count": [3, 3],
          "pattern": [[9.9, 10.1], [9.9, 10.1], [19.9, 20.1]]}
    CHECK_LIST.validate_python([ok])
    with pytest.raises(ValidationError, match="exact count"):
        CHECK_LIST.validate_python([{**ok, "count": [2, 3]}])
    with pytest.raises(ValidationError, match="3 distances"):
        CHECK_LIST.validate_python([{**ok, "pattern": [[9.9, 10.1]]}])


def test_any_of_nests_checks():
    checks = CHECK_LIST.validate_python([
        {"type": "any_of", "checks": [
            {"type": "bore", "diameter": [7.9, 8.1]},
            {"type": "boss", "diameter": [7.9, 8.1]},
        ]}
    ])
    assert checks[0].checks[1].type == "boss"


def test_load_concepts_rejects_duplicate_ids(tmp_path):
    p = tmp_path / "c.jsonl"
    line = json.dumps(_concept())
    p.write_text(line + "\n" + line + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate concept_id c900"):
        load_concepts(p)


def test_load_concepts_and_hash(tmp_path):
    p = tmp_path / "c.jsonl"
    p.write_text(json.dumps(_concept()) + "\n\n", encoding="utf-8")
    assert [c.concept_id for c in load_concepts(p)] == ["c900"]
    assert len(file_sha256(p)) == 64
