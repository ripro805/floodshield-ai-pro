# FloodShield AI Pro — n8n Integration Guide

## 1. Overview & Integration Philosophy

FloodShield AI Pro incorporates a hybrid automation framework connecting the core FastAPI backend with an n8n workflow engine. The integration is designed with a **Zero-Breakage, Fallback-First** philosophy:

1. **Supplied Webhook Endpoint**: The primary automation webhook is configured to route to the user's active n8n instance:
   `https://floodshield.app.n8n.cloud/webhook/floodshield-monitoring`
2. **Centralized Service Architecture**: All communication with n8n is isolated inside `backend/app/services/n8n_service.py` and routed via `backend/app/services/hybrid_automation.py`.
3. **Decoupled Security**: Webhook secrets and authentication tokens are kept strictly server-side in environment variables and are never exposed to the frontend or public logs.
4. **Resilient Non-Blocking Dispatch**: The backend probes webhook health before dispatch and captures errors (timeouts, 401/403 auth errors, 404/410 inactive workflow errors, 422 payload schema mismatches, and 5xx server faults) to trigger immediate fallback to native automation.

---

## 2. Configuration & Environment Variables

The backend configuration is managed in `backend/app/config.py` and sourced from `backend/.env`:

```env
# ── Hybrid n8n Automation Configuration ──────────────────────────────────────
# Master toggle for n8n integration (true/false)
N8N_ENABLED=true

# Provided n8n Webhook URL
N8N_WEBHOOK_URL=https://floodshield.app.n8n.cloud/webhook/floodshield-monitoring

# Automation mode: "auto" (n8n with native fallback), "n8n" (n8n-preferred), "native" (native only)
AUTOMATION_MODE=auto

# Webhook request timeout in seconds
N8N_TIMEOUT=15

# Health check cache TTL in seconds (prevents thundering herd on external webhook)
N8N_HEALTH_CACHE_SECONDS=30

# Optional Webhook Security Header and Secret (passed in request headers to n8n)
N8N_WEBHOOK_HEADER_NAME=X-Webhook-Secret
N8N_WEBHOOK_SECRET=your_n8n_webhook_secret_here

# Backend base URL for n8n reconciliation callbacks
FLOODSHIELD_BACKEND_BASE_URL=http://localhost:8000
```

---

## 3. Event Mappings & Workflow Contract

The backend maps internal automation jobs to specific event triggers accepted by the n8n workflow:

| Native Job Name | n8n Event (`event_type` & `event`) | Purpose | Workflow Action in n8n |
| :--- | :--- | :--- | :--- |
| `weather_collector` | `weather_check` | Periodic meteorological & hydrometric check | Fetch district telemetry, assess rainfall |
| `scheduled_district_predictions` | `weather_check` | Automated flood risk scoring across divisions | Evaluate risk models, trigger threshold alerts |
| `risk_monitor` | `weather_check` | Emergency precipitation threshold scanner | High rainfall detection & warning drafting |
| `inventory_monitor` | `inventory_check` | Hospital and NGO supply shortages scanner | Check stock levels, flag critical items |
| `unresolved_issues_escalator` | `issues_check` | Pending resource requests older than 24h | Escalate priority from normal to urgent |

---

## 4. Structured JSON Payload Format

The backend dispatches standard JSON payloads via `POST` requests. Both `event_type` and `event` keys are provided to ensure full compatibility with n8n Switch nodes filtering on either property:

```json
{
  "task_id": "inventory_monitor:702f9b36887249ecb85b2f1cddd97d3e",
  "event_id": "df26f0797aaf4925aa441c657480b0c5",
  "event_type": "inventory_check",
  "event": "inventory_check",
  "timestamp": "2026-11-20T06:12:56.123456+00:00",
  "source": "floodshield-backend",
  "job_name": "inventory_monitor",
  "data": {
    "scheduled_task": "inventory_monitor",
    "dispatched_at": "2026-11-20T06:12:56.123456+00:00"
  }
}
```

### Payload Field Definitions:
- `task_id` (*string*): Globally unique task identifier combining job name and a UUID (`job_name:hex`). Used for deduplication and status reconciliation.
- `event_id` (*string*): Unique event identifier for tracing.
- `event_type` (*string*): Canonical event classification (`inventory_check`, `issues_check`, `weather_check`).
- `event` (*string*): Alias for `event_type` (ensuring compatibility with `$json.body.event`).
- `timestamp` (*string*): ISO 8601 UTC timestamp of dispatch.
- `source` (*string*): Source system identifier (`floodshield-backend`).
- `job_name` (*string*): Internal job name.
- `data` (*object*): Task-specific context parameters.

---

## 5. Webhook Response & Outcome Classification

The backend interprets the HTTP response from n8n as follows:

| HTTP Status Code / Exception | Outcome Classification | System Behavior |
| :--- | :--- | :--- |
| **`200 OK` .. `299`** | `accepted` | Execution logged as `n8n` engine, `status: pending`. Processing proceeds in n8n. |
| **`401 Unauthorized` / `403 Forbidden`** | `rejected` | Logged as authentication error. Automatic fallback to Native Automation. |
| **`404 Not Found` / `410 Gone`** | `rejected` | Logged as workflow inactive/missing. Automatic fallback to Native Automation. |
| **`422 Unprocessable Entity`** | `rejected` | Logged as schema validation error. Automatic fallback to Native Automation. |
| **`500 Internal Server Error`** | `rejected` | Logged as n8n runtime failure. Automatic fallback to Native Automation. |
| **`httpx.TimeoutException`** | `timeout` | Execution logged as `engine: unknown`, `status: unknown`. **Native execution is NOT triggered** to prevent duplicate actions. |
| **`httpx.ConnectError`** | `rejected` | Logged as network failure. Automatic fallback to Native Automation. |

---

## 6. Reconciliation Callback API

When n8n completes an asynchronous workflow execution, it can notify the FloodShield backend to mark the task as verified:

- **Endpoint**: `POST /admin/automation/executions/{task_id}/callback`
- **Authentication**: Requires Admin JWT Bearer Token or valid `X-Webhook-Secret` header matching `N8N_WEBHOOK_SECRET`.
- **Request Body**:
```json
{
  "status": "success",
  "result": {
    "workflow_execution_id": "n8n_exec_98765",
    "completed_actions": 4,
    "notified_parties": ["hospital-admin@feni.gov.bd"]
  },
  "error": null
}
```
- **Response**: `200 OK` with updated `AutomationExecution` record.

---

## 7. Step-by-Step n8n Workflow Configuration Guide

To build or verify the workflow in your n8n workspace:

1. **Create a New Workflow**: Name it `FloodShield AI Monitoring`.
2. **Add a Webhook Trigger Node**:
   - HTTP Method: `POST`
   - Path: `floodshield-monitoring`
   - Response Mode: `On Received` (returns HTTP 200 immediately)
   - Authentication: Set Header Auth to match `X-Webhook-Secret` (or None if public).
3. **Add a Switch Node**:
   - Mode: `Rules`
   - Expression: `{{ $json.body.event || $json.body.event_type }}`
   - Rule 1: String equal to `weather_check` -> Connect to Weather Processing branch.
   - Rule 2: String equal to `inventory_check` -> Connect to Hospital/NGO Inventory branch.
   - Rule 3: String equal to `issues_check` -> Connect to Resource Escalation branch.
4. **Add Action Nodes**:
   - For `inventory_check`: Query backend API or database to inspect low-stock alerts, trigger Slack/Telegram/Email notifications to supply managers.
   - For `issues_check`: Check unresolved requests older than 24h, send reminder alerts to NGO coordinators.
   - For `weather_check`: Compare weather forecast data against flood thresholds, generate emergency notifications.
5. **Add Callback Node (Optional)**:
   - HTTP Request node targeting `http://localhost:8000/admin/automation/executions/{{ $json.body.task_id }}/callback` to close the audit loop.
6. **Activate the Workflow**: Click **Active** toggle in n8n.
