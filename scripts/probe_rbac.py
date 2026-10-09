"""Verify:
  1) admin user gets `recommendation` in the response
  2) citizen user does NOT get `recommendation` (server-side stripped)
  3) Different districts return different flood/forecast values
  4) The /assessment endpoint does not call satellite/segment auto.
"""
import json
import time
import httpx

BASE = "http://127.0.0.1:8000"

def login_as(role: str):
    email = f"{role}-{int(time.time()*1000)}@example.com"
    password = "Probe123!@#"
    with httpx.Client(base_url=BASE, timeout=30) as cx:
        cx.post("/auth/signup", json={"email": email, "password": password, "full_name": role.title(), "role": role}).raise_for_status()
        r = cx.post("/auth/login", json={"email": email, "password": password})
        r.raise_for_status()
        return r.json()["access_token"]

admin = login_as("admin")
citizen = login_as("citizen")

def get(token, district):
    with httpx.Client(base_url=BASE, timeout=120) as cx:
        r = cx.get(f"/assessment/{district}", headers={"Authorization": f"Bearer {token}"})
        r.raise_for_status()
        return r.json()

for d in ["Feni", "Dhaka", "Sylhet", "Bhola"]:
    a = get(admin, d)
    print(f"--- admin @ {d} ---")
    print(f"  is_operational={a['is_operational']}")
    print(f"  has recommendation={('recommendation' in a and a['recommendation'] is not None)}")
    print(f"  flood: prob={a['flood']['data']['flood_probability']} level={a['flood']['data']['flood_risk_level']}")
    print(f"  forecast: {a['forecast'].get('data')}")
    print(f"  satellite_extent status: {a['satellite_extent']['status']}")
    if a['satellite_extent']['status'] == 'ok':
        print(f"    event_label={a['satellite_extent']['data']['event_label']}")

# Citizen: recommendation must be absent
c = get(citizen, "Feni")
print(f"\n--- citizen @ Feni ---")
print(f"  is_operational={c['is_operational']}")
print(f"  has recommendation key: {'recommendation' in c}  (should be False for non-operational)")
print(f"  top-level keys: {list(c.keys())}")
