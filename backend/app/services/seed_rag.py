"""Seed the RAG corpus from `data/rag_corpus/`.

The seeder is idempotent -- it skips documents whose slug already exists
in `rag_documents`, so re-runs are safe.

First-time run will download the all-MiniLM-L6-v2 ONNX weights via
fastembed and embed every paragraph.  That's a one-time cost (~30s on
a modern laptop, dominated by the model download) and is cached on disk
for subsequent runs.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Iterable

from sqlalchemy.orm import Session

from app.reference_models import RagChunk, RagDocument

logger = logging.getLogger("floodshield.seed_rag")


def _repo_root() -> Path:
    """Resolve the absolute path to the repo root, regardless of CWD."""
    return Path(__file__).resolve().parents[2]  # backend/app/services -> backend/app -> backend -> repo


def _corpus_dir() -> Path:
    """Try a couple of plausible locations for the corpus folder."""
    candidates = [
        _repo_root() / "data" / "rag_corpus",       # repo-root layout
        _repo_root() / "backend" / "data" / "rag_corpus",  # backend/data layout
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(
        f"rag_corpus not found. Looked in: {[str(c) for c in candidates]}"
    )


def _existing_slugs(db: Session) -> set[str]:
    return {row[0] for row in db.query(RagDocument.slug).all()}


def seed_rag_corpus(db: Session) -> dict:
    """Insert every document in the manifest that is not yet in the DB.

    Returns a summary dict {"documents_added": int, "chunks_added": int,
    "skipped": int}.
    """
    manifest_path = _corpus_dir() / "_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing manifest at {manifest_path}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    existing = _existing_slugs(db)
    documents = manifest["documents"]

    # Lazy import so the embedder is only loaded when we actually need it.
    from app.rag_chunker import chunk_document
    from app.rag_embedder import embed_texts

    added_docs = 0
    added_chunks = 0
    skipped = 0

    for doc_meta in documents:
        slug = doc_meta["slug"]
        if slug in existing:
            skipped += 1
            continue

        file_path = _corpus_dir() / doc_meta["filename"]
        if not file_path.exists():
            logger.warning("RAG: missing file %s for slug %s", file_path, slug)
            continue

        text = file_path.read_text(encoding="utf-8")
        chunks = chunk_document(text)
        if not chunks:
            logger.warning("RAG: zero chunks for %s, skipping", slug)
            continue

        embeddings = embed_texts(chunks)

        document = RagDocument(
            source=doc_meta["source"],
            title=doc_meta["title"],
            slug=slug,
            language=doc_meta.get("language", "en"),
            category=doc_meta.get("category", "medical"),
            description=doc_meta.get("description"),
        )
        db.add(document)
        db.flush()  # populate document.id

        for idx, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            chunk = RagChunk(
                document_id=document.id,
                chunk_index=idx,
                text=chunk_text,
                embedding=embedding,
                token_estimate=len(chunk_text.split()),
            )
            db.add(chunk)
            added_chunks += 1

        added_docs += 1
        logger.info(
            "RAG: seeded %s (%d chunks)", slug, len(chunks)
        )

    db.commit()
    return {
        "documents_added": added_docs,
        "chunks_added": added_chunks,
        "skipped": skipped,
        "total_documents_in_db": len(existing) + added_docs,
    }