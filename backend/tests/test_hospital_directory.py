"""
Pytest for the Hospital Directory endpoints (Phase 3).

These tests run against a LIVE uvicorn server on http://127.0.0.1:8000
(bring it up before running `pytest -x tests/test_hospital_directory.py`).
They use a fresh citizen + admin user per session, so the test DB
just needs a working `users` + `hospitals` + `districts` schema.

The chatbot-suite-script (`test_chatbot_suite.py`) covers the LLM
fallback and conversational tool paths; this file only covers the
new directory HTTP API.
"""
import os
import time
import uuid

import pytest
import requests

BASE = os.getenv("API_BASE", "http://127.0.0.1:8000")
PWD = "Password123!"


def _signup_and_login(role_hint: str = "citizen") -> tuple[str, str]:
    """Create a fresh user and return (email, access_token)."""
    suffix = uuid.uuid4().hex[:8]
    email = f"dirtest_{role_hint}_{int(time.time())}_{suffix}@test.bd"
    r = requests.post(
        f"{BASE}/auth/signup",
        json={
            "email": email, "password": PWD,
            "full_name": "D", "district": "Feni",
        },
        timeout=30,
    )
    assert r.status_code in (200, 201), f"signup failed: {r.status_code} {r.text}"
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": PWD}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return email, r.json()["access_token"]


def _promote_to_admin(email: str) -> None:
    """Promote a user to admin via direct DB mutation.  Test-only
    path -- the production API doesn't expose user-promote (admin
    promotion is done via the existing /admin/users endpoint or the
    database directly when bootstrapping)."""
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from app.database import SessionLocal
    from app.auth_models import User, UserRole
    with SessionLocal() as db:
        u = db.query(User).filter_by(email=email).first()
        assert u is not None
        u.role = UserRole.admin
        db.commit()


@pytest.fixture(scope="module")
def citizen_token():
    _, token = _signup_and_login("citizen")
    return token


@pytest.fixture(scope="module")
def admin_token():
    email, _ = _signup_and_login("admin")
    _promote_to_admin(email)
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": PWD}, timeout=30)
    return r.json()["access_token"]


def test_districts_summary_requires_auth():
    r = requests.get(f"{BASE}/hospitals/districts-summary", timeout=30)
    assert r.status_code in (401, 403, 422)


def test_districts_summary_citizen_no_operational_fields(citizen_token):
    r = requests.get(
        f"{BASE}/hospitals/districts-summary",
        headers={"Authorization": f"Bearer {citizen_token}"},
        timeout=30,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total_districts"] == 64
    feni = next((d for d in body["items"] if d["district"] == "Feni"), None)
    assert feni is not None
    assert feni["hospital_count"] > 0
    # Citizens must not see operational field values (null or absent both OK)
    for op in ("ors_low", "iv_saline_low", "antibiotics_low"):
        assert feni.get(op) is None, f"citizen should not have {op} value"
    for op in ("total_ors", "total_iv_saline", "total_antibiotics"):
        assert feni.get(op) is None, f"citizen should not have {op} value"


def test_districts_summary_admin_has_low_stock(admin_token):
    r = requests.get(
        f"{BASE}/hospitals/districts-summary",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=30,
    )
    assert r.status_code == 200
    body = r.json()
    feni = next((d for d in body["items"] if d["district"] == "Feni"), None)
    assert feni is not None
    # Admins get real bools
    for op in ("ors_low", "iv_saline_low", "antibiotics_low"):
        assert feni.get(op) is not None
        assert isinstance(feni[op], bool)


def test_list_hospitals_citizen_no_operational_fields(citizen_token):
    r = requests.get(
        f"{BASE}/hospitals?district=Feni&limit=20",
        headers={"Authorization": f"Bearer {citizen_token}"},
        timeout=30,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["operational_fields_present"] is False
    assert body["total"] >= 1
    for it in body["items"]:
        assert "ors_stock" not in it
        assert "beds_total" not in it
        # Public fields must be present
        assert it["capacity_status"] in ("Available", "Limited", "Full")
        assert it["latitude"] is not None
        assert it["longitude"] is not None


def test_list_hospitals_admin_has_operational_fields(admin_token):
    r = requests.get(
        f"{BASE}/hospitals?district=Feni&limit=20",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=30,
    )
    body = r.json()
    assert body["operational_fields_present"] is True
    it0 = body["items"][0]
    assert "ors_stock" in it0
    assert "beds_total" in it0
    assert "occupancy_percent" in it0
    assert "ors_low" in it0
    assert "iv_saline_low" in it0
    assert "antibiotics_low" in it0


def test_nearby_returns_haversine_sorted(citizen_token):
    # Feni centroid (district row exists in the seed).
    r = requests.get(
        f"{BASE}/hospitals/nearby?lat=23.025&lng=91.4&radius_km=50&limit=5",
        headers={"Authorization": f"Bearer {citizen_token}"},
        timeout=30,
    )
    assert r.status_code == 200
    items = r.json()
    assert 1 <= len(items) <= 5
    # distances are sorted ascending
    for prev, nxt in zip(items, items[1:]):
        assert prev["distance_km"] <= nxt["distance_km"]
    # each item has a distance_km
    for it in items:
        assert it["distance_km"] >= 0


def test_nearby_out_of_range_422(citizen_token):
    r = requests.get(
        f"{BASE}/hospitals/nearby?lat=10&lng=90",
        headers={"Authorization": f"Bearer {citizen_token}"},
        timeout=30,
    )
    assert r.status_code == 422
    # 422 with a detail message
    assert "detail" in r.json() or "error" in r.text.lower()


def test_nearby_invalid_lat_422(citizen_token):
    # Latitude 99 is outside the global [-90, 90] range -- FastAPI's
    # ge= parameter check should reject this with 422.
    r = requests.get(
        f"{BASE}/hospitals/nearby?lat=99&lng=90",
        headers={"Authorization": f"Bearer {citizen_token}"},
        timeout=30,
    )
    assert r.status_code == 422


def test_single_hospital_citizen(citizen_token, admin_token):
    # Get a Feni hospital id from the admin list (admin can see all fields,
    # but we only use the id).
    r = requests.get(
        f"{BASE}/hospitals?district=Feni&limit=1",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=30,
    )
    hid = r.json()["items"][0]["id"]
    # Citizen detail
    r = requests.get(
        f"{BASE}/hospitals/{hid}",
        headers={"Authorization": f"Bearer {citizen_token}"},
        timeout=30,
    )
    assert r.status_code == 200
    body = r.json()
    assert "ors_stock" not in body, "citizen must not get ors_stock on detail"
    # Admin detail
    r = requests.get(
        f"{BASE}/hospitals/{hid}",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=30,
    )
    body = r.json()
    assert "ors_stock" in body
    assert "ors_low" in body


def test_hospitals_phone_never_fabricated(citizen_token):
    """The seed script NEVER fabricates a phone number.  Every seeded
    hospital must have phone=NULL.  This test guards against a future
    regression where a seed patch accidentally starts inventing phone
    numbers."""
    r = requests.get(
        f"{BASE}/hospitals?limit=500",
        headers={"Authorization": f"Bearer {citizen_token}"},
        timeout=30,
    )
    body = r.json()
    for it in body["items"]:
        assert it["phone"] is None, f"phone must be NULL for seed row {it['name']}"
