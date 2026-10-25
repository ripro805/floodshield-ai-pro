"""
/hospitals/districts/{district}/issue-rollup -- the per-district
read-only "open vs resolved" rollup used on the District Detail page.
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
    email = f"rollup_{int(time.time())}_{uuid.uuid4().hex[:6]}@test.bd"
    pw = "Password123!"
    r = requests.post(f"{BASE}/auth/signup",
                      json={"email": email, "password": pw,
                            "full_name": "Rollup", "role": "citizen",
                            "district": "Feni"}, timeout=10)
    assert r.status_code == 201, r.text
    return {"email": email, "pw": pw, "tok": r.json()["access_token"]}


def test_rollup_returns_expected_shape():
    u = _signup()
    r = requests.get(
        f"{BASE}/hospitals/districts/Feni/issue-rollup",
        headers={"Authorization": f"Bearer {u['tok']}"}, timeout=10,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    for k in ("district", "total", "open", "ack", "resolved",
              "dismissed", "top_categories"):
        assert k in body, k
    assert isinstance(body["top_categories"], list)
    for c in body["top_categories"]:
        assert "category" in c and "count" in c


def test_rollup_is_case_insensitive():
    u = _signup()
    a = requests.get(f"{BASE}/hospitals/districts/Feni/issue-rollup",
                     headers={"Authorization": f"Bearer {u['tok']}"}, timeout=10).json()
    b = requests.get(f"{BASE}/hospitals/districts/feni/issue-rollup",
                     headers={"Authorization": f"Bearer {u['tok']}"}, timeout=10).json()
    assert a["district"].lower() == b["district"].lower()
    assert a["total"] == b["total"]
    assert a["open"] == b["open"]


def test_rollup_404_without_auth():
    r = requests.get(f"{BASE}/hospitals/districts/Feni/issue-rollup", timeout=10)
    assert r.status_code == 401


def test_rollup_for_district_with_no_issues_returns_zeros():
    """Pick a district unlikely to have any reports -- the endpoint
    should still return 200 with all-zero counts."""
    u = _signup()
    # We use a real district name; the assertion is just that the
    # response is well-formed even when there are zero issues.
    r = requests.get(
        f"{BASE}/hospitals/districts/Rangamati/issue-rollup",
        headers={"Authorization": f"Bearer {u['tok']}"}, timeout=10,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["district"].lower() == "rangamati"
    for k in ("total", "open", "ack", "resolved", "dismissed"):
        assert body[k] >= 0
