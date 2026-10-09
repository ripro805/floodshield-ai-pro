"""Document chunking for the RAG pipeline.

The chunker is deliberately simple -- no NLP library, no overlap tuning --
because the source documents are short (~1-3 pages each) and we want a
predictable 1-row-per-paragraph mapping that survives changes to the
underlying PDFs.

Strategy:
  1. Split on blank lines into paragraphs.
  2. Coalesce consecutive short paragraphs (< 60 words) so each chunk is
     dense enough to embed meaningfully (model degrades on fragments).
  3. Cap each chunk at ~120 words / 600 chars so no chunk dominates the
     nearest-neighbour search.

This keeps the corpus at a few hundred rows for the ~10 source documents
we ship, which is well within pgvector's sweet spot (no shard split,
sub-millisecond ANN at HNSW ef=10).
"""
from __future__ import annotations

import re
from typing import Iterable

MAX_WORDS = 120
MAX_CHARS = 600
SOFT_MIN_WORDS = 30


def _split_paragraphs(text: str) -> list[str]:
    """Split on two-or-more newlines, drop empties, strip whitespace."""
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def _word_count(text: str) -> int:
    return len(re.findall(r"\S+", text))


def chunk_document(text: str) -> list[str]:
    """Turn a single document's text into embedding-ready chunks.

    Returns an ordered list of chunk strings; `len(chunks)` becomes the
    `chunk_index` in the DB.
    """
    paragraphs = _split_paragraphs(text)
    chunks: list[str] = []

    buffer: list[str] = []
    buffer_words = 0

    def flush() -> None:
        nonlocal buffer, buffer_words
        if buffer:
            joined = "\n\n".join(buffer).strip()
            if joined:
                chunks.append(joined)
        buffer = []
        buffer_words = 0

    for para in paragraphs:
        words = _word_count(para)

        # If the paragraph itself is over the cap, hard-split on sentences.
        if words > MAX_WORDS or len(para) > MAX_CHARS:
            flush()
            sentences = re.split(r"(?<=[.!?])\s+", para)
            sub_buf: list[str] = []
            sub_words = 0
            for sent in sentences:
                sent_words = _word_count(sent)
                if sub_words + sent_words > MAX_WORDS and sub_buf:
                    chunks.append(" ".join(sub_buf).strip())
                    sub_buf = [sent]
                    sub_words = sent_words
                else:
                    sub_buf.append(sent)
                    sub_words += sent_words
            if sub_buf:
                chunks.append(" ".join(sub_buf).strip())
            continue

        if buffer_words + words > MAX_WORDS or sum(len(p) for p in buffer) + len(para) > MAX_CHARS:
            flush()

        buffer.append(para)
        buffer_words += words

    flush()
    return [c for c in chunks if c]