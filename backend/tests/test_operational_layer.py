"""backend/tests/test_operational_layer.py
----------------------------------------
Comprehensive test suite verifying the operational management layer:
  1. Multi-role RBAC enforcement across all 6 roles
  2. Hospital dynamic multi-item inventory & stock transactions (non-negative enforcement)
  3. Hospital capacity updates & forecast-driven surge prep
  4. NGO relief campaigns, separate inventory, distribution tasks, & AI allocation
  5. Health Worker field tasks & visit logs
  6. Citizen incident reporting, tracking, withdrawal, and public safety views
  7. Government National Command Center, resource requisitions, allocations, & bilingual alerts
  8. N8N-free native automation engine & job runner
  9. CSV report data exports
"""
from __future__ import annotations

import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.auth_models import User, UserRole
from app.reference_models import Hospital, District
from app.operation_models import HospitalInventoryItem, AutomationJob
from app.services.automation_engine import run_single_job


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _create_user(client: TestClient, role: str, district: str = "Feni", org: str = "Test Org") -> dict:
    """Helper to create a user with a specific role and return auth header."""
    uid = uuid.uuid4().hex[:8]
    email = f"user_{role}_{uid}@floodshield.test"
    pwd = "TestPassword123!"
    r = client.post("/auth/signup", json={
        "email": email,
        "password": pwd,
        "full_name": f"{role.title()} User",
        "district": district,
    })
    assert r.status_code in (200, 201), f"Signup failed: {r.text}"

    # Mutate role and organization directly in DB
    with SessionLocal() as db:
        u = db.query(User).filter_by(email=email).first()
        assert u is not None
        u.role = UserRole(role)
        u.organization = org
        db.commit()

    # Log in to get fresh token with role claim
    login_r = client.post("/auth/login", json={"email": email, "password": pwd})
    assert login_r.status_code == 200, f"Login failed: {login_r.text}"
    token = login_r.json()["access_token"]
    return {
        "email": email,
        "role": role,
        "organization": org,
        "headers": {"Authorization": f"Bearer {token}"}
    }


@pytest.fixture(scope="module")
def citizen_user(client):
    return _create_user(client, "citizen")


@pytest.fixture(scope="module")
def health_worker_user(client):
    return _create_user(client, "health_worker")


@pytest.fixture(scope="module")
def hospital_user(client):
    return _create_user(client, "hospital", org="Feni General Hospital")


@pytest.fixture(scope="module")
def ngo_user(client):
    return _create_user(client, "ngo", org="Red Crescent Relief")


@pytest.fixture(scope="module")
def government_user(client):
    return _create_user(client, "government")


@pytest.fixture(scope="module")
def admin_user(client):
    return _create_user(client, "admin")


@pytest.fixture(scope="module")
def test_hospital():
    """Ensure at least one Hospital exists in DB for inventory tests."""
    with SessionLocal() as db:
        hosp = db.query(Hospital).first()
        if not hosp:
            dist = db.query(District).filter(District.name == "Feni").first()
            dist_id = dist.id if dist else None
            hosp = Hospital(
                name="Feni General Hospital",
                district="Feni",
                district_id=dist_id,
                upazila="Feni Sadar",
                beds=100,
                beds_occupied=40,
                icu_beds_total=10,
                icu_beds_occupied=4,
                operating_status="normal",
            )
            db.add(hosp)
            db.commit()
            db.refresh(hosp)
        return str(hosp.id)


# ══════════════════════════════════════════════════════════════════════════
# 1. Role-Based Access Control (RBAC) Boundaries
# ══════════════════════════════════════════════════════════════════════════

def test_citizen_cannot_access_hospital_inventory(client, citizen_user, test_hospital):
    r = client.get(f"/hospitals/{test_hospital}/inventory", headers=citizen_user["headers"])
    assert r.status_code == 403


def test_citizen_cannot_access_admin_jobs(client, citizen_user):
    r = client.get("/admin/jobs", headers=citizen_user["headers"])
    assert r.status_code == 403


def test_citizen_cannot_review_resource_requests(client, citizen_user):
    fake_id = str(uuid.uuid4())
    r = client.patch(
        f"/government/resource-requests/{fake_id}/review",
        json={"status": "approved"},
        headers=citizen_user["headers"]
    )
    assert r.status_code == 403


def test_ngo_cannot_access_admin_jobs(client, ngo_user):
    r = client.get("/admin/jobs", headers=ngo_user["headers"])
    assert r.status_code == 403


# ══════════════════════════════════════════════════════════════════════════
# 2. Hospital Operations: Inventory, Stock Transactions, Capacity, Forecast
# ══════════════════════════════════════════════════════════════════════════

def test_hospital_inventory_listing_and_bootstrap(client, hospital_user, admin_user, test_hospital):
    r = client.get(f"/hospitals/{test_hospital}/inventory", headers=admin_user["headers"])
    assert r.status_code == 200
    items = r.json().get("items", r.json())
    assert len(items) >= 4  # Bootstrapped catalog items
    assert any("Saline" in item["item_name"] or "ORS" in item["item_name"] for item in items)


def test_hospital_stock_transaction_received(client, admin_user, test_hospital):
    inv_r = client.get(f"/hospitals/{test_hospital}/inventory", headers=admin_user["headers"])
    items = inv_r.json().get("items", inv_r.json())
    item_id = items[0]["id"]
    prev_stock = items[0]["current_stock"]

    tx_r = client.post(
        f"/hospitals/{test_hospital}/inventory/{item_id}/transaction",
        json={
            "transaction_type": "received",
            "quantity": 50,
            "notes": "Emergency shipment received from DGHS",
        },
        headers=admin_user["headers"]
    )
    assert tx_r.status_code in (200, 201)
    assert tx_r.json()["new_stock"] == prev_stock + 50


def test_hospital_stock_transaction_consumed_and_insufficient_stock(client, admin_user, test_hospital):
    inv_r = client.get(f"/hospitals/{test_hospital}/inventory", headers=admin_user["headers"])
    items = inv_r.json().get("items", inv_r.json())
    item_id = items[0]["id"]
    current_stock = items[0]["current_stock"]

    # Deduct valid stock
    deduct_r = client.post(
        f"/hospitals/{test_hospital}/inventory/{item_id}/transaction",
        json={
            "transaction_type": "consumed",
            "quantity": 10,
            "notes": "Dispensed to cholera ward",
        },
        headers=admin_user["headers"]
    )
    assert deduct_r.status_code in (200, 201)
    assert deduct_r.json()["new_stock"] == current_stock - 10

    # Deduct more than available stock (must fail with 400 Bad Request)
    over_r = client.post(
        f"/hospitals/{test_hospital}/inventory/{item_id}/transaction",
        json={
            "transaction_type": "consumed",
            "quantity": 999999,
            "notes": "Attempt excessive deduction",
        },
        headers=admin_user["headers"]
    )
    assert over_r.status_code == 400
    assert "Insufficient stock" in over_r.json()["detail"]


def test_hospital_capacity_profile_update(client, admin_user, test_hospital):
    patch_r = client.patch(
        f"/hospitals/{test_hospital}/profile",
        json={
            "beds": 120,
            "beds_occupied": 80,
            "icu_beds_total": 15,
            "icu_beds_occupied": 5,
            "operating_status": "surge_overflow",
            "emergency_contact": "+8801700000000",
        },
        headers=admin_user["headers"]
    )
    assert patch_r.status_code == 200
    assert patch_r.json()["available_general_beds"] == 40
    assert patch_r.json()["available_icu_beds"] == 10


def test_hospital_forecast_preparation(client, admin_user, test_hospital):
    r = client.get(f"/hospitals/{test_hospital}/forecast-prep", headers=admin_user["headers"])
    assert r.status_code == 200
    data = r.json()
    assert "hospital_id" in data
    assert "forecast" in data
    assert "supplies_adequacy" in data
    assert "warnings" in data


# ══════════════════════════════════════════════════════════════════════════
# 3. NGO Relief Operations: Campaigns, Inventory, Distribution, AI Allocation
# ══════════════════════════════════════════════════════════════════════════

def test_ngo_campaign_lifecycle(client, ngo_user):
    # 1. Create campaign
    create_r = client.post(
        "/ngo/campaigns",
        json={
            "title": "Feni Flash Flood Immediate Relief",
            "description": "Distributing safe drinking water and ORS",
            "target_districts": "Feni",
            "target_upazilas": "Feni Sadar, Parshuram",
            "target_population": 5000,
            "start_date": "2026-10-25",
            "team_lead_name": "Rahim Khan",
            "team_lead_contact": "+8801811111111",
        },
        headers=ngo_user["headers"]
    )
    assert create_r.status_code == 201
    campaign_id = create_r.json()["campaign_id"]

    # 2. List campaigns
    list_r = client.get("/ngo/campaigns", headers=ngo_user["headers"])
    assert list_r.status_code == 200
    campaigns = list_r.json().get("campaigns", list_r.json())
    assert any(c["id"] == campaign_id for c in campaigns)

    # 3. Pause campaign
    patch_r = client.patch(
        f"/ngo/campaigns/{campaign_id}/status",
        json={"status": "paused"},
        headers=ngo_user["headers"]
    )
    assert patch_r.status_code == 200


def test_ngo_inventory_and_distribution(client, ngo_user):
    # 1. Add item
    add_r = client.post(
        "/ngo/inventory",
        json={
            "item_name": "Water Purification Sachets",
            "category": "water_purification",
            "unit": "packet",
            "current_stock": 1000,
            "min_threshold": 100,
            "warehouse_location": "Feni Regional Hub",
        },
        headers=ngo_user["headers"]
    )
    assert add_r.status_code == 201
    item_id = add_r.json()["item_id"]

    # 2. Dispatch stock
    tx_r = client.post(
        f"/ngo/inventory/{item_id}/transaction",
        json={
            "transaction_type": "dispatched",
            "quantity": 200,
            "recipient_location": "Parshuram Relief Center",
        },
        headers=ngo_user["headers"]
    )
    assert tx_r.status_code in (200, 201)
    assert tx_r.json()["new_stock"] == 800

    # 3. Create distribution task
    task_r = client.post(
        "/ngo/distribution-tasks",
        json={
            "title": "Parshuram Union 3 Relief Drop",
            "district": "Feni",
            "upazila": "Parshuram",
            "union_or_village": "Mirzanagar",
            "beneficiary_households": 150,
            "people_reached": 600,
            "assigned_team": "Team Alpha",
            "status": "in_transit",
        },
        headers=ngo_user["headers"]
    )
    assert task_r.status_code == 201


def test_ngo_ai_allocation(client, ngo_user):
    r = client.get("/ngo/ai-allocation/Feni", headers=ngo_user["headers"])
    assert r.status_code == 200
    data = r.json()
    assert data["district"] == "Feni"
    assert "suggested_interventions" in data
    assert "priority_rank" in data


# ══════════════════════════════════════════════════════════════════════════
# 4. Health Worker Field Tasks & Citizen Workflows
# ══════════════════════════════════════════════════════════════════════════

def test_health_worker_tasks_and_visit_logs(client, health_worker_user, admin_user):
    # 1. Assign task
    create_r = client.post(
        "/field/tasks",
        json={
            "title": "Investigate acute diarrhoea cluster",
            "task_type": "outbreak_investigation",
            "district": "Feni",
            "upazila": "Chhagalnaiya",
            "priority": "critical",
            "assigned_to_email": health_worker_user["email"],
        },
        headers=admin_user["headers"]
    )
    assert create_r.status_code == 201
    task_id = create_r.json()["task_id"]

    # 2. Health worker accepts & updates task
    patch_r = client.patch(
        f"/field/tasks/{task_id}",
        json={"status": "in_progress", "completion_notes": "Field team deployed"},
        headers=health_worker_user["headers"]
    )
    assert patch_r.status_code == 200

    # 3. Health worker logs visit
    visit_r = client.post(
        "/field/visit-logs",
        json={
            "district": "Feni",
            "upazila": "Chhagalnaiya",
            "location_name": "Ward 4 Community Shelter",
            "households_visited": 25,
            "suspected_cases_count": 6,
            "suspected_diseases": "AWD, Cholera",
            "ors_packets_distributed": 50,
            "water_purification_tablets_distributed": 100,
            "referrals_count": 2,
            "urgent_shortage_reported": "IV Saline shortage at local sub-center",
        },
        headers=health_worker_user["headers"]
    )
    assert visit_r.status_code == 201


def test_citizen_report_submission_and_tracking(client, citizen_user):
    # 1. Citizen submits report
    submit_r = client.post(
        "/citizen/reports",
        json={
            "text": "Water levels rising rapidly behind the school embankment.",
            "label": "flood_incident",
            "severity": "high",
            "district": "Feni",
            "upazila": "Feni Sadar",
            "reporter_email": citizen_user["email"],
        },
        headers=citizen_user["headers"]
    )
    assert submit_r.status_code == 201
    report_id = submit_r.json()["report_id"]
    assert submit_r.json()["status"] == "unverified"

    # 2. Track own reports
    my_r = client.get(f"/citizen/my-reports?email={citizen_user['email']}", headers=citizen_user["headers"])
    assert my_r.status_code == 200
    assert any(rep["id"] == report_id for rep in my_r.json())

    # 3. Withdraw unverified report
    withdraw_r = client.patch(f"/citizen/reports/{report_id}/withdraw", headers=citizen_user["headers"])
    assert withdraw_r.status_code == 200


def test_public_citizen_views(client):
    alerts_r = client.get("/citizen/public-alerts")
    assert alerts_r.status_code == 200
    assert isinstance(alerts_r.json(), list)

    hosp_r = client.get("/citizen/public-hospitals?district=Feni")
    assert hosp_r.status_code == 200
    assert isinstance(hosp_r.json(), list)
    if hosp_r.json():
        # Verify no private inventory data leaked
        assert "current_stock" not in hosp_r.json()[0]
        assert "general_beds_available" in hosp_r.json()[0]


# ══════════════════════════════════════════════════════════════════════════
# 5. Government Command Center & Resource Requisition
# ══════════════════════════════════════════════════════════════════════════

def test_government_command_overview(client, government_user):
    r = client.get("/government/command-overview", headers=government_user["headers"])
    assert r.status_code == 200
    data = r.json()
    assert "hospital_capacity" in data
    assert "ngo_operations" in data
    assert "coordination" in data


def test_government_resource_requisition_and_allocation(client, hospital_user, government_user):
    # 1. Hospital submits request
    req_r = client.post(
        "/government/resource-requests",
        json={
            "request_type": "iv_fluid",
            "district": "Feni",
            "upazila": "Feni Sadar",
            "requested_items": [{"item": "Normal Saline 1000ml", "quantity": 500, "unit": "bag"}],
            "urgency": "critical_emergency",
            "justification": "Heavy influx of acute gastroenteritis patients post-flood surge",
        },
        headers=hospital_user["headers"]
    )
    assert req_r.status_code == 201
    request_id = req_r.json()["request_id"]

    # 2. Government reviews & approves request
    review_r = client.patch(
        f"/government/resource-requests/{request_id}/review",
        json={
            "status": "approved",
            "review_notes": "Approved from Central Emergency Stockpile",
            "allocated_items": [{"item": "Normal Saline 1000ml", "quantity": 500, "unit": "bag"}],
        },
        headers=government_user["headers"]
    )
    assert review_r.status_code == 200

    # 3. Government creates allocation dispatch
    alloc_r = client.post(
        "/government/resource-allocations",
        json={
            "request_id": request_id,
            "source_depot_or_facility": "Chittagong Central Medical Depot",
            "destination_facility": "Feni General Hospital",
            "allocated_items": [{"item": "Normal Saline 1000ml", "quantity": 500, "unit": "bag"}],
            "tracking_number": "TRK-2026-FENI-001",
        },
        headers=government_user["headers"]
    )
    assert alloc_r.status_code == 201


def test_government_official_alert_draft_and_publish(client, government_user):
    # 1. Draft alert
    draft_r = client.post(
        "/alerts/official",
        json={
            "title_bn": "মুহুরী নদীর পানি বিপৎসীমার উপরে",
            "title_en": "Muhuri River Flowing Above Danger Level",
            "message_bn": "পরশুরাম ও ফুলগাজী উপজেলায় নিম্নাঞ্চলের বাসিন্দাদের সতর্ক থাকার অনুরোধ করা হচ্ছে।",
            "message_en": "Residents of low-lying areas in Parshuram and Fulgazi upazilas are advised to take shelter.",
            "severity": "critical",
            "target_districts": "Feni",
            "channel": "in_app",
        },
        headers=government_user["headers"]
    )
    assert draft_r.status_code == 201
    alert_id = draft_r.json()["alert_id"]

    # 2. Publish alert
    pub_r = client.post(f"/alerts/official/{alert_id}/publish", headers=government_user["headers"])
    assert pub_r.status_code == 200


def test_government_issues_rollup(client, government_user):
    r = client.get("/government/issues-rollup?district=Feni", headers=government_user["headers"])
    assert r.status_code == 200
    data = r.json()
    assert "community_incidents" in data
    assert "field_shortages" in data
    assert "hospital_shortages" in data


# ══════════════════════════════════════════════════════════════════════════
# 6. Native Backend Automation Engine & Admin Controls
# ══════════════════════════════════════════════════════════════════════════

def test_admin_jobs_list(client, admin_user):
    r = client.get("/admin/jobs", headers=admin_user["headers"])
    assert r.status_code == 200
    jobs = r.json()
    assert len(jobs) >= 5
    job_names = [j["job_name"] for j in jobs]
    assert "inventory_monitor" in job_names
    assert "risk_monitor" in job_names


def test_automation_engine_run_single_job():
    import asyncio
    result = asyncio.run(run_single_job("inventory_monitor"))
    assert result["status"] == "success"
    assert "result" in result


def test_admin_trigger_job_run(client, admin_user):
    r = client.post("/admin/jobs/inventory_monitor/run-now", headers=admin_user["headers"])
    assert r.status_code == 200
    assert r.json()["details"]["status"] == "success"


def test_admin_audit_logs_view(client, admin_user):
    r = client.get("/admin/audit-logs", headers=admin_user["headers"])
    assert r.status_code == 200
    logs = r.json()
    assert isinstance(logs, list)
    assert len(logs) > 0  # Preceding actions created audit events


# ══════════════════════════════════════════════════════════════════════════
# 7. Automated Reports Export (CSV)
# ══════════════════════════════════════════════════════════════════════════

def test_csv_report_exports(client, government_user):
    # Risk CSV
    r1 = client.get("/reports/daily-risk/csv", headers=government_user["headers"])
    assert r1.status_code == 200
    assert "text/csv" in r1.headers["content-type"]
    assert "Recorded At" in r1.text

    # Hospital Shortages CSV
    r2 = client.get("/reports/hospital-shortages/csv", headers=government_user["headers"])
    assert r2.status_code == 200
    assert "text/csv" in r2.headers["content-type"]
    assert "Hospital Name" in r2.text

    # NGO Distribution CSV
    r3 = client.get("/reports/ngo-distribution/csv", headers=government_user["headers"])
    assert r3.status_code == 200
    assert "text/csv" in r3.headers["content-type"]
    assert "Task Title" in r3.text

    # Resource Requests CSV
    r4 = client.get("/reports/resource-requests/csv", headers=government_user["headers"])
    assert r4.status_code == 200
    assert "text/csv" in r4.headers["content-type"]
    assert "Requester Email" in r4.text
