"""Visualization helpers for the future Streamlit UI."""

from __future__ import annotations

from typing import Any


def face_score_color(score: float) -> str:
    if score >= 0.75:
        return "#ef4444"
    if score >= 0.4:
        return "#f59e0b"
    return "#22c55e"


def ml_heatmap_color(score: float) -> str:
    if score >= 0.75:
        return "#fb923c"
    if score >= 0.4:
        return "#60a5fa"
    return "#1d4ed8"


def build_face_overlay_payload(report: dict[str, Any]) -> list[dict[str, Any]]:
    combined = report.get("combined_per_face_scores", {})
    ml_scores = report.get("ml", {}).get("per_face_scores", {}) if isinstance(report.get("ml"), dict) else {}
    payload: list[dict[str, Any]] = []
    for face_index, score in combined.items():
        ml_score = ml_scores.get(face_index, ml_scores.get(str(face_index), 0.0))
        payload.append(
            {
                "face_index": int(face_index),
                "combined_score": float(score),
                "combined_color": face_score_color(float(score)),
                "ml_score": float(ml_score),
                "ml_color": ml_heatmap_color(float(ml_score)),
            }
        )
    return payload
