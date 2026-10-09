# RAG (Retrieval-Augmented Generation) — How FloodShield's Chatbot Answers

The chatbot no longer relies on a single 6-row knowledge base that was
hard-coded into the system prompt.  It now uses a real vector retrieval
pipeline backed by **pgvector** on Neon Postgres.

## Architecture

```
   user query
      │
      ▼ embed_query()                     ← all-MiniLM-L6-v2 (fastembed / ONNX)
   384-dim vector
      │
      ▼ pgvector HNSW index (cosine)
   top-K rag_chunks rows
      │
      ▼ format with [Source: ... | Chunk N]
   grounded context block
      │
      ▼ Anthropic Claude (or local Ollama/HF) — system prompt contains:
       # PRIMARY CONTEXT (RAG)
       {retrieved_context}
       # SUPPLEMENTARY
       {legacy 6-disease card}
       # RULES
       Prefer RAG, cite sources, escalate emergencies to 999
```

## Corpus

8 source documents, ~105 chunks total, all stored in Neon (`rag_documents`
+ `rag_chunks` tables):

| Source     | Title                                                |
| ---------- | ---------------------------------------------------- |
| WHO        | Cholera: Clinical Management and Outbreak Control 2023 |
| DGHS       | Typhoid, Dengue, Hepatitis A/E — DGHS Protocols      |
| WHO/IMCI   | Acute Diarrhoea, ORS, Zinc, Skin Disease in Floods   |
| FloodShield | Flood-Related Health Risks and Public Health Response |
| FloodShield | Emergency First Aid and Evacuation During Floods     |
| FloodShield | Community Reports and WASH                            |
| FloodShield | Dataset Metadata (9 datasets)                        |
| FloodShield | Leptospirosis, Post-Flood Zoonoses, Breastfeeding    |

Sources are flat-text only — adding a new PDF is just a matter of
dropping it into `data/rag_corpus/` and adding a row to
`_manifest.json`.

## Key components

| File                                          | Role                                          |
| --------------------------------------------- | --------------------------------------------- |
| `app/reference_models.py` (`RagDocument`, `RagChunk`) | SQLAlchemy tables + pgvector column    |
| `app/rag_schema.py`                           | Idempotent CREATE EXTENSION + table + HNSW    |
| `app/rag_embedder.py`                         | fastembed wrapper (model lazy-load, 384-dim)  |
| `app/rag_chunker.py`                          | Paragraph split + sentence-window hard split  |
| `app/services/seed_rag.py`                    | Idempotent seeder (skip existing slugs)       |
| `app/services/rag_service.py`                 | Real pgvector cosine retrieval + legacy fallback |
| `app/routers/chatbot.py` (LLM system prompt)  | Uses RAG context as PRIMARY, KB as SUPPLEMENTARY |
| `app/routers/admin.py`                        | `/admin/rag/status`, `/ingest`, `/rebuild`, `/retrieve` |

## Admin endpoints

```
GET  /admin/rag/status           -- documents, chunks, per-source counts
POST /admin/rag/ingest           -- re-run seeder (skip existing slugs)
POST /admin/rag/rebuild          -- drop tables + recreate + re-seed
POST /admin/rag/retrieve         -- debug endpoint showing the top-K chunks
                                   that would be sent to the LLM for a query
```

All admin endpoints require the `admin` role.

## Deployment notes

- **pgvector extension** is auto-enabled via `ensure_rag_schema()` at
  backend startup.
- **fastembed model** downloads on first use (~100 MB ONNX, cached on
  disk).  The Dockerfile pre-warms the cache so the first chat request
  is fast.
- **Seed runs once** at backend startup.  Idempotent — safe to run on
  every restart.
- **Adding new documents**: drop a `.txt` file into `data/rag_corpus/`
  and add a row to `_manifest.json`.  Restart the backend (or call
  `POST /admin/rag/ingest`) to embed and insert.  No re-build of the
  index required.
- **Embedding model swap**: set `RAG_EMBED_MODEL=<other-model>` env var.
  Note: only models with **384-dim** outputs work with the existing
  schema unless you also migrate the column dimension.  Call
  `POST /admin/rag/rebuild` after changing.

## Local dev quick-start

```bash
# 1. Ensure pgvector is enabled (idempotent)
psql $DATABASE_URL -c "CREATE EXTENSION IF NOT EXISTS vector"

# 2. Start the backend -- the lifespan handler will create tables,
#    build the HNSW index, and seed the corpus.
uvicorn app.main:app --reload
```

## Verifying retrieval

```
POST /admin/rag/retrieve
{
  "query": "What is the cholera treatment protocol?",
  "limit": 3
}

=> 200 OK
{
  "query": "What is the cholera treatment protocol?",
  "limit": 3,
  "corpus_size": 105,
  "chunks": [
    { "title": "Cholera: Clinical Management ...", "chunk_index": 10, "distance": 0.276, "preview": "Cholera is treatable and preventable..." },
    { "title": "Cholera: Clinical Management ...", "chunk_index":  6, "distance": 0.284, "preview": "The pillars of cholera outbreak response..." },
    { "title": "Cholera: Clinical Management ...", "chunk_index":  0, "distance": 0.332, "preview": "CHOLERA: CLINICAL MANAGEMENT ..." }
  ],
  "context_block": "[Source: Cholera ... | Chunk 10]\nCholera is treatable...\n\n---\n\n..."
}
```

Cosine distance ~0.27 = highly relevant; ~0.4 = related topic;
>0.6 = probably irrelevant.

## Fallback behaviour

If `rag_chunks` is empty (e.g. before the first seeder run) OR if pgvector
is unreachable, `retrieve_context` falls back to the original
keyword-overlap ranking against `MEDICAL_KNOWLEDGE_BASE` (the 6-disease
card).  The chatbot will keep working without RAG, just with the legacy
shorter context.