"""RAG-lite over indexed FEA standards documents.

Index format (JSON on disk):

    {
        "meta": {"model": "sentence-transformers/all-MiniLM-L6-v2", "dim": 384,
                  "created_at": "...", "n_chunks": 312},
        "entries": [
            {"source": "NAFEMS_QA01.pdf", "page": 4, "chunk_id": 12,
             "text": "Mesh quality criteria ..."},
            ...
        ],
        "embeddings": [[float, ...], ...]   # L2-normalized, parallel to entries
    }

Search uses pure-numpy cosine similarity (since vectors are normalized,
similarity = dot product).

The default Embedder wraps sentence-transformers (CPU-friendly,
~80 MB MiniLM model). Tests inject a stub Embedder to avoid model download.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Protocol

import numpy as np


DEFAULT_MODEL_NAME = os.environ.get(
    "SIMREADY_RAG_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
)
DEFAULT_INDEX_PATH = Path("data/fea_docs_index.json")


class Embedder(Protocol):
    """Anything that can turn a list of strings into an (n, d) float array."""

    def embed(self, texts: list[str]) -> np.ndarray: ...

    @property
    def dim(self) -> int: ...

    @property
    def name(self) -> str: ...


class SentenceTransformerEmbedder:
    """Lazy wrapper around sentence-transformers. Loads the model on first use."""

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME) -> None:
        self._model_name = model_name
        self._model: Any | None = None
        self._dim: int | None = None

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "sentence-transformers not installed. Run: pip install sentence-transformers"
            ) from exc
        self._model = SentenceTransformer(self._model_name)
        self._dim = int(self._model.get_sentence_embedding_dimension())

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        self._ensure_model()
        vectors = self._model.encode(  # type: ignore[union-attr]
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return np.asarray(vectors, dtype=np.float32)

    @property
    def dim(self) -> int:
        self._ensure_model()
        assert self._dim is not None
        return self._dim

    @property
    def name(self) -> str:
        return self._model_name


def _normalize(vectors: np.ndarray) -> np.ndarray:
    """L2-normalize each row. Zero rows stay zero (avoid divide-by-zero)."""
    if vectors.size == 0:
        return vectors
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return (vectors / norms).astype(np.float32)


@dataclass
class RagIndex:
    """In-memory FEA-docs index. Use .search() for retrieval."""

    entries: list[dict[str, Any]]
    embeddings: np.ndarray  # shape (n, d), L2-normalized
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if len(self.entries) != len(self.embeddings):
            raise ValueError(
                f"entries ({len(self.entries)}) and embeddings ({len(self.embeddings)}) "
                "length mismatch"
            )

    @classmethod
    def load(cls, path: str | Path) -> "RagIndex":
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"RAG index not found at {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        embeddings = np.asarray(data.get("embeddings", []), dtype=np.float32)
        if embeddings.ndim == 1 and embeddings.size == 0:
            embeddings = embeddings.reshape(0, 0)
        return cls(
            entries=list(data.get("entries", [])),
            embeddings=_normalize(embeddings),
            meta=dict(data.get("meta", {})),
        )

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "meta": self.meta,
            "entries": self.entries,
            "embeddings": self.embeddings.tolist(),
        }
        path.write_text(json.dumps(payload), encoding="utf-8")

    def search(
        self,
        query: str,
        embedder: Embedder,
        top_k: int = 3,
    ) -> list[dict[str, Any]]:
        if not query or not query.strip():
            return []
        if len(self.entries) == 0:
            return []
        query_vec = embedder.embed([query])
        if query_vec.size == 0:
            return []
        query_vec = _normalize(query_vec)[0]
        scores = self.embeddings @ query_vec  # cosine because both normalized
        k = max(1, min(top_k, len(self.entries)))
        top_idx = np.argpartition(-scores, k - 1)[:k]
        top_idx = top_idx[np.argsort(-scores[top_idx])]
        results: list[dict[str, Any]] = []
        for idx in top_idx:
            entry = self.entries[int(idx)]
            results.append({
                "source": entry.get("source", "unknown"),
                "page": entry.get("page"),
                "chunk_id": entry.get("chunk_id"),
                "text": entry.get("text", ""),
                "score": float(scores[int(idx)]),
            })
        return results


def build_index(
    chunks: Iterable[dict[str, Any]],
    embedder: Embedder,
) -> RagIndex:
    """Embed an iterable of chunk dicts and return an indexed RagIndex.

    Each chunk dict must include at least `source` and `text`.
    """
    entries = [dict(c) for c in chunks if c.get("text", "").strip()]
    texts = [e["text"] for e in entries]
    if not entries:
        meta = {
            "model": embedder.name,
            "dim": embedder.dim if texts else 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "n_chunks": 0,
        }
        return RagIndex(entries=[], embeddings=np.zeros((0, 0), dtype=np.float32), meta=meta)
    vectors = _normalize(embedder.embed(texts))
    meta = {
        "model": embedder.name,
        "dim": int(vectors.shape[1]),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "n_chunks": len(entries),
    }
    return RagIndex(entries=entries, embeddings=vectors, meta=meta)


_INDEX_CACHE: dict[str, RagIndex] = {}


def get_default_index(path: str | Path | None = None) -> RagIndex:
    """Load (and cache) the default RAG index. Raises FileNotFoundError if missing."""
    resolved = Path(path or os.environ.get("SIMREADY_RAG_INDEX", DEFAULT_INDEX_PATH))
    key = str(resolved.resolve()) if resolved.exists() else str(resolved)
    if key not in _INDEX_CACHE:
        _INDEX_CACHE[key] = RagIndex.load(resolved)
    return _INDEX_CACHE[key]


def clear_index_cache() -> None:
    """Drop the in-process index cache. Useful for tests."""
    _INDEX_CACHE.clear()


_DEFAULT_EMBEDDER: Embedder | None = None


def get_default_embedder() -> Embedder:
    """Singleton SentenceTransformerEmbedder. Loads model on first .embed() call."""
    global _DEFAULT_EMBEDDER
    if _DEFAULT_EMBEDDER is None:
        _DEFAULT_EMBEDDER = SentenceTransformerEmbedder()
    return _DEFAULT_EMBEDDER


def set_default_embedder(embedder: Embedder | None) -> None:
    """Inject (or reset) the default embedder. Tests use this for stubs."""
    global _DEFAULT_EMBEDDER
    _DEFAULT_EMBEDDER = embedder
