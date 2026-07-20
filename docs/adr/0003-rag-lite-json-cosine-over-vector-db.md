# ADR 0003 — `lookup_standard`: JSON + Cosine over a Vector DB

- **Status:** Accepted (retro-documented 2026-07-20; decision made 2026-05-14, wk-1)
- **Related:** `simready/copilot/rag.py`, `scripts/index_fea_docs.py`

## Context

The `lookup_standard` tool retrieves FEA-standards passages. The corpus is a handful
of public FEA/meshing documents — order 10 documents, hundreds of chunks, growing
slowly if at all. The reflex choice (Chroma/FAISS/pgvector) adds a service or a
binary dependency to an environment that already fights pythonocc/conda on Windows.

## Decision

RAG-lite: sentence-transformers embeddings serialized to one JSON file, cosine
similarity via numpy at query time. Embeddings are pre-normalized at index time so
query scoring is a single matrix multiply; top-k via `argpartition`. The embedder is
injected behind a small protocol, so tests run with a fake and the index format
doesn't depend on the model choice.

## Consequences

- Zero services, zero native deps beyond numpy; the seed index is committed, so
  `lookup_standard` works on a fresh clone (this closed a real demo-dead-tool gap).
- Full-scan cosine is O(corpus) per query — irrelevant at ≤1k chunks (sub-ms), and the
  honest sizing judgment is itself an interview point: know when you don't need ANN.
- Re-indexing is a full rebuild (`index_fea_docs.py`). Acceptable while corpus changes
  are rare and manual. The switch point to a real vector store is when the corpus
  outgrows memory or needs incremental updates — neither is on the roadmap.
