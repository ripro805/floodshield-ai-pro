"""
POST /admin/hospitals/issues/status -- bulk ack/resolve/dismiss.

Distinct from PATCH /admin/hospitals/issues/{issue_id}/status (the
single-row path used by the per-row buttons).  Bulk takes a list of
ids and a target status; unknown ids come back in `not_found` so
the UI can show a partial-success banner.
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


def _signup() -> dict:
    email = f"bulk_{int(time.time())}_{uuid.uuid4().hex[:6]}@test.bd"
    pw = "Password123!"
    r = requests.post(
        f"{BASE}/auth/signup",
        json={"email": email, "password": pw, "full_name": "Bulk",
              "role": "citizen", "district": "Feni"},
        timeout=10,
    )
    assert r.status_code == 201, r.text
    return {"email": email, "pw": pw, "tok": r.json()["access_token"]}


def _admin_token() -> str:
    from app.database import SessionLocal
    from app.auth_models import User, UserRole
    from jose import jwt
    from datetime import datetime, timedelta, timezone
    JWT_SECRET = os.environ.get("JWT_SECRET_KEY", "floodshield-dev-secret-change-me")
    JWT_ALG = os.environ.get("JWT_ALGORITHM", "HS256")
    with SessionLocal() as db:
        admin = db.query(User).filter(User.role == UserRole.admin).first()
        return jwt.encode(
            {"sub": admin.email, "role": admin.role.value,
             "exp": datetime.now(timezone.utc) + timedelta(minutes=15)},
            JWT_SECRET, algorithm=JWT_ALG,
        )


def _first_hospital(token: str) -> str:
    r = requests.get(f"{BASE}/hospitals?district=Feni&limit=1",
                     headers={"Authorization": f"Bearer {token}"}, timeout=10)
    items = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
    return items[0]["id"]


def _file_issue(token: str, hid: str, descr: str) -> str:
    r = requests.post(
        f"{BASE}/hospitals/{hid}/issues",
        json={"category": "phone_wrong", "description": descr},
        headers={"Authorization": f"Bearer {token}"}, timeout=10,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ─── Tests ──────────────────────────────────────────────────────────

def test_non_admin_gets_403():
    u = _signup()
    r = requests.post(
        f"{BASE}/admin/hospitals/issues/status",
        json={"issue_ids": ["00000000-0000-0000-0000-000000000000"], "status": "ack"},
        headers={"Authorization": f"Bearer {u['tok']}"}, timeout=10,
    )
    assert r.status_code == 403, r.text


def test_unauthenticated_gets_401():
    r = requests.post(
        f"{BASE}/admin/hospitals/issues/status",
        json={"issue_ids": ["00000000-0000-0000-0000-000000000000"], "status": "ack"},
        timeout=10,
    )
    assert r.status_code == 401, r.text


def test_bulk_acks_multiple_issues():
    u = _signup()
    hid = _first_hospital(u["tok"])
    ids = [_file_issue(u["tok"], hid, f"bulk ack test {i}") for i in range(3)]
    atok = _admin_token()
    r = requests.post(
        f"{BASE}/admin/hospitals/issues/status",
        json={"issue_ids": ids, "status": "ack"},
        headers={"Authorization": f"Bearer {atok}"}, timeout=10,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["requested"] == 3
    assert body["updated"] == 3
    assert body["not_found"] == []
    assert body["status"] == "ack"

    # Confirm they actually flipped
    r2 = requests.get(
        f"{BASE}/admin/hospitals/issues",
        params={"status": "ack", "limit": 100},
        headers={"Authorization": f"Bearer {atok}"}, timeout=10,
    )
    statuses = {i["id"]: i["status"] for i in r2.json()["items"]}
    for i in ids:
        assert statuses.get(i) == "ack", f"{i} not acked: {statuses.get(i)}"


def test_bulk_partial_unknown_ids_returns_not_found():
    u = _signup()
    hid = _first_hospital(u["tok"])
    real = _file_issue(u["tok"], hid, "bulk partial test")
    bogus = "00000000-0000-0000-0000-000000000000"
    atok = _admin_token()
    r = requests.post(
        f"{BASE}/admin/hospitals/issues/status",
        json={"issue_ids": [real, bogus], "status": "resolved"},
        headers={"Authorization": f"Bearer {atok}"}, timeout=10,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["updated"] == 1
    assert body["not_found"] == [bogus]


def test_bulk_dedupes_input_ids():
    u = _signup()
    hid = _first_hospital(u["tok"])
    iid = _file_issue(u["tok"], hid, "bulk dedupe test")
    atok = _admin_token()
    r = requests.post(
        f"{BASE}/admin/hospitals/issues/status",
        json={"issue_ids": [iid, iid, iid], "status": "dismissed"},
        headers={"Authorization": f"Bearer {atok}"}, timeout=10,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["requested"] == 1
    assert body["updated"] == 1


def test_bulk_rejects_open_status():
    atok = _admin_token()
    r = requests.post(
        f"{BASE}/admin/hospitals/issues/status",
        json={"issue_ids": ["00000000-0000-0000-0000-000000000000"], "status": "open"},
        headers={"Authorization": f"Bearer {atok}"}, timeout=10,
    )
    assert r.status_code == 422, r.text


def test_bulk_rejects_invalid_uuid():
    atok = _admin_token()
    r = requests.post(
        f"{BASE}/admin/hospitals/issues/status",
        json={"issue_ids": ["not-a-uuid"], "status": "ack"},
        headers={"Authorization": f"Bearer {atok}"}, timeout=10,
    )
    assert r.status_code == 200, r.text  # the endpoint treats bad UUIDs as not_found, not 422
    body = r.json()
    assert body["updated"] == 0
    assert "not-a-uuid" in body["not_found"]


def test_bulk_rejects_empty_list():
    atok = _admin_token()
    r = requests.post(
        f"{BASE}/admin/hospitals/issues/status",
        json={"issue_ids": [], "status": "ack"},
        headers={"Authorization": f"Bearer {atok}"}, timeout=10,
    )
    assert r.status_code == 422, r.text


def test_bulk_caps_at_200_ids():
    atok = _admin_token()
    r = requests.post(
        f"{BASE}/admin/hospitals/issues/status",
        json={"issue_ids": ["00000000-0000-0000-0000-000000000000"] * 201,
              "status": "ack"},
        headers={"Authorization": f"Bearer {atok}"}, timeout=10,
    )
    assert r.status_code == 422, r.text
