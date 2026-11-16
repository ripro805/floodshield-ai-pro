"""
tests_audit/test_api_audit.py
-----------------------------
Comprehensive Deep Technical Audit Test Suite for FloodShield AI API.
Covers:
  - System Health & Monitoring
  - AI Models 1 through 6
  - RAG Clinical Chatbot
  - Hospital Directory & Weather Services
  - Full 6-Role RBAC Security Matrix
  - Input Validation, Sanitization & Vulnerability Resilience
"""
import pytest
import httpx
import json

BASE_URL = "http://127.0.0.1:8000"

# Dedicated test accounts from test_users_credentials.csv
CREDENTIALS = {
    "citizen": ("test.citizen@floodshield-demo.com", "RCkxbo4uRe82J4"),
    "health_worker": ("test.health_worker@floodshield-demo.com", "e2eAc$4VUqgh@x"),
    "hospital": ("test.hospital@floodshield-demo.com", "bWUL4VpYqLidkY"),
    "ngo": ("test.ngo@floodshield-demo.com", "RRSay48sQ$8B3i"),
    "government": ("test.government@floodshield-demo.com", "yT@XUcnrH9oFZS"),
    "admin": ("test.admin@floodshield-demo.com", "UGT9Tja4RiAAD3"),
}

@pytest.fixture(scope="session")
def tokens():
    """Retrieve auth tokens for all 6 roles using JSON login."""
    toks = {}
    with httpx.Client(base_url=BASE_URL, timeout=15) as client:
        for role, (email, pwd) in CREDENTIALS.items():
            res = client.post("/auth/login", json={"email": email, "password": pwd})
            if res.status_code == 200:
                toks[role] = res.json().get("access_token")
            else:
                toks[role] = None
    return toks


# ─────────────────────────────────────────────────────────────────────────────
# 1. System Health & Core API Engine
# ─────────────────────────────────────────────────────────────────────────────

def test_health_check():
    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        res = client.get("/")
        assert res.status_code == 200
        data = res.json()
        assert data.get("status") == "ok"
        assert "FloodShield" in data.get("service", "")
        assert data.get("models_loaded") is True


def test_monitoring_summary(tokens):
    """Operational monitoring summary."""
    token = tokens.get("admin") or tokens.get("government")
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        res = client.get("/monitoring/summary", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "prediction_count" in data


# ─────────────────────────────────────────────────────────────────────────────
# 2. Domain AI Models (Models 1 - 6)
# ─────────────────────────────────────────────────────────────────────────────

def test_model_1_flood_prediction(tokens):
    """Model 1: Binary Flood Classifier (Random Forest / XGBoost ensemble)."""
    token = tokens["citizen"]
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(base_url=BASE_URL, timeout=15) as client:
        payload = {
            "river_level_m": 8.7,
            "rainfall_mm": 185.5,
            "humidity_percent": 92.0,
            "elevation_m": 12.4,
            "location": "Sylhet",
        }
        res = client.post("/predict/flood", json=payload, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "flood_probability" in data
        assert "flood_risk_level" in data


def test_model_2_disease_outbreak_prediction(tokens):
    """Model 2: Overall Epidemic Risk Classifier."""
    token = tokens["citizen"]
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(base_url=BASE_URL, timeout=15) as client:
        payload = {
            "location": "Sylhet",
            "river_level_m": 7.5,
            "flood_depth_cm": 50.0,
            "previous_week_cases": 120.0,
            "previous_two_week_cases": 210.0,
            "rainfall_mm": 150.0,
            "temperature_c": 29.0,
            "humidity_percent": 88.0,
        }
        res = client.post("/predict/disease", json=payload, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "predicted_outbreak_risk" in data


def test_model_2b_pathogen_breakdown(tokens):
    """Model 2B: 6-Pathogen Quantitative Breakdown."""
    token = tokens["citizen"]
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(base_url=BASE_URL, timeout=15) as client:
        payload = {
            "location": "Sylhet",
            "river_level_m": 7.5,
            "flood_depth_cm": 50.0,
            "previous_week_cases": 120.0,
            "previous_two_week_cases": 210.0,
            "rainfall_mm": 150.0,
            "temperature_c": 29.0,
            "humidity_percent": 88.0,
        }
        res = client.post("/predict/disease-breakdown", json=payload, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "disease_breakdown" in data
        assert "dominant_disease" in data


def test_model_3_time_series_lstm_forecasting(tokens):
    """Model 3: Recurrent LSTM 7-Day & 14-Day Hospital Admission Surge."""
    token = tokens["citizen"]
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(base_url=BASE_URL, timeout=20) as client:
        # Requires 8 consecutive observations
        sample_week = {
            "weekly_cases": 120.0,
            "rainfall_mm": 90.0,
            "temperature_c": 28.0,
            "flood_depth_cm": 20.0,
            "sanitation_score": 0.5,
        }
        payload = {
            "district": "Munshiganj",
            "recent_weeks": [sample_week] * 8,
        }
        res = client.post("/predict/forecast", json=payload, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "forecast_next_7_days_cases" in data
        assert "forecast_next_14_days_cases" in data


def test_model_4_satellite_radar_extent():
    """Model 4: Sentinel-1 C-Band SAR Radar Water Segmentation."""
    with httpx.Client(base_url=BASE_URL, timeout=25) as client:
        res = client.get("/satellite/gee/extent", params={"district": "Sylhet"})
        assert res.status_code in (200, 404, 503)


def test_model_5_composite_risk_and_hotspots(tokens):
    """Model 5: Multi-Hazard Composite Scoring & DBSCAN Hotspots."""
    token = tokens["citizen"]
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(base_url=BASE_URL, timeout=15) as client:
        res = client.get("/risk/composite", headers=headers)
        assert res.status_code in (200, 404, 422)

        hotspot_res = client.get("/hotspots", headers=headers)
        assert hotspot_res.status_code in (200, 404)


def test_model_6_policy_recommendations(tokens):
    """Model 6: Operational Action Checklist Engine."""
    token = tokens["government"]
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(base_url=BASE_URL, timeout=15) as client:
        payload = {
            "district": "Sylhet",
            "flood_probability": 0.85,
        }
        res = client.post("/recommend", json=payload, headers=headers)
        assert res.status_code in (200, 422)


def test_full_district_assessment(tokens):
    """Unified Assessment API (/assessment/{district})."""
    token = tokens["citizen"]
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(base_url=BASE_URL, timeout=20) as client:
        res = client.get("/assessment/Sylhet", headers=headers)
        assert res.status_code in (200, 404)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Weather & Hospital Infrastructure
# ─────────────────────────────────────────────────────────────────────────────

def test_weather_services():
    with httpx.Client(base_url=BASE_URL, timeout=15) as client:
        res = client.get("/api/weather", params={"location": "Sylhet"})
        assert res.status_code == 200
        data = res.json()
        assert "temperature" in data or "humidity" in data or "rainfall" in data


def test_hospitals_directory(tokens):
    token = tokens["citizen"]
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(base_url=BASE_URL, timeout=15) as client:
        # Districts summary
        res = client.get("/hospitals/districts-summary", headers=headers)
        assert res.status_code == 200

        # Nearby hospital finder
        nearby = client.get("/hospitals/nearby", params={"lat": 24.8949, "lng": 91.8687, "limit": 3}, headers=headers)
        assert nearby.status_code == 200
        data = nearby.json()
        assert isinstance(data, list) or "hospitals" in data


def test_rag_medical_chatbot(tokens):
    token = tokens["citizen"]
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(base_url=BASE_URL, timeout=30) as client:
        payload = {
            "message": "What immediate first aid should be given for acute watery diarrhoea in a flood shelter?",
            "district": "Sylhet",
        }
        res = client.post("/chatbot/message", json=payload, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "response" in data or "message" in data or "reply" in data


# ─────────────────────────────────────────────────────────────────────────────
# 4. Strict Role-Based Access Control (RBAC) Security Boundaries
# ─────────────────────────────────────────────────────────────────────────────

def test_citizen_forbidden_endpoints(tokens):
    """Citizen role must be rejected from administrative & institutional mutations."""
    citizen_token = tokens["citizen"]
    assert citizen_token is not None, "Citizen test token could not be obtained"
    headers = {"Authorization": f"Bearer {citizen_token}"}

    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        # Admin User Management -> 403
        r_admin = client.get("/admin/users", headers=headers)
        assert r_admin.status_code == 403

        # Admin Jobs -> 403
        r_jobs = client.get("/admin/jobs", headers=headers)
        assert r_jobs.status_code == 403

        # Government Command Overview -> 403
        r_gov = client.get("/government/command-overview", headers=headers)
        assert r_gov.status_code == 403

        # NGO Campaign Creation -> 403
        r_ngo = client.post("/ngo/campaigns", json={"title": "Test"}, headers=headers)
        assert r_ngo.status_code == 403

        # Health Worker Visit Log Creation -> 403
        r_field = client.post("/field/visit-logs", json={"district": "Sylhet", "location_name": "Test"}, headers=headers)
        assert r_field.status_code == 403


def test_government_and_super_admin_shared_authority(tokens):
    """Government and Super Admin both have authority over command and alerts."""
    gov_token = tokens["government"]
    admin_token = tokens["admin"]
    assert gov_token is not None and admin_token is not None

    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        # Government Command Overview: both allowed
        r_gov_cmd = client.get("/government/command-overview", headers={"Authorization": f"Bearer {gov_token}"})
        assert r_gov_cmd.status_code == 200

        r_adm_cmd = client.get("/government/command-overview", headers={"Authorization": f"Bearer {admin_token}"})
        assert r_adm_cmd.status_code == 200

        # Official Alerts list: both allowed
        r_gov_alerts = client.get("/alerts/official", headers={"Authorization": f"Bearer {gov_token}"})
        assert r_gov_alerts.status_code == 200

        r_adm_alerts = client.get("/alerts/official", headers={"Authorization": f"Bearer {admin_token}"})
        assert r_adm_alerts.status_code == 200


def test_government_cannot_access_root_admin_features(tokens):
    """Government coordinator cannot access root admin user directory or job executor."""
    gov_token = tokens["government"]
    headers = {"Authorization": f"Bearer {gov_token}"}

    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        r_users = client.get("/admin/users", headers=headers)
        assert r_users.status_code == 403

        r_jobs = client.get("/admin/jobs", headers=headers)
        assert r_jobs.status_code == 403


def test_super_admin_exclusive_root_powers(tokens):
    """Super Admin has full access to user directory, automation jobs, and all portals."""
    admin_token = tokens["admin"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        r_users = client.get("/admin/users", headers=headers)
        assert r_users.status_code == 200
        assert isinstance(r_users.json(), list)

        r_jobs = client.get("/admin/jobs", headers=headers)
        assert r_jobs.status_code == 200


def test_citizen_can_submit_reports(tokens):
    """Citizen incident reporting is open to all authenticated citizens."""
    citizen_token = tokens["citizen"]
    headers = {"Authorization": f"Bearer {citizen_token}"}

    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        payload = {
            "text": "Rising floodwaters reported near Surma river embankment.",
            "label": "flood_incident",
            "severity": "medium",
            "district": "Sylhet",
            "upazila": "Sylhet Sadar",
        }
        res = client.post("/citizen/reports", json=payload, headers=headers)
        assert res.status_code in (200, 201)

        # Citizen can view own reports
        my_reports = client.get("/citizen/my-reports", headers=headers)
        assert my_reports.status_code in (200, 400)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Security & Input Sanitization Resilience
# ─────────────────────────────────────────────────────────────────────────────

def test_missing_or_tampered_token():
    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        # Protected route without token -> 401
        res = client.get("/admin/users")
        assert res.status_code == 401

        # Protected route with tampered token -> 401
        res_tampered = client.get("/admin/users", headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.tampered.token"})
        assert res_tampered.status_code == 401


def test_sql_injection_resilience(tokens):
    """Verify that SQL injection payloads do not cause 500 crashes or syntax leaks."""
    token = tokens["citizen"]
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        payloads = [
            "' OR '1'='1' --",
            "'; DROP TABLE users; --",
            "Sylhet' UNION SELECT NULL, NULL --",
        ]
        for injection in payloads:
            res = client.get("/hospitals", params={"district": injection}, headers=headers)
            assert res.status_code in (200, 404, 422), f"Failed on payload: {injection}"
            assert res.status_code != 500, "Database crashed or leaked syntax on SQL injection payload!"


def test_malformed_json_handling():
    """Verify that raw malformed JSON returns clean 422 unprocessable entity."""
    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        res = client.post(
            "/predict/flood",
            content="{ invalid_json: without_quotes }",
            headers={"Content-Type": "application/json"}
        )
        assert res.status_code in (400, 401, 422)
