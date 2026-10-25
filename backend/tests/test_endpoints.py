"""
Run with: pytest tests/ -v
(run from the backend/ root so the `app` package is importable)

Note: TestClient must be used as a context manager (`with TestClient(app) as client`)
for FastAPI's lifespan startup event to fire and actually load the models --
otherwise every route sees `models.loaded == False` and crashes on None.
"""
import os
import joblib
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import MODELS_DIR


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def auth_headers(client):
    """A citizen-role account -- enough for all /predict/* and /satellite/* endpoints."""
    import uuid
    email = f"testcitizen-{uuid.uuid4().hex[:8]}@example.com"
    r = client.post("/auth/signup", json={
        "email": email, "password": "testpassword123", "full_name": "Fixture Citizen"
    })
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def hospital_headers(client):
    """A hospital-role account -- needed for /recommend and /predict/full-assessment."""
    import uuid
    email = f"testhospital-{uuid.uuid4().hex[:8]}@example.com"
    r = client.post("/auth/signup", json={
        "email": email, "password": "testpassword123", "full_name": "Fixture Hospital",
        "role": "hospital", "district": "Munshiganj"
    })
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

DISEASE_PAYLOAD = {
    "rainfall_mm": 220, "temperature_c": 29, "humidity_percent": 87,
    "river_level_m": 7.5, "flood_depth_cm": 55, "population_density": 2100,
    "sanitation_score": 0.35, "water_quality_index": 50,
    "previous_week_cases": 210, "previous_two_week_cases": 190, "season": "Monsoon"
}


def test_health(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["models_loaded"] is True


def test_location_search_returns_real_district_or_upazila(client):
    r = client.get("/api/locations/search?q=Feni")
    assert r.status_code == 200
    assert any(item["district"] == "Feni" for item in r.json()["results"])


def test_weather_history_endpoint_is_available(client):
    r = client.get("/api/weather/history", params={"location": "Feni"})
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_monitoring_summary_requires_operational_role(client, hospital_headers):
    r = client.get("/monitoring/summary", headers=hospital_headers)
    assert r.status_code == 200
    assert "prediction_count" in r.json()


def test_flood_prediction(client, auth_headers):
    r = client.post("/predict/flood", json={
        "rainfall_mm": 180, "river_level_m": 8.5, "humidity_percent": 88,
        "temperature_c": 29, "elevation_m": 5, "water_quality_index": 60,
        "population_density": 1800, "season": "Monsoon"
    }, headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert 0 <= body["flood_probability"] <= 1
    assert body["flood_risk_level"] in ["Low", "Medium", "High"]
    assert body["feature_importance"]
    assert {"feature", "importance", "value"}.issubset(body["feature_importance"][0])
    history = client.get("/history/predictions?model_name=flood", headers=auth_headers)
    assert history.status_code == 200
    assert any(item["model_name"] == "flood" for item in history.json())


def test_flood_prediction_rejects_negative_rainfall(client, auth_headers):
    r = client.post("/predict/flood", json={
        "rainfall_mm": -5, "river_level_m": 8.5, "humidity_percent": 88, "temperature_c": 29
    }, headers=auth_headers)
    assert r.status_code == 422


def test_disease_prediction(client, auth_headers):
    r = client.post("/predict/disease", json=DISEASE_PAYLOAD, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["predicted_outbreak_risk"] in ["Medium", "High", "Critical"]
    assert r.json()["feature_importance"]


def test_risk_score(client, auth_headers):
    r = client.post("/predict/risk", json=DISEASE_PAYLOAD, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["final_risk_level"] in ["Low", "Medium", "High", "Critical"]


def test_disease_hotspots_use_real_district_data(client, auth_headers):
    r = client.get("/predict/hotspots", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["algorithm"] == "DBSCAN"
    assert body["source"].endswith((
        "water_risk_dataset.csv.xls",
        "climate_dataset_fixed.xlsx",
    ))
    assert body["cluster_count"] >= 1
    assert len(body["districts"]) >= 2
    assert {"district", "cluster_id", "is_noise"}.issubset(body["districts"][0])


def test_sms_subscription_lifecycle(client, auth_headers):
    r = client.post("/alerts/sms/subscribe", json={
        "phone_number": "+8801712345678", "district": "Feni", "risk_threshold": "High"
    }, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["is_active"] is True

    r = client.get("/alerts/sms/subscription", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["district"] == "Feni"

    r = client.delete("/alerts/sms/unsubscribe", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "unsubscribed"


def test_recommend(client, hospital_headers):
    r = client.post("/recommend", json={"district": "Munshiganj", "risk_level": "Critical"}, headers=hospital_headers)
    assert r.status_code == 200
    assert len(r.json()["recommendations"]) > 0


def test_recommend_unknown_district(client, hospital_headers):
    r = client.post("/recommend", json={"district": "NotARealPlace", "risk_level": "Low"}, headers=hospital_headers)
    assert r.status_code == 404


def test_full_assessment(client, hospital_headers):
    payload = dict(DISEASE_PAYLOAD)
    payload["district"] = "Munshiganj"
    r = client.post("/predict/full-assessment", json=payload, headers=hospital_headers)
    assert r.status_code == 200
    body = r.json()
    assert "risk_assessment" in body and "recommendation" in body


def test_forecast(client, auth_headers):
    scalers = joblib.load(os.path.join(MODELS_DIR, "timeseries_scalers.pkl"))
    district = list(scalers.keys())[0]
    payload = {
        "district": district,
        "recent_weeks": [
            {"weekly_cases": 120, "rainfall_mm": 90, "temperature_c": 28,
             "flood_depth_cm": 20, "sanitation_score": 0.5}
        ] * 8
    }
    r = client.post("/predict/forecast", json=payload, headers=auth_headers)
    assert r.status_code == 200
    assert "forecast_next_7_days_cases" in r.json()


def test_forecast_unknown_district(client, auth_headers):
    payload = {
        "district": "NotARealDistrict",
        "recent_weeks": [
            {"weekly_cases": 120, "rainfall_mm": 90, "temperature_c": 28,
             "flood_depth_cm": 20, "sanitation_score": 0.5}
        ] * 8
    }
    r = client.post("/predict/forecast", json=payload, headers=auth_headers)
    assert r.status_code == 404


def test_satellite_flood_extent_list(client, auth_headers):
    r = client.get("/satellite/flood-extent", headers=auth_headers)
    assert r.status_code == 200
    assert "Feni" in r.json()["available_districts"]


def test_satellite_flood_extent_feni(client, auth_headers):
    r = client.get("/satellite/flood-extent/Feni", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["geojson"]["type"] is not None


def test_satellite_ingest_returns_json_safe_chip(client, auth_headers):
    r = client.get("/satellite/ingest", params={"district": "Feni"}, headers=auth_headers)
    assert r.status_code in [200, 404, 503]
    if r.status_code == 200:
        pixels = r.json()["pixel_values"]
        assert len(pixels) == 256
        assert len(pixels[0]) == 256
        assert len(pixels[0][0]) == 2


# ---------- Auth / Role-based access tests ----------

def _unique_email(prefix):
    import uuid
    return f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"


def test_signup_and_login(client):
    email = _unique_email("citizen")
    r = client.post("/auth/signup", json={
        "email": email, "password": "testpassword123",
        "full_name": "Test Citizen", "role": "citizen"
    })
    assert r.status_code == 201
    assert r.json()["user"]["role"] == "citizen"

    r = client.post("/auth/login", json={"email": email, "password": "testpassword123"})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_signup_duplicate_email_rejected(client):
    email = _unique_email("dup")
    client.post("/auth/signup", json={"email": email, "password": "testpassword123", "full_name": "A"})
    r = client.post("/auth/signup", json={"email": email, "password": "testpassword123", "full_name": "B"})
    assert r.status_code == 400


def test_login_wrong_password_rejected(client):
    email = _unique_email("wrongpass")
    client.post("/auth/signup", json={"email": email, "password": "testpassword123", "full_name": "A"})
    r = client.post("/auth/login", json={"email": email, "password": "wrongpassword"})
    assert r.status_code == 401


def test_protected_endpoint_requires_token(client):
    r = client.post("/predict/flood", json={
        "rainfall_mm": 180, "river_level_m": 8.5, "humidity_percent": 88, "temperature_c": 29
    })
    assert r.status_code == 401


def test_citizen_can_call_prediction_endpoints(client):
    email = _unique_email("citizen2")
    signup = client.post("/auth/signup", json={"email": email, "password": "testpassword123", "full_name": "A"})
    token = signup.json()["access_token"]

    r = client.post("/predict/flood", json={
        "rainfall_mm": 180, "river_level_m": 8.5, "humidity_percent": 88, "temperature_c": 29
    }, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


def test_citizen_cannot_call_recommend(client):
    email = _unique_email("citizen3")
    signup = client.post("/auth/signup", json={"email": email, "password": "testpassword123", "full_name": "A"})
    token = signup.json()["access_token"]

    r = client.post("/recommend", json={"district": "Munshiganj", "risk_level": "Critical"},
                     headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_hospital_role_can_call_recommend(client):
    email = _unique_email("hospital")
    signup = client.post("/auth/signup", json={
        "email": email, "password": "testpassword123", "full_name": "A",
        "role": "hospital", "district": "Munshiganj"
    })
    token = signup.json()["access_token"]

    r = client.post("/recommend", json={"district": "Munshiganj", "risk_level": "Critical"},
                     headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
