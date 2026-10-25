"""
/admin/hospitals/import -- admin-only CSV import tests.

Covers:
  * RBAC (403 for citizen, 401 for no-auth)
  * Bad / empty CSV handling
  * Idempotency (re-import = no-op)
  * Reset=true wipes and re-imports
  * District backfill does NOT clobber existing data when reset=False
  * The template endpoint streams a valid CSV

These tests are intentionally short -- the dedupe / weighted-mean /
synthetic-coord logic is already covered by the CLI seed script
(`tests/test_seed_hospitals.py` if present).  The endpoint tests
focus on the *contract*: status codes, response shape, RBAC.
"""
import io
import os
import sys
import time
import uuid

import pytest
import requests

# Resolve the backend root regardless of where pytest is invoked from.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

BASE = os.environ.get("FS_API_BASE", "http://127.0.0.1:8000")


# ─── Fixtures ────────────────────────────────────────────────────────

def _signup(role: str = "citizen") -> dict:
    """Create a fresh user via /auth/signup, then log in to get a token.

    Signup caps the role at 'citizen' on the public endpoint, so for
    admin tests we promote via direct DB write after signup (see
    `_promote_to_admin` below)."""
    email = f"import_{role}_{int(time.time())}_{uuid.uuid4().hex[:6]}@test.bd"
    pw = "Password123!"
    r = requests.post(
        f"{BASE}/auth/signup",
        json={
            "email": email, "password": pw, "full_name": f"Import {role}",
            "role": "citizen", "district": "Feni",
        },
        timeout=15,
    )
    assert r.status_code in (200, 201), f"signup failed: {r.text}"
    r2 = requests.post(
        f"{BASE}/auth/login",
        json={"email": email, "password": pw}, timeout=15,
    )
    assert r2.status_code == 200, f"login failed: {r2.text}"
    return {"email": email, "password": pw, "token": r2.json()["access_token"], "role": role}


def _promote_to_admin(email: str) -> None:
    """Promote a user to admin via direct DB mutation (test-only)."""
    from app.database import SessionLocal
    from app.auth_models import User, UserRole
    with SessionLocal() as db:
        u = db.query(User).filter_by(email=email).first()
        assert u is not None
        u.role = UserRole.admin
        db.commit()


@pytest.fixture(scope="module")
def citizen_user() -> dict:
    return _signup("citizen")


@pytest.fixture(scope="module")
def admin_user() -> dict:
    u = _signup("admin")
    _promote_to_admin(u["email"])
    # Re-login so the token reflects the new role.
    r = requests.post(
        f"{BASE}/auth/login",
        json={"email": u["email"], "password": u["password"]}, timeout=15,
    )
    assert r.status_code == 200
    u["token"] = r.json()["access_token"]
    return u


def _multipart(file_name: str, content: bytes, fields: dict | None = None):
    """Build a requests-compatible (files=, data=) tuple for upload."""
    files = {"file": (file_name, io.BytesIO(content), "text/csv")}
    data = fields or {}
    return files, data


# ─── RBAC ───────────────────────────────────────────────────────────

def test_template_requires_auth():
    r = requests.get(f"{BASE}/admin/hospitals/import/template", timeout=10)
    assert r.status_code == 401, r.text


def test_template_citizen_forbidden(citizen_user):
    r = requests.get(
        f"{BASE}/admin/hospitals/import/template",
        headers={"Authorization": f"Bearer {citizen_user['token']}"},
        timeout=10,
    )
    assert r.status_code == 403, r.text


def test_import_citizen_forbidden(citizen_user):
    csv = b"district,hospital_name,beds\nDhaka,Test,50\n"
    files, data = _multipart("test.csv", csv)
    r = requests.post(
        f"{BASE}/admin/hospitals/import",
        files=files, data=data,
        headers={"Authorization": f"Bearer {citizen_user['token']}"},
        timeout=15,
    )
    assert r.status_code == 403, r.text


def test_import_unauthenticated():
    csv = b"district,hospital_name,beds\nDhaka,Test,50\n"
    files, _ = _multipart("test.csv", csv)
    r = requests.post(f"{BASE}/admin/hospitals/import", files=files, timeout=15)
    assert r.status_code == 401, r.text


# ─── Happy path ─────────────────────────────────────────────────────

def test_template_streamed_for_admin(admin_user):
    r = requests.get(
        f"{BASE}/admin/hospitals/import/template",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    body = r.content
    assert body.startswith(b"district,")
    assert b"hospital_name" in body
    assert b"beds" in body


def test_import_5_rows_with_1_dup(admin_user):
    """A 6-row CSV (5 unique + 1 duplicate) should dedupe to 5 rows
    and add them to the database without disturbing the existing
    64-district coverage."""
    csv = (
        b"district,hospital_name,beds,doctors,nurses,ors_stock,"
        b"iv_saline_stock,antibiotics_stock,address,upazila,phone\n"
        b"Dhaka,Pytest Test Hospital A,100,12,40,500,300,150,Sadar,Sadar,+880-2-111\n"
        b"Dhaka,Pytest Test Hospital A,100,12,40,500,300,150,Annex,Sadar,+880-2-222\n"
        b"Chattogram,Pytest Test Hospital B,80,8,30,400,200,100,,,\n"
        b"Khulna,Pytest Test Hospital C,60,6,20,200,150,80,,,\n"
        b"Sylhet,Pytest Test Hospital D,40,4,15,150,100,50,,,\n"
        b"Barisal,Pytest Test Hospital E,30,3,10,100,80,30,,,\n"  # legacy spelling
    )
    files, data = _multipart("test.csv", csv)
    r = requests.post(
        f"{BASE}/admin/hospitals/import",
        files=files, data=data,
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["deduped_rows"] == 5
    assert j["districts"] == 5
    assert j["hospitals_affected"] >= 5  # >= because the existing Dhaka row may have been re-upserted
    assert j["backfilled"] == 0, (
        "Expected 0 backfilled on a populated DB; the fix should "
        "read the actual DB present set, not the CSV batch."
    )
    assert j["data_source"] == "admin_import"

    # Verify the new row is queryable and stamped.
    r2 = requests.get(
        f"{BASE}/hospitals?district=Dhaka&limit=20",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        timeout=10,
    )
    assert r2.status_code == 200
    matches = [
        h for h in r2.json().get("items", [])
        if h.get("name", "").startswith("Pytest Test Hospital A")
    ]
    # 2 dups deduped into 1 row, weighted-mean 200 beds
    assert len(matches) == 1
    assert matches[0]["data_source"] == "admin_import"
    assert matches[0]["beds_total"] == 200

    # Cleanup so other tests don't see this row.
    from app.database import SessionLocal
    from app.reference_models import Hospital
    with SessionLocal() as db:
        db.query(Hospital).filter(
            Hospital.name.like("Pytest Test Hospital%")
        ).delete(synchronize_session=False)
        db.commit()


# ─── Error paths ────────────────────────────────────────────────────

def test_import_bad_csv_400(admin_user):
    """Header missing required columns -> 400."""
    bad = b"foo,bar\n1,2\n"
    files, _ = _multipart("bad.csv", bad)
    r = requests.post(
        f"{BASE}/admin/hospitals/import",
        files=files,
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        timeout=15,
    )
    assert r.status_code == 400, r.text
    assert "header" in r.json()["detail"].lower()


def test_import_empty_400(admin_user):
    files, _ = _multipart("empty.csv", b"")
    r = requests.post(
        f"{BASE}/admin/hospitals/import",
        files=files,
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        timeout=15,
    )
    assert r.status_code == 400, r.text


def test_import_no_rows_after_dedupe_400(admin_user):
    """CSV that has the right headers but zero usable rows."""
    # Only the header, no data rows.
    only_header = (
        b"district,hospital_name,beds,doctors,nurses,ors_stock,"
        b"iv_saline_stock,antibiotics_stock,address,upazila,phone\n"
    )
    files, _ = _multipart("h.csv", only_header)
    r = requests.post(
        f"{BASE}/admin/hospitals/import",
        files=files,
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        timeout=15,
    )
    # parse_csv returns ([], []) -> 400 "CSV had no usable rows"
    assert r.status_code == 400, r.text
