# FloodShield AI Pro — Role-Based Permission Matrix

This document defines the server-enforced role-based access control (RBAC) boundaries implemented across FloodShield AI Pro for all six logical roles:
1. `citizen`
2. `health_worker`
3. `hospital`
4. `ngo`
5. `government`
6. `admin`

> [!IMPORTANT]
> Frontend UI hiding is not security. All permissions listed below are strictly validated and enforced server-side via FastAPI dependency injection (`get_current_user`, `require_role`, `get_optional_user`) and entity ownership checks in SQLAlchemy query filters.

---

## 1. Role Capabilities Summary

| Role | Scope | Primary Workflows |
|---|---|---|
| **`citizen`** | Public Safety | Browse risk map, nearby hospital capacity, submit unverified incidents, track/withdraw own reports, read public alerts. |
| **`health_worker`** | Field Operations | Accept/complete field tasks, record household visit logs, triage suspected cases, distribute kits, submit supply requests. |
| **`hospital`** | Institutional Operations | Manage own bed/ICU capacity, dynamic multi-item catalog, stock transactions (receive, distribute, discard), forecast-based demand prep, hospital issue inbox. |
| **`ngo`** | Humanitarian Relief | Create and manage own relief campaigns, manage separate warehouse inventory, schedule distribution tasks, access AI-assisted allocation recommendations. |
| **`government`** | National Coordination | National command dashboard, review and allocate cross-agency resource requisitions, compose and broadcast official bilingual alerts, aggregate district issues. |
| **`admin`** | System Administration | User account management & role promotions, hospital bulk CSV import & deduplication, native automation engine monitoring & manual triggers, system audit log inspection. |

---

## 2. Granular API Permission Matrix

| API Endpoint | HTTP Method | Allowed Roles | Enforcement Mechanism |
|---|---|---|---|
| **Public & Citizen Safety** | | | |
| `/predict/*`, `/risk/*`, `/forecast/*` | GET, POST | All (Public / Authenticated) | Open read-only access to risk indices and forecasts. |
| `/hospitals/nearby` | GET | All | Public read-only hospital contact and bed availability. |
| `/field/public/alerts` | GET | All | Public read-only active government alerts. |
| `/field/public/hospitals-capacity` | GET | All | Public read-only hospital beds and operating status. |
| `/field/citizen/reports` | POST | All authenticated | Attaches `reporter_id` and `reporter_email`. Sets status to `unverified`. |
| `/field/citizen/my-reports` | GET | All authenticated | Filters `CommunityReport` by `reporter_id == user.id`. |
| `/field/citizen/reports/{id}/withdraw` | POST | All authenticated | Only permitted if `report.reporter_id == user.id` and status is still `unverified`. |
| **Health Worker Field Operations** | | | |
| `/field/tasks` | GET | `health_worker`, `admin` | Filtered by `assigned_to == user.id` (or all for admin). |
| `/field/tasks/{id}/status` | PATCH | `health_worker`, `admin` | Restricted to assigned worker or admin. |
| `/field/visit-logs` | GET, POST | `health_worker`, `admin` | Creates household visit record, logs triage counts and distributed kits. |
| **Hospital Operations Management** | | | |
| `/hospitals/{id}/profile` | PATCH | `hospital`, `admin` | Checks `user.role == 'admin'` or `user.organization == hospital.name`. Updates bed/ICU counts with non-negative constraints. |
| `/hospitals/{id}/inventory` | GET, POST | `hospital`, `admin` | Organization ownership check. Creates dynamic inventory item with minimum thresholds and batch numbers. |
| `/hospitals/{id}/inventory/{item_id}/transaction` | POST | `hospital`, `admin` | Atomic stock transaction (received, distributed, consumed, damaged, expired). Prevents negative inventory. |
| `/hospitals/{id}/issues` | GET, POST | `hospital`, `health_worker`, `government`, `admin` | Hospital issue inbox with full lifecycle (`OPEN` -> `ACKNOWLEDGED` -> `IN_PROGRESS` -> `RESOLVED`). |
| `/hospitals/{id}/forecast-prep` | GET | `hospital`, `admin` | Correlates Model 3 (WeeklyHistory) projected patient load with current inventory to compute 14-day supply deficits. |
| **NGO Relief Operations** | | | |
| `/ngo/campaigns` | GET, POST | `ngo`, `admin` | Filtered by `organization == user.organization` (or all for admin). |
| `/ngo/campaigns/{id}` | GET, PATCH | `ngo`, `admin` | Update campaign target population, dates, and status (`draft`, `active`, `paused`, `completed`). |
| `/ngo/inventory` | GET, POST | `ngo`, `admin` | Separate warehouse inventory (drinking water, food, purification tablets) owned by the NGO. |
| `/ngo/inventory/{id}/transaction` | POST | `ngo`, `admin` | Stock dispatch and receipt transactions with balance safeguards. |
| `/ngo/distributions` | GET, POST | `ngo`, `admin` | Planned vs actual relief distribution tasks with beneficiaries reached. |
| `/ngo/ai-allocations` | GET | `ngo`, `government`, `admin` | Combines Model 5 composite risk and Model 6 action recommendations into suggested quotas. |
| **Government Emergency Coordination** | | | |
| `/government/command-overview` | GET | `government`, `admin` | Consolidated national summary (critical districts, hospital bed deficits, active NGO campaigns, pending requests). |
| `/government/resource-requests` | GET, POST | `hospital`, `ngo`, `government`, `admin` | Requisitions submitted by hospitals/NGOs, reviewed by government. |
| `/government/resource-requests/{id}/review` | PATCH | `government`, `admin` | Approve or reject requisition with mandatory justification note. |
| `/government/resource-allocations` | POST | `government`, `admin` | Dispatch allocation against approved requisition. Validates available supply. |
| `/government/alerts/compose` | POST | `government`, `admin` | Draft bilingual alert (Bengali + English) with target districts, upazilas, and validity dates. |
| `/government/alerts/{id}/publish` | POST | `government`, `admin` | Two-step authorization: records publisher ID, marks alert `active`, logs audit event. |
| `/government/issues/rollup` | GET | `government`, `admin` | Cross-agency aggregation of community reports, hospital issues, and field escalations. |
| **Automation & Administration** | | | |
| `/admin/jobs` | GET | `admin` | Background job execution registry, last run, next run, status, and error logs. |
| `/admin/jobs/{job_name}/run-now` | POST | `admin` | Triggers immediate background execution of a registered job. |
| `/admin/audit-logs` | GET | `admin` | Immutable audit trail of administrative actions, status updates, and stock transactions. |
| `/reports/*` | GET | `health_worker`, `hospital`, `ngo`, `government`, `admin` | CSV reports with role-based data filtering. |

---

## 3. Data Isolation and Tenant Security Rules

1. **Hospital Separation**: Hospital staff cannot access or modify records of another hospital unless authorized as a district health supervisor (`admin`).
2. **NGO Independence**: NGO campaigns and warehouse stocks are isolated by `organization` name. NGOs cannot edit another organization's inventory.
3. **Citizen Privacy**: Citizens only have read access to their own submitted reports (`reporter_id == user.id`). They cannot view other citizens' submissions, hospital stocks, or internal requisitions.
4. **Predictive Model Immutability**: No role (including Admin or Government) can alter raw ML model prediction values or historical weights. All administrative interventions take the form of separate, auditable official alerts or action directives.
