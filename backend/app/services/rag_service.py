"""Real vector retrieval over the RAG corpus in Neon (pgvector).

The pipeline:

    user query
       │
       ▼  embed_query()
    384-dim vector
       │
       ▼  cosine nearest-neighbour (pgvector HNSW)
    top-K RagChunk rows
       │
       ▼  format with source title + chunk text
    grounded context string

The result is concatenated and forwarded to the LLM as part of the
system prompt.  Falls back to the legacy keyword-overlap ranking
when the RAG tables are empty (e.g. first cold-start before the
seeder has run).
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.knowledge_base import MEDICAL_KNOWLEDGE_BASE

logger = logging.getLogger("floodshield.rag")


def _legacy_keyword_retrieval(query: str, limit: int = 3) -> str:
    """Original term-overlap fallback.  Used only when rag_chunks is empty."""
    corpus = MEDICAL_KNOWLEDGE_BASE
    chunks = [c.strip() for c in re.split(r"\n(?=\d+\.)", corpus) if c.strip()]
    terms = set(re.findall(r"[a-zA-Z]+", query.lower()))
    ranked = sorted(
        chunks,
        key=lambda chunk: len(terms.intersection(set(re.findall(r"[a-zA-Z]+", chunk.lower())))),
        reverse=True,
    )
    return "\n".join(ranked[:limit])


def _format_chunks(hits: list[tuple[str, str, float, int]]) -> str:
    """Render a list of (title, chunk_text, distance, chunk_index) into the
    context block the LLM consumes."""
    if not hits:
        return ""
    blocks = []
    for title, chunk_text, _dist, idx in hits:
        blocks.append(
            f"[Source: {title} | Chunk {idx}]\n{chunk_text}"
        )
    return "\n\n---\n\n".join(blocks)


def retrieve_context(
    db: Optional[Session],
    query: str,
    limit: int = 4,
    categories: Optional[list[str]] = None,
) -> str:
    """Top-`limit` chunks of grounding context for `query`.

    By default, EXCLUDES documents in the `metadata` category (those are
    assistant self-knowledge -- about the platform itself, not medical
    advice).  Pass `categories=['medical','district']` (or any subset) to
    restrict further; pass `categories=None` (default) to allow everything
    except metadata.

    Falls back to:
      - the embedded MEDICAL_KNOWLEDGE_BASE if the RAG tables are empty
      - legacy keyword overlap if pgvector is unreachable
    """
    if db is None or not query or not query.strip():
        return _legacy_keyword_retrieval(query, limit)

    # Default: allow medical / safety / district, exclude metadata.
    if categories is None:
        categories = ["medical", "safety", "district"]

    try:
        from app.reference_models import RagChunk
        row_count = db.query(RagChunk).count()
        if row_count == 0:
            logger.info("RAG: empty rag_chunks table, using legacy KB")
            return _legacy_keyword_retrieval(query, limit)

        from app.rag_embedder import embed_query

        query_vec = embed_query(query)
        vec_str = "[" + ",".join(f"{x:.6f}" for x in query_vec) + "]"
        sql = text("""
            SELECT
                d.title,
                c.text,
                c.embedding <=> CAST(:vec AS vector) AS distance,
                c.chunk_index
            FROM rag_chunks c
            JOIN rag_documents d ON d.id = c.document_id
            WHERE d.category = ANY(:cats)
            ORDER BY c.embedding <=> CAST(:vec AS vector)
            LIMIT :limit
        """)
        rows = db.execute(sql, {"vec": vec_str, "limit": limit, "cats": categories}).fetchall()
        hits = [(r[0], r[1], float(r[2]), int(r[3])) for r in rows]
        if not hits:
            return _legacy_keyword_retrieval(query, limit)
        return _format_chunks(hits)
    except Exception as e:
        logger.exception("RAG retrieval failed: %s", e)
        return _legacy_keyword_retrieval(query, limit)


def corpus_stats(db: Session) -> dict:
    """Return a summary of the RAG corpus for /admin/rag/status."""
    doc_count = db.execute(text("SELECT COUNT(*) FROM rag_documents")).scalar() or 0
    chunk_count = db.execute(text("SELECT COUNT(*) FROM rag_chunks")).scalar() or 0
    sources = db.execute(
        text("SELECT source, COUNT(*) FROM rag_documents GROUP BY source")
    ).fetchall()
    return {
        "documents": int(doc_count),
        "chunks": int(chunk_count),
        "sources": [{"source": s[0], "count": int(s[1])} for s in sources],
    }