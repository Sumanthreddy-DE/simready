"""Tests for simready/copilot/rag.py.

Uses a deterministic stub embedder so tests run offline and never download
the sentence-transformers model.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from simready.copilot import rag, tools


class FixedEmbedder:
    """Deterministic embedder for tests. Maps known phrases to fixed vectors;
    unknown text gets a hash-based vector. Pre-normalizes nothing — RagIndex
    handles normalization."""

    def __init__(self, mapping: dict[str, list[float]] | None = None, dim: int = 4) -> None:
        self._mapping = mapping or {}
        self._dim = dim

    def embed(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self._dim), dtype=np.float32)
        for i, text in enumerate(texts):
            if text in self._mapping:
                out[i] = np.asarray(self._mapping[text], dtype=np.float32)
            else:
                # Deterministic fallback: char-sum modulo dim, single-hot.
                idx = sum(ord(c) for c in text) % self._dim
                out[i, idx] = 1.0
        return out

    @property
    def dim(self) -> int:
        return self._dim

    @property
    def name(self) -> str:
        return "fixed-test-embedder"


@pytest.fixture
def small_corpus() -> list[dict[str, object]]:
    return [
        {"source": "NAFEMS_QA01.pdf", "page": 4, "chunk_id": 0,
         "text": "mesh quality criteria require aspect ratio under 5"},
        {"source": "ASME_PTC60.pdf", "page": 12, "chunk_id": 0,
         "text": "wall thickness for SLS printing should exceed 0.8 mm"},
        {"source": "Vendor_whitepaper.pdf", "page": 1, "chunk_id": 0,
         "text": "stress concentration factors near sharp internal corners"},
    ]


@pytest.fixture
def aligned_embedder(small_corpus) -> FixedEmbedder:
    """Each corpus text gets its own basis vector + queries align with one of them."""
    mapping = {
        small_corpus[0]["text"]: [1.0, 0.0, 0.0, 0.0],
        small_corpus[1]["text"]: [0.0, 1.0, 0.0, 0.0],
        small_corpus[2]["text"]: [0.0, 0.0, 1.0, 0.0],
        "mesh quality": [1.0, 0.0, 0.0, 0.0],
        "wall thickness": [0.0, 1.0, 0.0, 0.0],
        "stress concentration": [0.0, 0.0, 1.0, 0.0],
    }
    return FixedEmbedder(mapping=mapping, dim=4)


def test_build_index_shape_matches_corpus(small_corpus, aligned_embedder) -> None:
    index = rag.build_index(small_corpus, aligned_embedder)
    assert len(index.entries) == 3
    assert index.embeddings.shape == (3, 4)
    assert index.meta["dim"] == 4
    assert index.meta["n_chunks"] == 3
    # Embeddings must be unit-normalized.
    norms = np.linalg.norm(index.embeddings, axis=1)
    np.testing.assert_allclose(norms, 1.0, atol=1e-6)


def test_build_index_drops_empty_text(aligned_embedder) -> None:
    chunks = [
        {"source": "a.pdf", "page": 1, "chunk_id": 0, "text": ""},
        {"source": "a.pdf", "page": 2, "chunk_id": 1, "text": "real text"},
        {"source": "a.pdf", "page": 3, "chunk_id": 2, "text": "   "},
    ]
    index = rag.build_index(chunks, aligned_embedder)
    assert len(index.entries) == 1
    assert index.entries[0]["text"] == "real text"


def test_search_returns_top_match_with_citation(small_corpus, aligned_embedder) -> None:
    index = rag.build_index(small_corpus, aligned_embedder)
    hits = index.search("mesh quality", embedder=aligned_embedder, top_k=2)
    assert len(hits) == 2
    assert hits[0]["source"] == "NAFEMS_QA01.pdf"
    assert hits[0]["page"] == 4
    assert "aspect ratio" in hits[0]["text"]
    assert hits[0]["score"] == pytest.approx(1.0, abs=1e-5)
    # Second hit must score lower than first (orthogonal basis -> 0).
    assert hits[1]["score"] < hits[0]["score"]


def test_search_top_k_caps_at_corpus_size(small_corpus, aligned_embedder) -> None:
    index = rag.build_index(small_corpus, aligned_embedder)
    hits = index.search("mesh quality", embedder=aligned_embedder, top_k=99)
    assert len(hits) == 3


def test_search_empty_query_returns_empty(small_corpus, aligned_embedder) -> None:
    index = rag.build_index(small_corpus, aligned_embedder)
    assert index.search("", embedder=aligned_embedder) == []
    assert index.search("   ", embedder=aligned_embedder) == []


def test_search_on_empty_index_returns_empty(aligned_embedder) -> None:
    empty = rag.build_index([], aligned_embedder)
    assert empty.search("anything", embedder=aligned_embedder) == []


def test_save_and_load_roundtrip(tmp_path, small_corpus, aligned_embedder) -> None:
    index = rag.build_index(small_corpus, aligned_embedder)
    path = tmp_path / "idx.json"
    index.save(path)
    assert path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["meta"]["n_chunks"] == 3
    assert len(payload["entries"]) == 3
    assert len(payload["embeddings"]) == 3

    reloaded = rag.RagIndex.load(path)
    assert reloaded.entries == index.entries
    np.testing.assert_allclose(reloaded.embeddings, index.embeddings, atol=1e-6)
    # Search still produces the same top hit after round-trip.
    hits = reloaded.search("mesh quality", embedder=aligned_embedder, top_k=1)
    assert hits[0]["source"] == "NAFEMS_QA01.pdf"


def test_load_missing_file_raises(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        rag.RagIndex.load(tmp_path / "nope.json")


def test_index_constructor_rejects_length_mismatch() -> None:
    with pytest.raises(ValueError):
        rag.RagIndex(
            entries=[{"source": "a.pdf", "text": "x"}],
            embeddings=np.zeros((2, 4), dtype=np.float32),
        )


def test_lookup_standard_returns_ok_with_real_index(
    monkeypatch, tmp_path, small_corpus, aligned_embedder
) -> None:
    """Wire a real (synthetic) index via env override and confirm the tool returns hits."""
    index = rag.build_index(small_corpus, aligned_embedder)
    index_path = tmp_path / "fea_docs_index.json"
    index.save(index_path)

    monkeypatch.setenv("SIMREADY_RAG_INDEX", str(index_path))
    monkeypatch.setattr(rag, "DEFAULT_INDEX_PATH", index_path)
    rag.clear_index_cache()
    rag.set_default_embedder(aligned_embedder)
    try:
        result = tools.lookup_standard("mesh quality", top_k=2)
    finally:
        rag.set_default_embedder(None)
        rag.clear_index_cache()

    assert result["status"] == "ok"
    assert result["query"] == "mesh quality"
    assert len(result["results"]) == 2
    assert result["results"][0]["source"] == "NAFEMS_QA01.pdf"
    assert result["index_meta"]["n_chunks"] == 3
