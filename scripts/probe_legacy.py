"""Confirm legacy spellings resolve to the same row."""
import time, httpx
BASE = "http://127.0.0.1:8000"
email = f"legacy-{int(time.time())}@example.com"
with httpx.Client(base_url=BASE, timeout=30) as cx:
    cx.post("/auth/signup", json={"email": email, "password": "Probe123!@#", "full_name": "L", "role": "admin"}).raise_for_status()
    r = cx.post("/auth/login", json={"email": email, "password": "Probe123!@#"})
    r.raise_for_status()
    tok = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {tok}"}
    for d in ["Barisal", "Bogra", "Comilla", "Barishal", "Bogura", "Cumilla", "Cox's Bazar", "Cox's Bazar".replace("'","\\'")]:
        r = cx.get(f"/assessment/{d}", headers=headers, timeout=60)
        if r.status_code != 200:
            print(f"  {d}: HTTP {r.status_code}")
            continue
        sat = r.json()["satellite_extent"]
        ev = (sat.get("data") or {}).get("event_label") if sat["status"] == "ok" else None
        print(f"  {d:<15} status={sat['status']:<11}  event={ev!r}")
