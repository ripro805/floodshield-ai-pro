"""
/hospitals/{id} PATCH (ops + admin) + /hospitals/{id}/issues (all
auth'd) -- RBAC, payload validation, and audit log assertions.
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
    """Sign up a fresh citizen (the public endpoint caps at citizen)."""
    email = f"hosp_{int(time.time())}_{uuid.uuid4().hex[:6]}@test.bd"
    pw = "Password123!"
    r = requests.post(
        f"{BASE}/auth/signup",
        json={"email": email, "password": pw, "full_name": "Hosp Test",
              "role": "citizen", "district": "Feni"},
        timeout=15,
    )
    assert r.status_code in (200, 201), r.text
    r2 = requests.post(f"{BASE}/auth/login",
                       json={"email": email, "password": pw}, timeout=15)
    return {"email": email, "password": pw,
            "token": r2.json()["access_token"], "role": "citizen"}


def _promote(email: str, role: str) -> None:
    """Promote a user via direct DB write (test-only)."""
    from app.database import SessionLocal
    from app.auth_models import User, UserRole
    with SessionLocal() as db:
        u = db.query(User).filter_by(email=email).first()
        assert u is not None
        u.role = UserRole(role)
        db.commit()


def _make_user(role: str) -> dict:
    u = _signup()
    if role != "citizen":
        _promote(u["email"], role)
    r = requests.post(f"{BASE}/auth/login",
                       json={"email": u["email"], "password": u["password"]}, timeout=15)
    u["token"] = r.json()["access_token"]
    u["role"] = role
    return u


@pytest.fixture(scope="module")
def admin_u() -> dict:
    return _make_user("admin")


@pytest.fixture(scope="module")
def ops_u() -> dict:
    """An ops user (health_worker is in the standard OPERATIONAL_ROLES
    set so it has PATCH access; it's NOT in the admin metadata set)."""
    return _make_user("health_worker")


@pytest.fixture(scope="module")
def citizen_u() -> dict:
    return _make_user("citizen")


def _first_hospital_id(admin_token: str, district: str = "Feni") -> str:
    """Grab the first hospital id for a given district (defaults to
    Feni so the ops user -- who is registered to Feni -- can PATCH
    it)."""
    r = requests.get(
        f"{BASE}/hospitals?district={district}&limit=1",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    items = body if isinstance(body, list) else body.get("items", [])
    assert items, f"no hospitals in district {district}"
    return items[0]["id"]


# ─── PATCH RBAC ────────────────────────────────────────────────────

def test_patch_requires_auth():
    r = requests.patch(
        f"{BASE}/hospitals/00000000-0000-0000-0000-000000000000",
        json={"beds": 100}, timeout=10,
    )
    assert r.status_code == 401, r.text


def test_patch_citizen_forbidden(citizen_u):
    r = requests.patch(
        f"{BASE}/hospitals/00000000-0000-0000-0000-000000000000",
        json={"beds": 100},
        headers={"Authorization": f"Bearer {citizen_u['token']}"},
        timeout=10,
    )
    # 403 from require_roles
    assert r.status_code in (401, 403), r.text


def test_patch_inventory_ok_for_ops(ops_u, admin_u):
    """An ops user (health_worker) can update inventory fields."""
    hid = _first_hospital_id(admin_u["token"], "Feni")
    r = requests.get(
        f"{BASE}/hospitals/{hid}",
        headers={"Authorization": f"Bearer {ops_u['token']}"},
        timeout=10,
    )
    if r.status_code != 200:
        pytest.skip("GET /hospitals/{id} not accessible to ops")
    before = r.json().get("beds_total") or 0
    new_beds = max(1, before + 5)

    r = requests.patch(
        f"{BASE}/hospitals/{hid}",
        json={"beds": new_beds, "doctors": 7, "nurses": 21},
        headers={"Authorization": f"Bearer {ops_u['token']}"},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    j = r.json()
    h = j.get("hospital", j)
    assert h["beds"] == new_beds

    # Restore
    requests.patch(
        f"{BASE}/hospitals/{hid}",
        json={"beds": before, "doctors": 6, "nurses": 20},
        headers={"Authorization": f"Bearer {ops_u['token']}"},
        timeout=10,
    )


def test_patch_phone_ok_for_ops(ops_u, admin_u):
    """Phone is an ops-metadata field -- health_worker can write it.
    We capture the original phone (if any) and restore it so this
    test doesn't leave phone numbers on seed rows that the
    'phone_never_fabricated' test in test_hospital_directory
    depends on."""
    hid = _first_hospital_id(admin_u["token"], "Feni")
    # Capture the original phone (or NULL) so we can restore it.
    r0 = requests.get(
        f"{BASE}/hospitals/{hid}",
        headers={"Authorization": f"Bearer {ops_u['token']}"},
        timeout=10,
    )
    orig_phone = (r0.json() or {}).get("phone")  # may be None

    r = requests.patch(
        f"{BASE}/hospitals/{hid}",
        json={"phone": "+880-2-555-TEST"},
        headers={"Authorization": f"Bearer {ops_u['token']}"},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    h = r.json().get("hospital", r.json())
    assert h.get("phone") == "+880-2-555-TEST"

    # Restore -- pass the literal original value (None becomes
    # an explicit null in the payload).
    requests.patch(
        f"{BASE}/hospitals/{hid}",
        json={"phone": orig_phone},
        headers={"Authorization": f"Bearer {ops_u['token']}"},
        timeout=10,
    )


def test_patch_admin_metadata_forbidden_for_ops(ops_u, admin_u):
    """A non-admin ops user CANNOT change name/hospital_type/lat/lng."""
    hid = _first_hospital_id(admin_u["token"], "Feni")
    r = requests.patch(
        f"{BASE}/hospitals/{hid}",
        json={"name": "Hacked"},
        headers={"Authorization": f"Bearer {ops_u['token']}"},
        timeout=10,
    )
    assert r.status_code == 422, r.text
    assert "admin-only" in r.json()["detail"]


def test_patch_admin_metadata_ok_for_admin(admin_u):
    """An admin CAN change the name and coordinates."""
    hid = _first_hospital_id(admin_u["token"], "Feni")
    # Read the current name so we can restore it.
    r0 = requests.get(
        f"{BASE}/hospitals/{hid}",
        headers={"Authorization": f"Bearer {admin_u['token']}"},
        timeout=10,
    )
    orig_name = r0.json()["name"]
    new_name = orig_name + " (test)"

    r = requests.patch(
        f"{BASE}/hospitals/{hid}",
        json={"name": new_name},
        headers={"Authorization": f"Bearer {admin_u['token']}"},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    h = r.json().get("hospital", r.json())
    assert h["name"] == new_name

    # Restore
    requests.patch(
        f"{BASE}/hospitals/{hid}",
        json={"name": orig_name},
        headers={"Authorization": f"Bearer {admin_u['token']}"},
        timeout=10,
    )


def test_patch_unknown_field_422(ops_u, admin_u):
    """A typo in the field name is a 422 (not a silent drop)."""
    hid = _first_hospital_id(admin_u["token"], "Feni")
    r = requests.patch(
        f"{BASE}/hospitals/{hid}",
        json={"bedss": 100},
        headers={"Authorization": f"Bearer {ops_u['token']}"},
        timeout=10,
    )
    # Pydantic will reject the unknown field because the model
    # doesn't have `model_config = ConfigDict(extra='allow')`.
    assert r.status_code in (422, 400), r.text


def test_patch_empty_body_422(admin_u):
    hid = _first_hospital_id(admin_u["token"], "Feni")
    r = requests.patch(
        f"{BASE}/hospitals/{hid}",
        json={},
        headers={"Authorization": f"Bearer {admin_u['token']}"},
        timeout=10,
    )
    assert r.status_code == 422, r.text


def test_patch_writes_audit_log(admin_u):
    """An admin rename writes one row to hospital_updates with the
    new value captured in the `changes` JSON."""
    from app.database import SessionLocal
    from app.reference_models import HospitalUpdate

    hid = _first_hospital_id(admin_u["token"], "Feni")
    r0 = requests.get(
        f"{BASE}/hospitals/{hid}",
        headers={"Authorization": f"Bearer {admin_u['token']}"},
        timeout=10,
    )
    orig_name = r0.json()["name"]
    new_name = orig_name + " (audit-test)"

    with SessionLocal() as db:
        before = db.query(HospitalUpdate).filter_by(hospital_id=hid).count()

    r = requests.patch(
        f"{BASE}/hospitals/{hid}",
        json={"name": new_name},
        headers={"Authorization": f"Bearer {admin_u['token']}"},
        timeout=10,
    )
    assert r.status_code == 200, r.text

    with SessionLocal() as db:
        after = db.query(HospitalUpdate).filter_by(hospital_id=hid).count()
        assert after == before + 1, f"audit log not written (before={before}, after={after})"
        latest = (
            db.query(HospitalUpdate)
            .filter_by(hospital_id=hid)
            .order_by(HospitalUpdate.created_at.desc())
            .first()
        )
        assert latest is not None
        assert "name" in latest.changes
        assert latest.changes["name"]["to"] == new_name

    # Restore
    requests.patch(
        f"{BASE}/hospitals/{hid}",
        json={"name": orig_name},
        headers={"Authorization": f"Bearer {admin_u['token']}"},
        timeout=10,
    )


# ─── /hospitals/{id}/issues ────────────────────────────────────────

def test_issue_create_ok_for_citizen(citizen_u, admin_u):
    hid = _first_hospital_id(admin_u["token"], "Feni")
    r = requests.post(
        f"{BASE}/hospitals/{hid}/issues",
        json={"category": "phone_wrong", "description": "Test report from pytest"},
        headers={"Authorization": f"Bearer {citizen_u['token']}"},
        timeout=10,
    )
    assert r.status_code == 201, r.text
    j = r.json()
    assert j["status"] == "open"
    assert j["category"] == "phone_wrong"


def test_issue_create_requires_auth(admin_u):
    hid = _first_hospital_id(admin_u["token"], "Feni")
    r = requests.post(
        f"{BASE}/hospitals/{hid}/issues",
        json={"category": "phone_wrong", "description": "no auth"},
        timeout=10,
    )
    assert r.status_code == 401, r.text


def test_issue_create_invalid_category_422(citizen_u, admin_u):
    hid = _first_hospital_id(admin_u["token"], "Feni")
    r = requests.post(
        f"{BASE}/hospitals/{hid}/issues",
        json={"category": "made_up", "description": "x" * 10},
        headers={"Authorization": f"Bearer {citizen_u['token']}"},
        timeout=10,
    )
    assert r.status_code == 422, r.text


def test_issue_create_short_description_422(citizen_u, admin_u):
    hid = _first_hospital_id(admin_u["token"], "Feni")
    r = requests.post(
        f"{BASE}/hospitals/{hid}/issues",
        json={"category": "phone_wrong", "description": "no"},
        headers={"Authorization": f"Bearer {citizen_u['token']}"},
        timeout=10,
    )
    # Pydantic min_length=4
    assert r.status_code == 422, r.text


def test_issue_create_unknown_hospital_404(citizen_u):
    r = requests.post(
        f"{BASE}/hospitals/00000000-0000-0000-0000-000000000000/issues",
        json={"category": "phone_wrong", "description": "no such hospital"},
        headers={"Authorization": f"Bearer {citizen_u['token']}"},
        timeout=10,
    )
    assert r.status_code == 404, r.text


def test_issue_list_includes_created(citizen_u, admin_u):
    """The list endpoint must return the issue the test just
    created (assuming it is still 'open')."""
    hid = _first_hospital_id(admin_u["token"], "Feni")
    # Create one
    r = requests.post(
        f"{BASE}/hospitals/{hid}/issues",
        json={"category": "no_stock", "description": "Out of ORS as of 9am"},
        headers={"Authorization": f"Bearer {citizen_u['token']}"},
        timeout=10,
    )
    assert r.status_code == 201
    new_id = r.json()["id"]

    # List
    r = requests.get(
        f"{BASE}/hospitals/{hid}/issues?status=open",
        headers={"Authorization": f"Bearer {citizen_u['token']}"},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    ids = [x["id"] for x in r.json()]
    assert new_id in ids
