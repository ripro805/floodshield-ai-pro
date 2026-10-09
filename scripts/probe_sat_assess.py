"""Verify what the assessment endpoint reports for the satellite
section, district by district.  The user reported only Feni shows
data; the other 3 registered districts (Chattogram, Cumilla, Sylhet)
should also report ok."""
import json, time, httpx
BASE = "http://127.0.0.1:8000"
email = f"sat-check-{int(time.time())}@example.com"
with httpx.Client(base_url=BASE, timeout=30) as cx:
    cx.post("/auth/signup", json={"email": email, "password": "Probe123!@#", "full_name": "S", "role": "admin"}).raise_for_status()
    r = cx.post("/auth/login", json={"email": email, "password": "Probe123!@#"})
    r.raise_for_status()
    tok = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {tok}"}
    for d in ["Feni", "Chattogram", "Cumilla", "Sylhet", "Dhaka", "Bhola"]:
        r = cx.get(f"/assessment/{d}", headers=headers, timeout=60)
        r.raise_for_status()
        body = r.json()
        s = body["satellite_extent"]
        ev = (s.get("data") or {}).get("event_label") if s["status"] == "ok" else None
        print(f"  {d:<12} satellite status={s['status']:<11} event={ev!r}")
