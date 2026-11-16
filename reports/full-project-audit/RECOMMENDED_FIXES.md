# Recommended Fixes & Production Hardening Guide: FloodShield AI Pro

**Date**: November 16, 2026  
**Auditor**: Senior Software Reliability & Architecture Engineer  
**Objective**: Clear, actionable architectural recommendations to transition the project from staging/demo grade to production-grade resilience.

---

## 1. High-Priority Hardening Recommendations

### 1.1 Centralized Model Feature Pipeline (Prevent Schema Drift)
- **Current State**:
  Feature dictionaries are assembled individually in `flood.py`, `disease.py`, and `disease_breakdown.py`. While default fallbacks have now been implemented, changes in training features could introduce schema mismatch.
- **Recommendation**:
  Consolidate feature extraction into a single shared service (e.g. `backend/app/services/feature_builder.py`) with a strict Pydantic model validator, ensuring all models share identical baseline transformations and imputation logic.

### 1.2 Database Connection Pooling & Reconnect Retries
- **Current State**:
  FastAPI relies on SQLAlchemy `engine` connecting directly to Neon Serverless Postgres. During idle periods or cold starts, Neon serverless compute instances may spin down, occasionally causing a 1–2 second delay on initial queries.
- **Recommendation**:
  Configure SQLAlchemy connection pool with `pool_pre_ping=True` and `pool_recycle=300`:
  ```python
  engine = create_engine(
      DATABASE_URL,
      pool_pre_ping=True,
      pool_recycle=300,
      pool_size=10,
      max_overflow=20
  )
  ```

### 1.3 Asynchronous Non-Blocking Seed Initialization
- **Current State**:
  In `main.py`'s `lifespan` handler, `seed_rag_corpus` runs synchronously during application startup, taking 10–15 seconds to download/verify embeddings before uvicorn binds to port 8000.
- **Recommendation**:
  Offload the corpus verification and heavy embedding model warm-up into a background startup task (`asyncio.create_task(warmup_rag_cache())`) so uvicorn binds to port 8000 immediately, satisfying container health check probes (e.g., Kubernetes liveness/readiness probes, Docker healthchecks).

---

## 2. Medium-Priority Enhancements

### 2.1 Automated CI/CD Regression Pipeline
- Integrate the newly established Playwright and Pytest suites into GitHub Actions / GitLab CI:
  - Trigger pytest on every pull request against `tests_audit/`.
  - Trigger Playwright smoke and RBAC tests before production deployments.
  - Fail pipeline immediately if any role-boundary check or 500 error occurs.

### 2.2 Client-Side Global Error Boundary
- Wrap dynamic dashboard charts (such as Leaflet maps and Recharts LSTM forecast graphs) in granular React `<ErrorBoundary>` components with friendly fallback cards, ensuring that unexpected third-party map tile delays do not crash parent dashboard layouts.
