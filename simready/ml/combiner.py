"""Rule and ML score fusion for Phase 2."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FusionResult:
    combined_per_face: dict[int, float] = field(default_factory=dict)
    rule_per_face: dict[int, float] = field(default_factory=dict)
    ml_per_face: dict[int, float] = field(default_factory=dict)
    body_score: float = 0.0
    overall_score: float = 0.0
    ml_penalty_applied: bool = False
    ml_penalty_points: float = 0.0
    breakdown: dict[str, Any] = field(default_factory=dict)


def _normalize_scores(scores: dict[int, float] | None) -> dict[int, float]:
    normalized: dict[int, float] = {}
    for face_index, score in (scores or {}).items():
        normalized[int(face_index)] = min(1.0, max(0.0, float(score)))
    return normalized


def fuse_scores(rule_scores: dict[int, float] | None, ml_scores: dict[int, float] | None) -> dict[int, float]:
    normalized_rule = _normalize_scores(rule_scores)
    normalized_ml = _normalize_scores(ml_scores)
    face_indices = sorted(set(normalized_rule) | set(normalized_ml))

    combined: dict[int, float] = {}
    for face_index in face_indices:
        rule = normalized_rule.get(face_index, 0.0)
        ml = normalized_ml.get(face_index, 0.5)
        high = max(rule, ml)
        low = min(rule, ml)
        combined[face_index] = (high * 0.6) + (low * 0.4)
    return combined


def aggregate_face_scores(per_face_scores: dict[int, float] | None) -> float:
    normalized = _normalize_scores(per_face_scores)
    if not normalized:
        return 0.0
    return sum(normalized.values()) / len(normalized)


def score_report(
    findings: list[dict[str, Any]],
    rule_scores: dict[int, float] | None,
    ml_scores: dict[int, float] | None,
    ml_available: bool,
) -> FusionResult:
    normalized_rule = _normalize_scores(rule_scores)
    normalized_ml = _normalize_scores(ml_scores)
    combined = fuse_scores(normalized_rule, normalized_ml)
    body_score = aggregate_face_scores(combined)

    base_score = 100.0
    critical = sum(1 for finding in findings if finding.get("severity") == "Critical")
    major = sum(1 for finding in findings if finding.get("severity") == "Major")
    minor = sum(1 for finding in findings if finding.get("severity") == "Minor")

    if critical:
        overall = 0.0
        ml_penalty = 0.0
        ml_penalty_applied = False
    else:
        overall = base_score - (major * 15.0) - (minor * 5.0)
        ml_penalty_applied = bool(ml_available and normalized_ml)
        ml_penalty = aggregate_face_scores(normalized_ml) * 20.0 if ml_penalty_applied else 0.0
        overall = max(0.0, overall - ml_penalty)

    return FusionResult(
        combined_per_face=combined,
        rule_per_face=normalized_rule,
        ml_per_face=normalized_ml,
        body_score=body_score,
        overall_score=overall,
        ml_penalty_applied=ml_penalty_applied,
        ml_penalty_points=ml_penalty,
        breakdown={
            "critical_count": critical,
            "major_count": major,
            "minor_count": minor,
            "rule_face_count": len(normalized_rule),
            "ml_face_count": len(normalized_ml),
        },
    )


def score_label(score: float) -> str:
    if score >= 90:
        return "SimulationReady"
    if score >= 70:
        return "ReviewRecommended"
    if score >= 40:
        return "NeedsAttention"
    return "NotReady"


def complexity_tier(face_count: int) -> dict[str, Any]:
    """Classify model complexity and score confidence."""
    if face_count <= 50:
        return {
            "tier": "simple",
            "label": "Simple Geometry",
            "confidence": "high",
            "note": "Score is well-calibrated for simple geometry.",
        }
    if face_count <= 200:
        return {
            "tier": "moderate",
            "label": "Moderate Geometry",
            "confidence": "medium",
            "note": "Score is indicative. Manual review recommended for critical applications.",
        }
    if face_count <= 1000:
        return {
            "tier": "complex",
            "label": "Complex Geometry",
            "confidence": "low",
            "note": "Score is approximate. Checks may miss issues on complex geometry. Manual review strongly recommended.",
        }
    return {
        "tier": "very_complex",
        "label": "Very Complex Geometry",
        "confidence": "minimal",
        "note": "Model exceeds typical calibration range. Score should be treated as a rough indicator only.",
    }
