"""Embedding model wrapper.

Uses `fastembed` (ONNX runtime, no torch) so the package footprint stays
small -- the alternative, sentence-transformers, pulls ~500MB of PyTorch
which is painful on free-tier deploys.  We initialise the model lazily on
first use so the backend boot path stays clean (the model download happens
on the first ingest, not on every uvicorn reload).
"""
from __future__ import annotations

import os
import threading
from typing import Iterable, Sequence

# Embedding model choice: all-MiniLM-L6-v2 is 384-dim, fast, well-tested on
# short medical/government text.  Override via RAG_EMBED_MODEL env var if a
# team wants to swap to multilingual-e5-small (for Bangla support).
DEFAULT_MODEL = os.getenv("RAG_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
EMBEDDING_DIM = 384


_lock = threading.Lock()
_model = None


def _get_model():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                from fastembed import TextEmbedding
                _model = TextEmbedding(DEFAULT_MODEL)
    return _model


def embed_texts(texts: Sequence[str]) -> list[list[float]]:
    """Return one 384-dim float list per input string.

    fastembed returns numpy arrays; we serialise to plain lists so SQLAlchemy
    can hand them straight to pgvector.
    """
    model = _get_model()
    vectors: list[list[float]] = []
    # fastembed supports a list input but yields a generator; normalise.
    for arr in model.embed(list(texts)):
        vectors.append([float(x) for x in arr])
    return vectors


def embed_query(text: str) -> list[float]:
    """Convenience for the one-shot query embed at retrieval time."""
    return embed_texts([text])[0]