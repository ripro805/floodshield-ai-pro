"""Schema bootstrap helpers for the RAG tables.

We split schema work across two layers:

1. SQLAlchemy `Base.metadata.create_all()` -- creates the `rag_documents`
   and `rag_chunks` tables (with the `vector(384)` column on chunks).

2. Raw DDL -- the HNSW index on the embedding column.  SQLAlchemy can't
   declare pgvector operator classes from declarative metadata, so we run
   `CREATE EXTENSION IF NOT EXISTS vector` and
   `CREATE INDEX IF NOT EXISTS ... USING hnsw (embedding vector_cosine_ops)`
   once at startup.  Both statements are safe no-ops if they already ran.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


HNSW_INDEX_DDL = """
CREATE INDEX IF NOT EXISTS rag_chunks_embedding_hnsw_idx
ON rag_chunks
USING hnsw (embedding vector_cosine_ops)
"""


def ensure_rag_schema(engine: Engine) -> None:
    """Create pgvector extension, RAG tables, and the HNSW index.

    Idempotent: every statement is `IF NOT EXISTS` and the `Base.metadata`
    call is a no-op when the tables already exist.

    Also applies any inline ALTER TABLE migrations the codebase needs for
    older deployments (e.g. add the `category` column to rag_documents).
    """
    # 1. Enable the pgvector extension first; required for the `vector`
    #    column type and the HNSW index below.
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    # 2. Create the tables -- must happen BEFORE the HNSW index because
    #    the index references the `embedding` column.
    from app.reference_models import Base  # noqa: WPS433 (local import intentional)
    Base.metadata.create_all(engine, tables=[
        Base.metadata.tables["rag_documents"],
        Base.metadata.tables["rag_chunks"],
    ])
    # 3. Inline migrations for older deployments.  Each ADD COLUMN IF NOT
    #    EXISTS statement is idempotent.
    with engine.begin() as conn:
        conn.execute(text(
            "ALTER TABLE rag_documents ADD COLUMN IF NOT EXISTS category VARCHAR(20) "
            "NOT NULL DEFAULT 'medical'"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS rag_documents_category_idx "
            "ON rag_documents (category)"
        ))
    # 4. Mark the assistant-knowledge-base metadata doc so the chatbot can
    #    exclude it from medical queries.
    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE rag_documents SET category = 'metadata' WHERE slug = 'datasets-metadata'"
        ))
        conn.execute(text(
            "UPDATE rag_documents SET category = 'safety' WHERE slug IN ("
            "'flood-health-bd', 'first-aid-evacuation', 'community-reports-wash'"
            ")"
        ))
        conn.execute(text(
            "UPDATE rag_documents SET category = 'medical' WHERE slug IN ("
            "'cholera-who-2023', 'typhoid-dengue-hepatitis-dghs', "
            "'diarrhea-ors-skin', 'leptospirosis-ascii'"
            ")"
        ))
    # 5. Create the HNSW index.  IF NOT EXISTS so re-runs are no-ops.
    with engine.begin() as conn:
        conn.execute(text(HNSW_INDEX_DDL))