# FloodShield AI Pro — Native Backend Automation Architecture (N8N-Free)

This document provides complete operational guidance on FloodShield AI Pro's native, self-hosted Python automation and background scheduling architecture.

---

## 1. Design Principles & Architecture

To avoid recurring costs, complex third-party SaaS requirements, or external node dependencies like n8n, FloodShield AI Pro includes an asynchronous, self-contained background scheduler engine built directly inside the FastAPI backend.

- **Engine Core**: `backend/app/services/automation_engine.py`
- **Execution Model**: `asyncio` non-blocking worker loop started during FastAPI application lifespan.
- **Persistence & Monitoring**: `AutomationJob` SQLAlchemy model stores job execution status, start times, completion times, retry counts, and stack traces.
- **Admin Control**: REST endpoints at `/admin/jobs` and `/admin/jobs/{job_name}/run-now` provide real-time inspection and manual on-demand triggers.
- **Multi-Worker Safety**: Includes database record timestamps and run-locking logic to prevent duplicate concurrent executions across scaled instances.

```
                      FastAPI Lifespan (Startup)
                                   │
                                   ▼
                   ┌───────────────────────────────┐
                   │    automation_engine_loop     │
                   │   (Async Periodic Poller)     │
                   └───────────────┬───────────────┘
                                   │
            ┌──────────────────────┼──────────────────────┐
            ▼                      ▼                      ▼
┌──────────────────────┐ ┌───────────────────┐ ┌─────────────────────┐
│ 1. Weather Collector │ │ 2. Prediction Job │ │ 3. Risk Monitor     │
│ 6-hour district sync │ │ Daily batch risk  │ │ Critical transition │
│ OpenWeatherMap API   │ │ Model 1 + Model 2 │ │ candidate alerts    │
└──────────────────────┘ └───────────────────┘ └─────────────────────┘
            │                      │                      │
            └──────────────────────┼──────────────────────┘
                                   │
            ┌──────────────────────┴──────────────────────┐
            ▼                                             ▼
┌──────────────────────────────┐              ┌───────────────────────┐
│ 4. Inventory Monitor         │              │ 5. Issue Escalator    │
│ Low-stock & 30-day expiry    │              │ 48h unresolved ticket │
│ warnings for hospital & NGO  │              │ notifications         │
└──────────────────────────────┘              └───────────────────────┘
                                   │
                                   ▼
                   ┌───────────────────────────────┐
                   │     AutomationJob Table       │
                   │ (Status, Duration, Logs, DB)  │
                   └───────────────────────────────┘
```

---

## 2. Registered Automated Background Jobs

| Job Identifier | Default Interval | Description | Impacted Entities |
|---|---|---|---|
| `weather_collector` | 6 hours (21,600s) | Queries OpenWeatherMap for 64 districts; records rainfall, temperature, humidity in `weather_observations`. | `WeatherObservation` |
| `scheduled_district_predictions` | 24 hours (86,400s) | Runs Models 1 & 2 across all 64 districts; updates `WeeklyHistory` and composite risk scores. | `WeeklyHistory`, Risk Index |
| `risk_monitor` | 1 hour (3,600s) | Detects districts crossing into `Critical` risk; prepares candidate drafts for official alerts. | `OfficialAlert` |
| `inventory_monitor` | 12 hours (43,200s) | Audits hospital pharmacies and NGO warehouses for stocks falling below minimum threshold or expiring within 30 days. | `HospitalInventoryItem`, `NgoInventoryItem` |
| `unresolved_issues_escalator` | 6 hours (21,600s) | Flags hospital tickets or citizen reports in `OPEN` status for more than 48 hours without resolution. | `HospitalIssue`, `CommunityReport` |

---

## 3. Configuration & Environment Variables

Control scheduler execution intervals and behavior via environment variables in `backend/.env`:

```bash
# Enable or disable the native automation worker
AUTOMATION_ENGINE_ENABLED=true

# Check interval for the scheduler loop (seconds)
AUTOMATION_POLL_INTERVAL=60

# Specific job intervals (seconds)
JOB_INTERVAL_WEATHER=21600
JOB_INTERVAL_PREDICTIONS=86400
JOB_INTERVAL_RISK_MONITOR=3600
JOB_INTERVAL_INVENTORY=43200
JOB_INTERVAL_ESCALATION=21600
```

---

## 4. Running Locally & In Production

### Development / Local
When starting FastAPI via Uvicorn, the automation worker starts automatically in the background:
```bash
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Production (Systemd or Docker)
In multi-worker production setups (e.g. `gunicorn -w 4 -k uvicorn.workers.UvicornWorker`), ensure only one worker is designated as the scheduler leader, or rely on the built-in database row lock in `automation_engine.py`:
```bash
# On AWS EC2 or Ubuntu Server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```

---

## 5. Admin Monitoring & Manual Job Execution

Administrators can navigate to `/dashboard/admin/jobs` in the web frontend or query the API directly:

1. **List all background jobs and status**:
   ```http
   GET /admin/jobs
   Authorization: Bearer <ADMIN_JWT_TOKEN>
   ```

2. **Trigger an instant manual execution**:
   ```http
   POST /admin/jobs/scheduled_district_predictions/run-now
   Authorization: Bearer <ADMIN_JWT_TOKEN>
   ```

3. **Inspect system audit trail**:
   ```http
   GET /admin/audit-logs?limit=50
   Authorization: Bearer <ADMIN_JWT_TOKEN>
   ```
