"""
ui_action type "open_hospital" + the post-tool ui_action emitted by
t_file_hospital_issue.  Verifies:

  - The whitelist accepts 'open_hospital' for citizens and ops.
  - The whitelist rejects bad UUIDs and missing hospital_id.
  - t_file_hospital_issue's success response includes a cleaned
    ui_action block so the chatbot widget deep-links the modal.
"""
import os
import sys
import asyncio
import time
import uuid

import pytest
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
BASE = os.environ.get("FS_API_BASE", "http://127.0.0.1:8000")


# ─── Helpers ────────────────────────────────────────────────────────

def _signup() -> dict:
    email = f"oact_{int(time.time())}_{uuid.uuid4().hex[:6]}@test.bd"
    pw = "Password123!"
    r = requests.post(
        f"{BASE}/auth/signup",
        json={"email": email, "password": pw, "full_name": "OAct",
              "role": "citizen", "district": "Feni"},
        timeout=10,
    )
    assert r.status_code == 201, r.text
    return {"email": email, "tok": r.json()["access_token"]}


def _first_hospital(token: str) -> str:
    r = requests.get(f"{BASE}/hospitals?district=Feni&limit=1",
                     headers={"Authorization": f"Bearer {token}"}, timeout=10)
    items = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
    return items[0]["id"]


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


# ─── Whitelist tests ────────────────────────────────────────────────

def test_whitelist_accepts_open_hospital_for_citizen():
    from app.services.agent_tools import whitelist_ui_action
    from app.auth_models import UserRole
    r = whitelist_ui_action(
        {"type": "open_hospital", "params": {"hospital_id": "25f18a5c-5794-4451-bd93-7cbd0430dcce"}},
        UserRole.citizen,
    )
    assert r == {
        "type": "open_hospital",
        "params": {"hospital_id": "25f18a5c-5794-4451-bd93-7cbd0430dcce"},
    }


def test_whitelist_accepts_open_hospital_for_admin():
    from app.services.agent_tools import whitelist_ui_action
    from app.auth_models import UserRole
    r = whitelist_ui_action(
        {"type": "open_hospital", "params": {"hospital_id": "25f18a5c-5794-4451-bd93-7cbd0430dcce"}},
        UserRole.admin,
    )
    assert r["type"] == "open_hospital"


def test_whitelist_accepts_open_hospital_with_district():
    from app.services.agent_tools import whitelist_ui_action
    from app.auth_models import UserRole
    r = whitelist_ui_action(
        {"type": "open_hospital", "params": {
            "hospital_id": "25f18a5c-5794-4451-bd93-7cbd0430dcce",
            "district": "Feni",
        }},
        UserRole.citizen,
    )
    assert r["params"]["district"] == "Feni"


def test_whitelist_rejects_open_hospital_with_missing_id():
    from app.services.agent_tools import whitelist_ui_action
    from app.auth_models import UserRole
    r = whitelist_ui_action({"type": "open_hospital", "params": {}}, UserRole.citizen)
    assert r.get("code") == "bad_action"


def test_whitelist_rejects_open_hospital_with_bad_uuid():
    from app.services.agent_tools import whitelist_ui_action
    from app.auth_models import UserRole
    r = whitelist_ui_action(
        {"type": "open_hospital", "params": {"hospital_id": "not-a-uuid"}},
        UserRole.citizen,
    )
    assert r.get("code") == "bad_action"


# ─── Tool-level test ────────────────────────────────────────────────

def test_file_hospital_issue_emits_ui_action():
    """When the tool succeeds, the response includes a whitelisted
    open_hospital ui_action the chatbot widget can deep-link."""
    from app.services.agent_tools import t_file_hospital_issue, whitelist_ui_action
    from app.auth_models import UserRole
    from app.database import SessionLocal
    from app.auth_models import User

    u = _signup()
    hid = _first_hospital(u["tok"])

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == u["email"]).first()
        result = _run(t_file_hospital_issue(db, user, {
            "hospital_id": hid,
            "category": "phone_wrong",
            "description": "ui action emit test",
        }))

    assert result.get("ok") is True
    assert "ui_action" in result
    ua = result["ui_action"]
    # Confirm the embedded action passes the server whitelist.
    cleaned = whitelist_ui_action(ua, UserRole.citizen)
    assert cleaned.get("type") == "open_hospital"
    assert cleaned["params"]["hospital_id"] == hid
