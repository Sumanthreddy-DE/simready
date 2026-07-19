"""Tests for apply_random_features in scripts/generate_parametric_steps.py.

Domain randomization for the defect head's real-CAD FP problem
(real_eval.md §1): 'clean' training geometry must carry manufactured
features (fillets/chamfers) so feature-richness stays orthogonal to the
defect label.
"""

from __future__ import annotations

import random

import pytest

occ = pytest.importorskip(
    "OCC.Core.BRepPrimAPI",
    reason="pythonocc-core not available (run under the sr env)",
)

from scripts.generate_parametric_steps import apply_random_features, gen_normal_box
from simready.occ_utils import count_topology


def test_fillet_increases_face_count():
    rng = random.Random(42)
    base = gen_normal_box(rng)
    featured = apply_random_features(base, rng, fillet_prob=1.0, chamfer_prob=0.0)
    assert count_topology(featured)["face_count"] > 6


def test_chamfer_increases_face_count():
    rng = random.Random(42)
    base = gen_normal_box(rng)
    featured = apply_random_features(base, rng, fillet_prob=0.0, chamfer_prob=1.0)
    assert count_topology(featured)["face_count"] > 6


def test_zero_prob_is_identity():
    rng = random.Random(42)
    base = gen_normal_box(rng)
    out = apply_random_features(base, rng, fillet_prob=0.0, chamfer_prob=0.0)
    assert out is base


def test_failed_fillet_falls_back_to_previous_shape():
    # Radius far larger than the part: OCC must fail, generation must not.
    rng = random.Random(42)
    base = gen_normal_box(rng)
    out = apply_random_features(
        base, rng, fillet_prob=1.0, chamfer_prob=0.0, radius_range=(500.0, 600.0)
    )
    assert out is not None
    assert count_topology(out)["face_count"] >= 6


def test_featured_shape_remains_valid_solid():
    from simready.validator import validate_brep

    rng = random.Random(7)
    base = gen_normal_box(rng)
    featured = apply_random_features(base, rng, fillet_prob=0.5, chamfer_prob=0.25)
    assert validate_brep(featured).is_valid is True
