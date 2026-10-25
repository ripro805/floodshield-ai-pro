# FloodShield AI Pro — Existing Feature Inventory & Baseline Audit

Date of Audit: October 2026
Branch: `feature/operational-layer-upgrade`
Environment: Python 3.12 / 3.14, Node.js 20, Next.js 14.2, FastAPI, Neon PostgreSQL + pgvector, AWS EC2, Vercel

---

## 1. System Architecture Overview

FloodShield AI Pro is an AI-powered flood and disease outbreak early-warning and disaster-response decision platform tailored for Bangladesh's 64 districts.

- **Frontend**: Next.js 14.2 (App Router), React 18, TypeScript, Tailwind CSS, Lucide React, Framer Motion, TanStack Query, Leaflet, Three.js (3D Bangladesh Globe).
- **Backend**: FastAPI REST API, Uvicorn, SQLAlchemy 2.0, Pydantic v2, PostgreSQL (Neon Cloud) with `pgvector` HNSW extension.
- **Authentication**: JWT (HS256) bearer authentication, bcrypt password hashing, 6 role enumerations (`citizen`, `health_worker`, `hospital`, `ngo`, `government`, `admin`).
- **AI/ML Layer**: 6 machine learning models hosted locally or dynamically pulled from Hugging Face Hub (`ripro805/floodshield-ai-models`), plus a RAG (Retrieval-Augmented Generation) medical chatbot.

---

## 2. Feature-by-Feature Baseline Audit & Classification

Classification Key:
- `EXISTS_AND_WORKS`: Implemented, tested, and functioning in current code.
- `EXISTS_BUT_INCOMPLETE`: Implemented in part, requires operational extension or missing CRUD/workflow.
- `MISSING`: Not yet present in database, backend router, or frontend portal.
- `BLOCKED_BY_EXTERNAL_DEPENDENCY`: Requires active 3rd-party credentials (e.g. Twilio live credit, live GEE service account in all environments).

### 2.1 AI / ML Prediction Engines

| Feature / Model | Status | Notes & Location |
|---|---|---|
| **Model 1: Flood Prediction** | `EXISTS_AND_WORKS` | `backend/app/routers/flood.py` — RF/XGBoost binary classifier. Accepts rainfall, river discharge, elevation. |
| **Model 2: Disease Outbreak Risk** | `EXISTS_AND_WORKS` | `backend/app/routers/disease.py` — 3-class classifier (`Medium`, `High`, `Critical`). |
| **Model 2B: Disease Breakdown** | `EXISTS_AND_WORKS` | `backend/app/routers/disease_breakdown.py` — 6 per-disease XGBoost regressors (cholera, malaria, dengue, typhoid, diarrhoea, hepatitis). |
| **Model 3: Time-Series LSTM** | `EXISTS_AND_WORKS` | `backend/app/routers/forecast.py` — 7-day & 14-day LSTM forecasting. Supported by TensorFlow/Keras on server. |
| **Model 4A: Satellite Flood Extents** | `EXISTS_AND_WORKS` | `backend/app/routers/satellite.py` (`/satellite/flood-extent`) — Google Earth Engine / GAUL GeoJSON exports stored in DB. |
| **Model 4B: U-Net SAR Segmentation** | `EXISTS_AND_WORKS` | `backend/app/routers/satellite.py` (`/satellite/segment`) — Sentinel-1 SAR acquisition via GEE and U-Net inference on Hugging Face weights. |
| **Model 5: Composite Risk & Hotspots** | `EXISTS_AND_WORKS` | `backend/app/routers/risk.py`, `/predict/hotspots` — Combines flood (0.4) and disease (0.6) risk weights across all 64 districts. |
| **Model 6: Operational Recommendations** | `EXISTS_AND_WORKS` | `backend/app/routers/recommend.py` — Action recommendations for operational roles (`health_worker`, `hospital`, `ngo`, `government`, `admin`). |
| **RAG Medical Chatbot** | `EXISTS_AND_WORKS` | `backend/app/routers/chatbot.py` — Claude/Ollama/HF with pgvector cosine retrieval on 8 WHO/DGHS guideline documents. |

---

### 2.2 Role-Based Portals & Operational Layer

| Role / Capability | Status | Notes & Gap Analysis |
|---|---|---|
| **Citizen: Risk & Map Browsing** | `EXISTS_AND_WORKS` | District-level risk indicators, 3D Globe, district map. |
| **Citizen: Public Hospital Search** | `EXISTS_AND_WORKS` | `/hospitals/nearby` with GPS geolocation, public contact details. |
| **Citizen: Incident Reporting** | `EXISTS_BUT_INCOMPLETE` | Chatbot supports `report_incident`, writes to `community_reports`. Missing: citizen view and status tracking of their own submitted reports. |
| **Health Worker: Field Tasks** | `MISSING` | No dedicated field task assignment, acceptance, or task progress entity. |
| **Health Worker: Field Visit Logs** | `MISSING` | No structured logs for household visits, suspected case counting, ORS kit distribution tracking. |
| **Health Worker: Supply & Referral Requests** | `MISSING` | No medical supply requisition or hospital patient referral tracking. |
| **Hospital: Capacity Management** | `EXISTS_BUT_INCOMPLETE` | General & ICU beds exist in `hospitals` table. Missing: non-negative/capacity validation, emergency isolation capacity, daily patient load. |
| **Hospital: Dynamic Inventory** | `EXISTS_BUT_INCOMPLETE` | Fixed stock columns exist (`ors_packets_stock`, `iv_saline_bags_stock`). Missing: multi-item inventory catalogue, batch/expiry tracking, stock transactions (received, distributed, consumed, damaged), low-stock alerts. |
| **Hospital: Issue Inbox & Ticketing** | `EXISTS_AND_WORKS` | `hospital_issues` table, `/hospitals/{id}/issues`, admin issue rollup. Needs full lifecycle (`OPEN -> ACKNOWLEDGED -> IN_PROGRESS -> RESOLVED -> REJECTED`). |
| **NGO: Relief Campaigns** | `MISSING` | No entity or portal for campaign management (objectives, target districts/upazilas, dates, population target, field teams). |
| **NGO: Relief Inventory** | `MISSING` | No separate NGO warehouse inventory (dry food, water purification, blankets, hygiene kits) distinct from hospital medical stocks. |
| **NGO: Relief Distribution Tasks** | `MISSING` | No planned vs actual distribution logs with people reached. |
| **Government: National Command Overview** | `EXISTS_BUT_INCOMPLETE` | District assessment and hotspots exist. Missing: unified consolidated dashboard aggregating hospital shortages, NGO campaigns, and active alerts. |
| **Government: Official Alert Management** | `EXISTS_BUT_INCOMPLETE` | `/sms/send` exists. Missing: formal alert drafting, bilingual English/Bengali template preview, approval workflow, alert validity periods, broadcast logs. |
| **Government: Resource Request & Allocation** | `MISSING` | No inter-agency resource request submission, review, approval, and allocation pipeline. |
| **Admin: User Management** | `EXISTS_AND_WORKS` | `/admin/users`, role promotion, user details in `AdminPanel`. |
| **Admin: Hospital Bulk Import** | `EXISTS_AND_WORKS` | CSV import with geocoding, preview, deduplication in `HospitalImportModal`. |
| **Admin: Background Job Monitor** | `MISSING` | No monitoring UI or registry for background automation jobs. |

---

### 2.3 Backend Automation & Scheduled Workflows

| Capability | Status | Implementation Details |
|---|---|---|
| **Weather Ingestion Loop** | `EXISTS_AND_WORKS` | `app/services/weather_scheduler.py` — Periodic 6-hour refresh for selected districts. |
| **Automated Periodic Predictions** | `MISSING` | Predictions currently run only on user request. Needs scheduled daily district risk batch calculation. |
| **Risk Threshold Monitoring & Alerts** | `MISSING` | No automated detector that triggers an alert candidate when a district transitions into `Critical` risk. |
| **Low-Stock & Expiry Detection** | `MISSING` | No scheduled check alerting hospital/NGO managers to inventory approaching threshold or expiry date. |
| **Unresolved Issue Escalation** | `MISSING` | No automated reminder for issues pending over 48 hours. |
| **Job Execution Registry** | `MISSING` | Need database-backed `automation_jobs` table to record start time, completion, status, errors, and retry logs without n8n. |

---

### 2.4 External Dependencies

| Dependency | Configuration / State |
|---|---|
| **Neon PostgreSQL** | Fully operational with `pgvector` HNSW index. |
| **Google Earth Engine** | `ee_service_account.json` configured on EC2 for live Sentinel-1 SAR acquisition. |
| **OpenWeatherMap** | `WEATHER_API_KEY` configured in `.env` for 64 districts. |
| **Anthropic Claude** | `ANTHROPIC_API_KEY` configured in `.env` for RAG chatbot. |
| **Hugging Face Hub** | Models loaded dynamically from `ripro805/floodshield-ai-models`. |
| **Twilio SMS** | Configurable via `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`. Optional/mocked gracefully when credentials absent. |
