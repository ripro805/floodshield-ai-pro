"""
FloodShield AI -- Backend API

Run locally:
    uvicorn app.main:app --reload

Then open http://127.0.0.1:8000/docs for the interactive Swagger UI.
Click "Authorize" and log in (via /auth/login) to try protected endpoints
directly from the browser.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.models_loader import models
from app.database import engine, Base
from app.routers import flood, disease, forecast, risk, recommend, satellite, auth, weather, chatbot, hotspots, sms, locations, monitoring, disease_breakdown
from app.routers import assessment  # /assessment/{district} (per-section full assessment)
from app.routers import history
from app.routers import admin
from app.routers import hospitals
from app.routers import hospitals_directory  # noqa: E402  -- /hospitals/districts-summary, /hospitals, /hospitals/nearby, /hospitals/{id}
from app.routers import hospitals_admin  # noqa: E402  -- /admin/hospitals/import (admin-only CSV import)
from app.routers import hospitals_issues  # noqa: E402  -- /hospitals/{id}/issues (per-hospital issue inbox)
from app.routers import hospitals_admin_inbox  # noqa: E402  -- /admin/hospitals/issues (admin issue inbox)
from app.routers import hospitals_admin_bulk  # noqa: E402  -- /admin/hospitals/issues/status (admin bulk status mutation)
from app.routers import hospitals_issue_rollup  # noqa: E402  -- /hospitals/districts/{district}/issue-rollup (read-only per-district rollup)
from app.routers import hospitals_issue_history  # noqa: E402  -- /hospitals/{id}/issue-history (per-hospital chronological timeline)

import app.history_models  # noqa: F401 -- registers WeeklyHistory with Base.metadata
import app.sms_models  # noqa: F401 -- registers SmsSubscription with Base.metadata
import app.prediction_models  # noqa: F401 -- registers PredictionHistory with Base.metadata
import app.weather_models  # noqa: F401 -- registers WeatherObservation with Base.metadata
import app.reference_models  # noqa: F401 -- registers Location, DistrictEnv, Hospital,
                            # DistrictHospitalAggregate, KnowledgeArticle,
                            # CommunityReport, SatelliteExtent with Base.metadata
import asyncio
from app.services.weather_scheduler import weather_refresh_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load every model artifact ONCE, when the server starts -- not per-request.
    models.load_all()
    # Create the `users` table if it doesn't exist yet. Fine for this project's
    # scale; a larger app would use Alembic migrations instead.
    Base.metadata.create_all(bind=engine)
    # `create_all` only creates *missing* tables -- it doesn't add new
    # columns to tables that already exist.  Run the explicit ALTER
    # migrations so the live DB picks up new columns like
    # `hospitals.district_id` / `hospitals.address` without a manual
    # schema migration step.  Idempotent (each helper uses
    # `ADD COLUMN IF NOT EXISTS`).
    try:
        from app.services.db_migrations import run_db_migrations
        run_db_migrations(engine)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("db_migrations failed: %s", exc)
    # Enable the pgvector extension on Neon Postgres and ensure the RAG
    # tables + HNSW index exist.  Idempotent.
    try:
        from app.rag_schema import ensure_rag_schema
        ensure_rag_schema(engine)
    except Exception as exc:  # pragma: no cover -- startup logging only
        import logging
        logging.getLogger(__name__).warning("RAG schema bootstrap failed: %s", exc)
    # Seed 8 weeks of synthetic-but-realistic weekly history per district so
    # /dashboard/[district] and /dashboard/reports can render the disease
    # outbreak risk and LSTM forecast cards immediately. The seeder only
    # writes for districts with zero existing history rows, so operational
    # data is never overwritten.
    try:
        from app.database import SessionLocal
        from app.services.seed_history import seed_weekly_history_if_empty
        from app.services.seed_reference import seed_reference_data_if_empty
        from app.services.seed_rag import seed_rag_corpus
        import logging
        _logger = logging.getLogger(__name__)
        with SessionLocal() as _session:
            seed_reference_data_if_empty(_session)
            seed_weekly_history_if_empty(_session)
            # Hospital Directory auto-seed (idempotent; honours the
            # AUTO_SEED_ON_EMPTY env flag -- no-op if the hospitals
            # table already has rows).  See app/scripts/seed_hospitals.py.
            try:
                from app.scripts.seed_hospitals import auto_seed_if_empty
                auto_seed_if_empty()
            except Exception as exc:
                _logger.warning("hospital auto-seed failed: %s", exc)
            # RAG seed runs LAST because it is the slowest (model download +
            # embedding).  Errors here are non-fatal -- the chatbot will fall
            # back to the legacy keyword-overlap KB if the RAG corpus is
            # unavailable.
            try:
                rag_summary = seed_rag_corpus(_session)
                _logger.info('RAG seed: %s', rag_summary)
            except Exception as _rag_exc:
                _logger.warning('RAG seed skipped: %s', _rag_exc)
    except Exception as exc:  # pragma: no cover -- startup logging only
        import logging
        logging.getLogger(__name__).warning("startup seed skipped: %s", exc)
    refresh_task = asyncio.create_task(weather_refresh_loop())
    yield
    refresh_task.cancel()
    try:
        await refresh_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="FloodShield AI API",
    description=(
        "AI-powered flood and disease outbreak early-warning platform for Bangladesh. "
        "Wraps Models 1, 2, 3, 5, 6 (trained in Colab) and Model 4 (satellite flood "
        "detection) behind a single REST API for the frontend dashboard, with "
        "JWT authentication and role-based access (citizen, health_worker, "
        "hospital, ngo, government, admin)."
    ),
    version="1.1.0",
    lifespan=lifespan,
)

# Allow the Next.js frontend (any origin during development) to call this API.
# Tighten this to the real frontend domain before production deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(flood.router)
app.include_router(disease.router)
app.include_router(forecast.router)
app.include_router(risk.router)
app.include_router(recommend.router)
app.include_router(satellite.router)
app.include_router(weather.router)
app.include_router(chatbot.router)
app.include_router(hotspots.router)
app.include_router(sms.router)
app.include_router(locations.router)
app.include_router(monitoring.router)
app.include_router(history.router)
app.include_router(admin.router)
app.include_router(hospitals_directory.router)  # MUST come before hospitals.router so /hospitals/districts-summary and /hospitals/nearby don't get caught by /hospitals/{id}
app.include_router(hospitals.router)
app.include_router(hospitals_admin.router)  # /admin/hospitals/import (admin-only CSV import)
app.include_router(hospitals_issues.router)  # /hospitals/{id}/issues (per-hospital issue inbox, all auth'd users)
app.include_router(hospitals_admin_inbox.router)  # /admin/hospitals/issues (admin issue inbox)
app.include_router(hospitals_admin_bulk.router)  # /admin/hospitals/issues/status (bulk ack/resolve/dismiss)
app.include_router(hospitals_issue_rollup.router)  # /hospitals/districts/{district}/issue-rollup
app.include_router(hospitals_issue_history.router)  # /hospitals/{id}/issue-history
app.include_router(disease_breakdown.router)
app.include_router(disease_breakdown.router)
app.include_router(assessment.router)  # /assessment/{district} (full per-section assessment)


@app.get("/", tags=["Health"])
def health_check():
    return {
        "status": "ok",
        "service": "FloodShield AI API",
        "models_loaded": models.loaded,
    }

