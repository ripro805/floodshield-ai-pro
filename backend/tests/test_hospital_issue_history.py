"""
GET /hospitals/{id}/issue-history -- the per-hospital chronological
timeline.  Verifies that single PATCH /admin/hospitals/issues/{id}/status
and POST /admin/hospitals/issues/status both write the audit columns
that the history endpoint surfaces.
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
    email = f"hist_{int(time.time())}_{uuid.uuid4().hex[:6]}@test.bd"
    pw = "Password123!"
    r = requests.post(
        f"{BASE}/auth/signup",
        json={"email": email, "password": pw, "full_name": "Hist",
              "role": "citizen", "district": "Feni"},
        timeout=10,
    )
    assert r.status_code == 201, r.text
    return {"email": email, "tok": r.json()["access_token"]}


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


# ─── Tests ──────────────────────────────────────────────────────────

def test_history_requires_auth():
    r = requests.get(
        f"{BASE}/hospitals/00000000-0000-0000-0000-000000000000/issue-history",
        timeout=10,
    )
    assert r.status_code == 401


def test_history_rejects_invalid_uuid():
    u = _signup()
    r = requests.get(
        f"{BASE}/hospitals/not-a-uuid/issue-history",
        headers={"Authorization": f"Bearer {u['tok']}"}, timeout=10,
    )
    assert r.status_code == 422


def test_history_404_for_unknown_hospital():
    u = _signup()
    r = requests.get(
        f"{BASE}/hospitals/00000000-0000-0000-0000-000000000000/issue-history",
        headers={"Authorization": f"Bearer {u['tok']}"}, timeout=10,
    )
    assert r.status_code == 404


def test_history_records_audit_columns_on_single_patch():
    """File an issue, ack it via the admin PATCH, then read the
    history endpoint and confirm the ack event is present."""
    u = _signup()
    hid = _first_hospital(u["tok"])
    r = requests.post(
        f"{BASE}/hospitals/{hid}/issues",
        json={"category": "phone_wrong", "description": "history ack test"},
        headers={"Authorization": f"Bearer {u['tok']}"}, timeout=10,
    )
    assert r.status_code == 201
    iid = r.json()["id"]

    atok = _admin_token()
    r = requests.patch(
        f"{BASE}/admin/hospitals/issues/{iid}/status",
        json={"status": "ack"},
        headers={"Authorization": f"Bearer {atok}"}, timeout=10,
    )
    assert r.status_code == 200

    r = requests.get(
        f"{BASE}/hospitals/{hid}/issue-history",
        headers={"Authorization": f"Bearer {u['tok']}"}, timeout=10,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    kinds_for_issue = [e for e in body["events"] if e["issue_id"] == iid]
    assert any(e["kind"] == "reported" for e in kinds_for_issue)
    assert any(e["kind"] == "ack" for e in kinds_for_issue)
    # Resolved/dismissed are not in the stream yet.
    assert not any(e["kind"] == "resolved" for e in kinds_for_issue)


def test_history_records_audit_columns_on_bulk_patch():
    """File two issues, bulk-ack, then check the history endpoint."""
    u = _signup()
    hid = _first_hospital(u["tok"])
    ids = []
    for i in range(2):
        r = requests.post(
            f"{BASE}/hospitals/{hid}/issues",
            json={"category": "no_stock", "description": f"history bulk {i}"},
            headers={"Authorization": f"Bearer {u['tok']}"}, timeout=10,
        )
        ids.append(r.json()["id"])

    atok = _admin_token()
    r = requests.post(
        f"{BASE}/admin/hospitals/issues/status",
        json={"issue_ids": ids, "status": "resolved"},
        headers={"Authorization": f"Bearer {atok}"}, timeout=10,
    )
    assert r.status_code == 200
    assert r.json()["updated"] == 2

    r = requests.get(
        f"{BASE}/hospitals/{hid}/issue-history",
        headers={"Authorization": f"Bearer {u['tok']}"}, timeout=10,
    )
    body = r.json()
    for iid in ids:
        kinds = [e["kind"] for e in body["events"] if e["issue_id"] == iid]
        assert "reported" in kinds
        assert "resolved" in kinds


def test_history_preserves_first_audit_timestamp():
    """If the same row is acked twice, the first ack_at is preserved."""
    u = _signup()
    hid = _first_hospital(u["tok"])
    r = requests.post(
        f"{BASE}/hospitals/{hid}/issues",
        json={"category": "other", "description": "first-wins"},
        headers={"Authorization": f"Bearer {u['tok']}"}, timeout=10,
    )
    iid = r.json()["id"]

    atok = _admin_token()
    requests.patch(f"{BASE}/admin/hospitals/issues/{iid}/status",
                   json={"status": "ack"},
                   headers={"Authorization": f"Bearer {atok}"}, timeout=10)
    time.sleep(0.05)
    requests.patch(f"{BASE}/admin/hospitals/issues/{iid}/status",
                   json={"status": "ack"},
                   headers={"Authorization": f"Bearer {atok}"}, timeout=10)

    r = requests.get(
        f"{BASE}/hospitals/{hid}/issue-history",
        headers={"Authorization": f"Bearer {u['tok']}"}, timeout=10,
    )
    body = r.json()
    ack_events = [e for e in body["events"]
                  if e["issue_id"] == iid and e["kind"] == "ack"]
    assert len(ack_events) == 1, "should only have ONE ack event per issue"


def test_history_events_are_newest_first():
    u = _signup()
    hid = _first_hospital(u["tok"])
    for i in range(3):
        requests.post(
            f"{BASE}/hospitals/{hid}/issues",
            json={"category": "other", "description": f"order {i}"},
            headers={"Authorization": f"Bearer {u['tok']}"}, timeout=10,
        )
        time.sleep(0.05)
    r = requests.get(
        f"{BASE}/hospitals/{hid}/issue-history",
        headers={"Authorization": f"Bearer {u['tok']}"}, timeout=10,
    )
    body = r.json()
    ats = [e["at"] for e in body["events"]]
    assert ats == sorted(ats, reverse=True)


def test_history_respects_limit():
    u = _signup()
    hid = _first_hospital(u["tok"])
    r = requests.get(
        f"{BASE}/hospitals/{hid}/issue-history?limit=5",
        headers={"Authorization": f"Bearer {u['tok']}"}, timeout=10,
    )
    assert r.status_code == 200
    body = r.json()
    # At most 5 rows * 4 events = 20 events, but the limit is on rows
    assert body["total"] <= 5
