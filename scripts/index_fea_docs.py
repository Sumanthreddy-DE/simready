"""Build the SimReady RAG index from PDFs in data/fea_docs/.

Pipeline:
    1. For each PDF, read pages with pypdf.
    2. Split each page on blank-line boundaries → raw paragraphs.
    3. Merge runts < MIN_CHARS into the previous chunk.
    4. Hard-split chunks > MAX_CHARS at sentence-ish boundaries.
    5. Embed all chunks via simready.copilot.rag.SentenceTransformerEmbedder.
    6. Write data/fea_docs_index.json.

Run:
    python scripts/index_fea_docs.py
    python scripts/index_fea_docs.py --input data/fea_docs --output data/fea_docs_index.json
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Iterator

from pypdf import PdfReader

from simready.copilot.rag import (
    DEFAULT_INDEX_PATH,
    SentenceTransformerEmbedder,
    build_index,
)


DEFAULT_INPUT = Path("data/fea_docs")
MIN_CHARS = 200
MAX_CHARS = 1500
PARAGRAPH_SPLIT = re.compile(r"\n\s*\n+")
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z(])")


def iter_chunks_for_pdf(pdf_path: Path) -> Iterator[dict[str, object]]:
    """Yield {source, page, chunk_id, text} dicts for a single PDF."""
    try:
        reader = PdfReader(str(pdf_path))
    except Exception as exc:
        print(f"  WARN  failed to open {pdf_path.name}: {exc}", flush=True)
        return

    chunk_id = 0
    for page_idx, page in enumerate(reader.pages, start=1):
        try:
            raw = page.extract_text() or ""
        except Exception as exc:
            print(f"  WARN  page {page_idx} of {pdf_path.name}: {exc}", flush=True)
            continue
        if not raw.strip():
            continue
        for chunk_text in _chunk_page(raw):
            yield {
                "source": pdf_path.name,
                "page": page_idx,
                "chunk_id": chunk_id,
                "text": chunk_text,
            }
            chunk_id += 1


def _chunk_page(text: str) -> Iterator[str]:
    """Split a page into chunks of [MIN_CHARS, MAX_CHARS] characters."""
    paragraphs = [p.strip() for p in PARAGRAPH_SPLIT.split(text) if p.strip()]
    buffer = ""
    for para in paragraphs:
        if not buffer:
            buffer = para
        elif len(buffer) < MIN_CHARS:
            buffer = f"{buffer}\n\n{para}"
        else:
            yield from _split_long(buffer)
            buffer = para
    if buffer:
        yield from _split_long(buffer)


def _split_long(text: str) -> Iterator[str]:
    """Yield text whole if <= MAX_CHARS, otherwise split on sentence boundaries."""
    text = text.strip()
    if not text:
        return
    if len(text) <= MAX_CHARS:
        yield text
        return
    sentences = SENTENCE_SPLIT.split(text)
    chunk = ""
    for sentence in sentences:
        candidate = f"{chunk} {sentence}".strip() if chunk else sentence
        if len(candidate) <= MAX_CHARS:
            chunk = candidate
        else:
            if chunk:
                yield chunk
            if len(sentence) <= MAX_CHARS:
                chunk = sentence
            else:
                # No sentence boundaries — fall back to hard slice.
                for i in range(0, len(sentence), MAX_CHARS):
                    piece = sentence[i:i + MAX_CHARS]
                    if i + MAX_CHARS >= len(sentence):
                        chunk = piece
                    else:
                        yield piece
    if chunk:
        yield chunk


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT,
                        help=f"Input directory of PDFs (default: {DEFAULT_INPUT})")
    parser.add_argument("--output", type=Path, default=DEFAULT_INDEX_PATH,
                        help=f"Output index JSON (default: {DEFAULT_INDEX_PATH})")
    parser.add_argument("--model", type=str, default=None,
                        help="Override embedding model name (env SIMREADY_RAG_MODEL also works)")
    args = parser.parse_args(argv)

    if not args.input.exists():
        print(f"Input dir {args.input} missing. Run scrape_fea_docs.py first.", flush=True)
        return 1

    pdfs = sorted(args.input.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {args.input}. Drop some files in and re-run.", flush=True)
        return 1

    print(f"Indexing {len(pdfs)} PDF(s)...", flush=True)
    chunks: list[dict[str, object]] = []
    for pdf in pdfs:
        before = len(chunks)
        chunks.extend(iter_chunks_for_pdf(pdf))
        print(f"  {pdf.name}: {len(chunks) - before} chunk(s)", flush=True)

    if not chunks:
        print("No text extracted from any PDF. Index NOT written.", flush=True)
        return 1

    embedder = SentenceTransformerEmbedder(args.model) if args.model else SentenceTransformerEmbedder()
    print(f"Embedding {len(chunks)} chunks via {embedder.name}...", flush=True)
    index = build_index(chunks, embedder)
    index.save(args.output)
    print(f"Wrote {args.output} (n_chunks={index.meta['n_chunks']}, dim={index.meta['dim']})",
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
