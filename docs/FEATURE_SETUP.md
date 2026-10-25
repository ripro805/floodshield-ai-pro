# FloodShield AI Pro — Feature Setup & Environment Configuration

This guide documents the setup instructions, environment variables, external services, and deployment requirements for the operational upgrade layer.

---

## 1. Environment Variables Configuration

Ensure the following variables are defined in `backend/.env` (refer to `backend/.env.example`):

```bash
# ==============================================================================
# Database & Authentication
# ==============================================================================
DATABASE_URL=postgresql://neondb_owner:***@ep-***.ap-southeast-1.aws.neon.tech/neondb?sslmode=require
SECRET_KEY=your_secure_random_jwt_secret_key_here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# ==============================================================================
# Native Background Automation (N8N-Free)
# ==============================================================================
AUTOMATION_ENGINE_ENABLED=true
AUTOMATION_POLL_INTERVAL=60
JOB_INTERVAL_WEATHER=21600
JOB_INTERVAL_PREDICTIONS=86400
JOB_INTERVAL_RISK_MONITOR=3600
JOB_INTERVAL_INVENTORY=43200
JOB_INTERVAL_ESCALATION=21600

# ==============================================================================
# Weather & Environmental Integrations
# ==============================================================================
WEATHER_API_KEY=your_openweathermap_api_key_here

# ==============================================================================
# AI Models & External Providers (Optional / Gracefully Degraded)
# ==============================================================================
ANTHROPIC_API_KEY=your_claude_api_key_for_rag_chatbot
TWILIO_ACCOUNT_SID=your_twilio_sid_optional
TWILIO_AUTH_TOKEN=your_twilio_token_optional
TWILIO_FROM_NUMBER=+1234567890
```

Frontend environment (`frontend/.env.local`):
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## 2. Database Schema & Automatic Migrations

The new operational entities are automatically synchronized on backend startup via `backend/app/services/db_migrations.py`. No manual SQL commands are required.

The migration service executes idempotent `ALTER TABLE` and `CREATE TABLE IF NOT EXISTS` statements for:
- `users`: Added `organization` (VARCHAR) and `phone` (VARCHAR).
- `hospitals`: Added `beds_occupied`, `icu_beds_total`, `icu_beds_occupied`, `operating_status`, `contact_person`.
- `community_reports`: Added `district`, `upazila`, `reporter_email`, `status`, `image_url`.
- `hospital_inventory_items` & `hospital_stock_transactions`
- `relief_campaigns`, `ngo_inventory_items`, `ngo_stock_transactions`, `relief_distribution_tasks`
- `field_tasks`, `field_visit_logs`
- `resource_requests`, `resource_allocations`
- `official_alerts`
- `automation_jobs`
- `audit_events`

---

## 3. External Service Status & Requirements

| Service / Provider | Purpose | Status / Fallback Mechanism |
|---|---|---|
| **Neon PostgreSQL** | Relational data + pgvector embeddings | Active & connected. |
| **OpenWeatherMap** | Live weather for 64 districts | Ingests live data if key present; falls back to historical records. |
| **Google Earth Engine (GEE)** | Sentinel-1 SAR acquisition | Active on server via `ee_service_account.json`. Mocked in local test suites. |
| **Hugging Face Hub** | Models 1–6 weights | Dynamically pulled from `ripro805/floodshield-ai-models` or local cache. |
| **Twilio SMS** | Emergency broadcast delivery | Optional. When credentials are not set, alerts are marked `simulated_logged` and stored without failing. |
| **Anthropic Claude** | RAG health assistant | Optional. Falls back to keyword and FAQ match when key is unavailable. |

---

## 4. Local Execution Commands

### Starting the Backend (FastAPI + Automation Loop)
```bash
cd backend
# Activate virtual environment if configured
# Windows: .venv\Scripts\activate
# Linux/Mac: source .venv/bin/activate

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Starting the Frontend (Next.js)
```bash
cd frontend
npm run dev
# Accessible at http://localhost:3000
```

### Running Backend Unit & Integration Tests
```bash
cd backend
python -m pytest tests/test_operational_layer.py -v
```
