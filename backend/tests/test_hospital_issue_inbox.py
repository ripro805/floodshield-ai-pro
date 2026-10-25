"""
/admin/hospitals/issues (admin-only) + /admin/hospitals/issues/summary
+ PATCH /admin/hospitals/issues/{id}/status -- RBAC + summary shape +
status mutation round-trip.
"""
import os
import sys
import time
import uuid

import pytest
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
BASE = os.environ.get("FS_API_BASE", "http://127.0.0.1:8000")

# ─── Helpers ────────────────────────────────────────────────────────

def _signup(email: str = None, role: str = "citizen", district: str = "Feni") -> dict:
    email = email or f"inbox_{int(time.time())}_{uuid.uuid4().hex[:6]}@test.bd"
    pw = "Password123!"
    r = requests.post(
        f"{BASE}/auth/signup",
        json={"email": email, "password": pw, "full_name": "Inbox Test",
              "role": role, "district": district},
        timeout=10,
    )
    assert r.status_code == 201, r.text
    return {"email": email, "pw": pw}


def _login(email: str, pw: str) -> str:
    r = requests.post(
        f"{BASE}/auth/login", json={"email": email, "password": pw}, timeout=10,
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _admin_token() -> str:
    """Get an admin token by reaching into the DB and minting a JWT.
    This is the same approach the existing tests use for /hospitals/import."""
    from app.database import SessionLocal
    from app.auth_models import User, UserRole
    from jose import jwt
    from datetime import datetime, timedelta, timezone

    JWT_SECRET = os.environ.get("JWT_SECRET_KEY", "floodshield-dev-secret-change-me")
    JWT_ALG = os.environ.get("JWT_ALGORITHM", "HS256")

    with SessionLocal() as db:
        admin = db.query(User).filter(User.role == UserRole.admin).first()
        assert admin is not None, "no admin in DB; seed one before running this test"
        return jwt.encode(
            {"sub": admin.email, "role": admin.role.value,
             "exp": datetime.now(timezone.utc) + timedelta(minutes=15)},
            JWT_SECRET, algorithm=JWT_ALG,
        )


def _first_hospital_in(token: str, district: str = "Feni") -> str:
    r = requests.get(
        f"{BASE}/hospitals",
        params={"district": district, "limit": 1},
        headers={"Authorization": f"Bearer {token}"}, timeout=10,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    items = body if isinstance(body, list) else body.get("items", [])
    assert items, "no hospital found"
    return items[0]["id"]


# ─── Tests ──────────────────────────────────────────────────────────

def test_non_admin_gets_403():
    u = _signup()
    tok = _login(u["email"], u["pw"])
    r = requests.get(
        f"{BASE}/admin/hospitals/issues",
        headers={"Authorization": f"Bearer {tok}"}, timeout=10,
    )
    assert r.status_code == 403, r.text


def test_non_admin_summary_gets_403():
    u = _signup()
    tok = _login(u["email"], u["pw"])
    r = requests.get(
        f"{BASE}/admin/hospitals/issues/summary",
        headers={"Authorization": f"Bearer {tok}"}, timeout=10,
    )
    assert r.status_code == 403, r.text


def test_admin_list_returns_expected_shape():
    tok = _admin_token()
    r = requests.get(
        f"{BASE}/admin/hospitals/issues",
        params={"limit": 5},
        headers={"Authorization": f"Bearer {tok}"}, timeout=10,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "items" in body and "total" in body
    assert isinstance(body["items"], list)
    if body["items"]:
        row = body["items"][0]
        for k in ("id", "hospital_id", "hospital_name", "category",
                  "description", "status", "created_at"):
            assert k in row, f"missing key {k}"


def test_admin_summary_has_all_buckets():
    tok = _admin_token()
    r = requests.get(
        f"{BASE}/admin/hospitals/issues/summary",
        headers={"Authorization": f"Bearer {tok}"}, timeout=10,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "total" in body and "by_status" in body
    assert "by_district" in body and "by_category" in body
    assert isinstance(body["by_status"], list)
    assert isinstance(body["by_district"], list)
    assert isinstance(body["by_category"], list)


def test_filter_by_status():
    tok = _admin_token()
    r = requests.get(
        f"{BASE}/admin/hospitals/issues",
        params={"status": "open", "limit": 50},
        headers={"Authorization": f"Bearer {tok}"}, timeout=10,
    )
    assert r.status_code == 200, r.text
    for row in r.json()["items"]:
        assert row["status"] == "open"


def test_filter_by_category():
    tok = _admin_token()
    r = requests.get(
        f"{BASE}/admin/hospitals/issues",
        params={"category": "phone_wrong", "limit": 50},
        headers={"Authorization": f"Bearer {tok}"}, timeout=10,
    )
    assert r.status_code == 200, r.text
    for row in r.json()["items"]:
        assert row["category"] == "phone_wrong"


def test_filter_by_district():
    tok = _admin_token()
    r = requests.get(
        f"{BASE}/admin/hospitals/issues",
        params={"district": "Feni", "limit": 50},
        headers={"Authorization": f"Bearer {tok}"}, timeout=10,
    )
    assert r.status_code == 200, r.text
    for row in r.json()["items"]:
        assert row["district"] == "Feni"


def test_status_mutation_round_trip():
    """Create a fresh issue, ack -> resolved -> dismissed, confirm the
    PATCH endpoint enforces the write vocabulary."""
    citizen = _signup()
    ctok = _login(citizen["email"], citizen["pw"])
    hid = _first_hospital_in(ctok)
    r = requests.post(
        f"{BASE}/hospitals/{hid}/issues",
        json={"category": "phone_wrong", "description": "test inbox mutation"},
        headers={"Authorization": f"Bearer {ctok}"}, timeout=10,
    )
    assert r.status_code == 201, r.text
    issue_id = r.json()["id"]

    atok = _admin_token()
    # open -> ack
    r = requests.patch(
        f"{BASE}/admin/hospitals/issues/{issue_id}/status",
        json={"status": "ack"},
        headers={"Authorization": f"Bearer {atok}"}, timeout=10,
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ack"

    # ack -> resolved
    r = requests.patch(
        f"{BASE}/admin/hospitals/issues/{issue_id}/status",
        json={"status": "resolved"},
        headers={"Authorization": f"Bearer {atok}"}, timeout=10,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "resolved"

    # resolved -> dismissed
    r = requests.patch(
        f"{BASE}/admin/hospitals/issues/{issue_id}/status",
        json={"status": "dismissed"},
        headers={"Authorization": f"Bearer {atok}"}, timeout=10,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "dismissed"

    # open is not writable
    r = requests.patch(
        f"{BASE}/admin/hospitals/issues/{issue_id}/status",
        json={"status": "open"},
        headers={"Authorization": f"Bearer {atok}"}, timeout=10,
    )
    assert r.status_code == 422, r.text

    # invalid status
    r = requests.patch(
        f"{BASE}/admin/hospitals/issues/{issue_id}/status",
        json={"status": "banana"},
        headers={"Authorization": f"Bearer {atok}"}, timeout=10,
    )
    assert r.status_code == 422


def test_invalid_status_filter():
    tok = _admin_token()
    r = requests.get(
        f"{BASE}/admin/hospitals/issues",
        params={"status": "banana"},
        headers={"Authorization": f"Bearer {tok}"}, timeout=10,
    )
    assert r.status_code == 422


def test_invalid_category_filter():
    tok = _admin_token()
    r = requests.get(
        f"{BASE}/admin/hospitals/issues",
        params={"category": "banana"},
        headers={"Authorization": f"Bearer {tok}"}, timeout=10,
    )
    assert r.status_code == 422


def test_patch_404_for_unknown_issue():
    tok = _admin_token()
    r = requests.patch(
        f"{BASE}/admin/hospitals/issues/00000000-0000-0000-0000-000000000000/status",
        json={"status": "ack"},
        headers={"Authorization": f"Bearer {tok}"}, timeout=10,
    )
    assert r.status_code == 404


def test_non_admin_patch_gets_403():
    u = _signup()
    tok = _login(u["email"], u["pw"])
    r = requests.patch(
        f"{BASE}/admin/hospitals/issues/00000000-0000-0000-0000-000000000000/status",
        json={"status": "ack"},
        headers={"Authorization": f"Bearer {tok}"}, timeout=10,
    )
    assert r.status_code == 403
