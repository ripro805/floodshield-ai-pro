# FloodShield AI Pro — Automation Before Changes (Baseline Audit)

## 1. Executive Summary

This document audits the baseline automation architecture of FloodShield AI Pro before the integration of the n8n hybrid automation system. The project already possesses a production-grade Native Backend Automation Engine operating entirely inside FastAPI and PostgreSQL. 

The primary architectural objective is **Zero Breakage**: preserve every existing native job handler, background worker, database model, API endpoint, and scheduling mechanism, while augmenting the system with an intelligent, fault-tolerant n8n hybrid routing layer.

---

## 2. Existing Native Automation Architecture

### 2.1 Native Automation Engine (`backend/app/services/automation_engine.py`)
The native engine is an asynchronous, periodic scheduling system running natively inside the FastAPI lifespan loop (`automation_engine_loop`). It executes without requiring any external orchestrator or Docker dependency.

#### Core Job Registry (`REGISTERED_JOBS`):
1. **`weather_collector`** (Interval: 14,400s / 4 hours)
   - Ingests real-time meteorology and hydrology for monitored districts (temperature, humidity, precipitation, river stage, water quality index).
   - Persists observations directly to the `weather_observations` table.
2. **`scheduled_district_predictions`** (Interval: 21,600s / 6 hours)
   - Performs periodic health risk evaluation and rainfall trend analysis across disaster-prone divisions in Bangladesh.
3. **`risk_monitor`** (Interval: 3,600s / 1 hour)
   - Scans recent hydrometric records for severe thresholds (rainfall > 70.0 mm or critical river surge).
   - Automatically drafts bilingual emergency warnings in the `official_alerts` table for administrative review.
4. **`inventory_monitor`** (Interval: 1,800s / 30 minutes)
   - Inspects `hospital_inventory_items` and `ngo_inventory_items` against safety thresholds (`current_stock < min_threshold`).
   - Flags critical shortages (`is_critical_shortage = True`) in real time.
5. **`unresolved_issues_escalator`** (Interval: 7,200s / 2 hours)
   - Queries `resource_requests` pending unreviewed for more than 24 hours and elevates their urgency from `normal` to `urgent`.

### 2.2 Independent Weather Scheduler (`backend/app/services/weather_scheduler.py`)
- Executes `weather_refresh_loop()` as an independent background task in FastAPI lifespan.
- Runs periodic hydrometric queries against OpenWeatherMap / Open-Meteo across 64 districts.

### 2.3 Legacy Incident Notification Helper (`backend/app/services/automation_service.py`)
- Provides `notify_n8n(event)` used for incident workflow webhooks.
- Operates on a simple best-effort HTTP POST without execution tracking, health caching, or automated fallback.

---

## 3. Database Schema & State Tracking (`backend/app/operation_models.py`)

The existing database utilizes PostgreSQL (Neon Serverless) and SQLAlchemy ORM:
- **`automation_jobs`**: Contains job definitions, intervals, run counters (`total_runs`, `success_runs`, `failure_runs`), execution durations (`last_duration_seconds`), timestamps (`last_run_at`, `next_run_at`), and status flags.
- **`audit_events`**: Immutable audit trail recording user and system actions.
- **`official_alerts`**: System-generated and government-approved crisis announcements.
- **`hospital_inventory_items`** & **`ngo_inventory_items`**: Track medical supplies and emergency rations.
- **`resource_requests`**: Inter-agency requisitions subject to automated escalation.

---

## 4. Admin Management & API Layer (`backend/app/routers/automation_admin.py`)

The backend exposes administrative endpoints:
- `GET /admin/jobs`: Lists all registered automation jobs, health metrics, and last run stats.
- `POST /admin/jobs/{job_name}/run-now`: Triggers an immediate execution of any registered job on demand.
- `GET /admin/audit-logs`: Retrieves system-wide audit event trails with filtering.

---

## 5. Docker & Deployment Configuration (`docker-compose.yml`)

The multi-container Docker configuration orchestrates:
- `backend`: FastAPI service exposed on port `8000`.
- `frontend`: Next.js 14 service exposed on port `3000`.
- Optional `postgres`: Local PostgreSQL container alternative.

---

## 6. Pre-Change Dependencies & Invariants

1. **Self-Sufficiency**: Native automation executes seamlessly even if Docker is not installed or n8n is offline.
2. **Data Integrity**: Database constraints prevent duplicate concurrent job execution.
3. **Auditability**: Every execution logs duration, status, and error states.
4. **Zero-Breakage Mandate**: The native handlers in `automation_engine.py` will remain completely intact and serve as the resilient fallback engine for the hybrid integration.
