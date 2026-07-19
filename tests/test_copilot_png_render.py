"""Tests for the static colored-face PNG renderer (Day-11 option C).

Covers:
- ``color_for_score`` thresholds match the ui/viz.py palette.
- ``_save_png`` writes a non-empty PNG given fake triangles (pure-mpl path,
  no OCC required).
- ``analyze_geometry`` attaches an ``image_path`` when the renderer returns a
  path (renderer monkeypatched so the test runs without OCC + mpl backends).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from simready.copilot import png_render, tools


def test_color_for_score_thresholds() -> None:
    assert png_render.color_for_score(0.0) == png_render._GREEN
    assert png_render.color_for_score(0.39) == png_render._GREEN
    assert png_render.color_for_score(0.4) == png_render._AMBER
    assert png_render.color_for_score(0.74) == png_render._AMBER
    assert png_render.color_for_score(0.75) == png_render._RED
    assert png_render.color_for_score(1.0) == png_render._RED


def test_save_png_writes_file(tmp_path: Path) -> None:
    pytest.importorskip("PIL")
    out = tmp_path / "render.png"
    tris = [
        [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.5, 1.0, 0.0)],
        [(0.0, 0.0, 1.0), (1.0, 0.0, 1.0), (0.5, 1.0, 1.0)],
    ]
    colors = [png_render._GREEN, png_render._RED]
    result = png_render._save_png(tris, colors, out, width=400, height=300)
    assert result == out
    assert out.exists()
    assert out.stat().st_size > 200  # nontrivial PNG (header + IDAT)


def test_save_png_returns_none_on_empty_tris(tmp_path: Path) -> None:
    pytest.importorskip("PIL")
    out = tmp_path / "empty.png"
    assert png_render._save_png([], [], out, width=400, height=300) is None
    assert not out.exists()


def test_project_isometric_is_deterministic() -> None:
    # Same input -> same output; different points -> distinct projections.
    p1 = png_render._project_isometric((1.0, 2.0, 3.0))
    p2 = png_render._project_isometric((1.0, 2.0, 3.0))
    p3 = png_render._project_isometric((1.0, 2.0, 4.0))
    assert p1 == p2
    assert p1 != p3
    # Depth must move when z moves.
    assert p1[2] != p3[2]


def test_analyze_geometry_attaches_image_path(monkeypatch, tmp_path: Path) -> None:
    """``analyze_geometry`` should expose ``image_path`` in the slim summary
    when the renderer returns a path. Pipeline is stubbed to avoid OCC."""
    step = tmp_path / "fake.step"
    step.write_text("dummy")
    fake_png = tmp_path / "fake.png"
    fake_png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)

    def _fake_analyze(path: str, timeout: int = 120) -> dict:
        return {
            "status": "ReviewRecommended",
            "complexity": "moderate",
            "score": {"overall": 70.0, "label": "Yellow"},
            "geometry": {"face_count": 5, "edge_count": 15, "solid_count": 1},
            "bodies": [{"face_count": 5}],
            "findings": [],
            "combined_per_face_scores": {0: 0.1, 1: 0.5, 2: 0.9},
            "ml": {"available": False},
            "elapsed_seconds": 0.0,
        }

    def _fake_render(step_path, per_face_scores, out_dir, **kwargs):
        assert per_face_scores == {0: 0.1, 1: 0.5, 2: 0.9}
        return fake_png

    monkeypatch.setattr(tools, "analyze_file", _fake_analyze)
    monkeypatch.setattr(png_render, "render_face_score_png", _fake_render)
    # tools._maybe_render_png imports render lazily — patch the symbol it imports.
    monkeypatch.setattr(
        "simready.copilot.png_render.render_face_score_png", _fake_render
    )

    result = tools.analyze_geometry(str(step))
    assert result["image_path"] == str(fake_png)


def test_analyze_geometry_render_disabled(monkeypatch, tmp_path: Path) -> None:
    """When ``render_image=False`` the slim summary must not include ``image_path``."""
    step = tmp_path / "fake.step"
    step.write_text("dummy")

    def _fake_analyze(path: str, timeout: int = 120) -> dict:
        return {
            "status": "SimulationReady",
            "complexity": "simple",
            "score": {"overall": 95.0, "label": "Green"},
            "geometry": {"face_count": 1, "edge_count": 3, "solid_count": 1},
            "bodies": [{"face_count": 1}],
            "findings": [],
            "combined_per_face_scores": {0: 0.0},
            "ml": {"available": False},
            "elapsed_seconds": 0.0,
        }

    monkeypatch.setattr(tools, "analyze_file", _fake_analyze)
    result = tools.analyze_geometry(str(step), render_image=False)
    assert "image_path" not in result


def test_analyze_geometry_render_missing_silently(monkeypatch, tmp_path: Path) -> None:
    """If the renderer returns None (no OCC or empty tess), ``image_path`` is omitted."""
    step = tmp_path / "fake.step"
    step.write_text("dummy")

    def _fake_analyze(path: str, timeout: int = 120) -> dict:
        return {
            "status": "SimulationReady",
            "complexity": "simple",
            "score": {"overall": 95.0, "label": "Green"},
            "geometry": {"face_count": 1, "edge_count": 3, "solid_count": 1},
            "bodies": [{"face_count": 1}],
            "findings": [],
            "combined_per_face_scores": {},
            "ml": {"available": False},
            "elapsed_seconds": 0.0,
        }

    monkeypatch.setattr(tools, "analyze_file", _fake_analyze)
    monkeypatch.setattr(
        "simready.copilot.png_render.render_face_score_png",
        lambda **kw: None,
    )
    result = tools.analyze_geometry(str(step))
    assert "image_path" not in result
