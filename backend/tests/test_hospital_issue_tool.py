"""
t_file_hospital_issue -- the agent tool that lets the chatbot
auto-file a user complaint against a specific hospital.
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

def _signup() -> dict:
    email = f"tool_{int(time.time())}_{uuid.uuid4().hex[:6]}@test.bd"
    pw = "Password123!"
    r = requests.post(
        f"{BASE}/auth/signup",
        json={"email": email, "password": pw, "full_name": "Tool Test",
              "role": "citizen", "district": "Feni"},
        timeout=10,
    )
    assert r.status_code == 201, r.text
    return {"email": email, "pw": pw, "token": r.json()["access_token"]}


def _login(email: str, pw: str) -> str:
    r = requests.post(f"{BASE}/auth/login",
                      json={"email": email, "password": pw}, timeout=10)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _first_hospital(token: str) -> dict:
    r = requests.get(f"{BASE}/hospitals?district=Feni&limit=1",
                     headers={"Authorization": f"Bearer {token}"}, timeout=10)
    assert r.status_code == 200, r.text
    body = r.json()
    items = body if isinstance(body, list) else body.get("items", [])
    assert items
    return items[0]


# ─── Tests ──────────────────────────────────────────────────────────

def test_tool_filing_succeeds_and_lands_in_inbox():
    u = _signup()
    h = _first_hospital(u["token"])
    # Invoke the tool directly via the agent endpoint that runs tools.
    # We do this by calling a real /chatbot/chat with a careful prompt
    # is too flaky -- instead we use the same DB session the tool uses.
    from app.database import SessionLocal
    from app.auth_models import User
    from app.services.agent_tools import t_file_hospital_issue

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == u["email"]).first()
        result = await_run(t_file_hospital_issue, db, user, {
            "hospital_id": h["id"],
            "category": "phone_wrong",
            "description": "The phone number doesn't connect.",
        })
    assert result.get("ok") is True, result
    assert result["status"] == "open"
    assert result["category"] == "phone_wrong"
    # And the new issue shows up in /admin/hospitals/issues
    atok = _admin_token()
    r = requests.get(
        f"{BASE}/admin/hospitals/issues",
        params={"status": "open", "category": "phone_wrong", "limit": 50},
        headers={"Authorization": f"Bearer {atok}"}, timeout=10,
    )
    assert r.status_code == 200
    assert any(i["id"] == result["issue_id"] for i in r.json()["items"]), \
        "newly filed issue should be in admin inbox"


def test_tool_rejects_unknown_hospital_id():
    u = _signup()
    from app.database import SessionLocal
    from app.auth_models import User
    from app.services.agent_tools import t_file_hospital_issue
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == u["email"]).first()
        result = await_run(t_file_hospital_issue, db, user, {
            "hospital_id": "00000000-0000-0000-0000-000000000000",
            "category": "other",
            "description": "ghost hospital",
        })
    assert result.get("code") == "not_found"


def test_tool_rejects_invalid_category():
    u = _signup()
    h = _first_hospital(u["token"])
    from app.database import SessionLocal
    from app.auth_models import User
    from app.services.agent_tools import t_file_hospital_issue
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == u["email"]).first()
        result = await_run(t_file_hospital_issue, db, user, {
            "hospital_id": h["id"],
            "category": "banana",
            "description": "x",
        })
    assert result.get("code") == "bad_input"


def test_tool_rejects_missing_description():
    u = _signup()
    h = _first_hospital(u["token"])
    from app.database import SessionLocal
    from app.auth_models import User
    from app.services.agent_tools import t_file_hospital_issue
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == u["email"]).first()
        result = await_run(t_file_hospital_issue, db, user, {
            "hospital_id": h["id"],
            "category": "no_doctor",
            "description": "  ",
        })
    assert result.get("code") == "missing_input"


def test_tool_rejects_invalid_uuid():
    u = _signup()
    from app.database import SessionLocal
    from app.auth_models import User
    from app.services.agent_tools import t_file_hospital_issue
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == u["email"]).first()
        result = await_run(t_file_hospital_issue, db, user, {
            "hospital_id": "not-a-uuid",
            "category": "other",
            "description": "x",
        })
    assert result.get("code") == "bad_input"


def test_tool_visible_in_tool_schema():
    """The schema advertised to the LLM must include the new tool."""
    from app.services.agent_tools import TOOL_SCHEMAS
    names = [t["name"] for t in TOOL_SCHEMAS]
    assert "file_hospital_issue" in names
    tool = next(t for t in TOOL_SCHEMAS if t["name"] == "file_hospital_issue")
    assert "hospital_id" in tool["input_schema"]["properties"]
    assert "category" in tool["input_schema"]["properties"]
    assert "description" in tool["input_schema"]["properties"]
    assert set(tool["input_schema"]["required"]) == {"hospital_id", "category", "description"}


# ─── Internal helpers ───────────────────────────────────────────────

import asyncio
def await_run(coro_fn, *args, **kwargs):
    """Run a coroutine in a fresh event loop (pytest is sync)."""
    return asyncio.new_event_loop().run_until_complete(coro_fn(*args, **kwargs))


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
