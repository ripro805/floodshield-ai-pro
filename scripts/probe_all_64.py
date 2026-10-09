"""Sweep all 64 districts to confirm every one returns satellite ok."""
import json, time, httpx, sys
sys.path.insert(0, ".")
from app.database import SessionLocal
from app.reference_models import Location
s = SessionLocal()
db = sorted({r.district for r in s.query(Location).filter(Location.upazila.is_(None)).all()})
print(f"DB districts: {len(db)}")

# Build modern-name alias map (the same one the backend uses)
ALIAS = {"barisal": "Barishal", "bogra": "Bogura", "comilla": "Cumilla", "chittagong": "Chattogram", "jessore": "Jashore"}
def canon(name):
    return ALIAS.get(name.casefold(), name)
districts_modern = [canon(d) for d in db]
print(f"Modern spelling count: {len(set(districts_modern))}, unique: {len(set(districts_modern))}")

# Auth
BASE = "http://127.0.0.1:8000"
email = f"sweep-{int(time.time())}@example.com"
with httpx.Client(base_url=BASE, timeout=30) as cx:
    cx.post("/auth/signup", json={"email": email, "password": "Probe123!@#", "full_name": "Sweep", "role": "admin"}).raise_for_status()
    r = cx.post("/auth/login", json={"email": email, "password": "Probe123!@#"})
    r.raise_for_status()
    tok = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {tok}"}
    ok = 0
    placeholder = 0
    unavailable = []
    for d in districts_modern:
        r = cx.get(f"/assessment/{d}", headers=headers, timeout=60)
        if r.status_code != 200:
            print(f"  {d}: HTTP {r.status_code}")
            continue
        s2 = r.json()["satellite_extent"]
        if s2["status"] == "ok":
            ev = s2["data"]["event_label"]
            if "Placeholder" in ev:
                placeholder += 1
            else:
                ok += 1
        else:
            unavailable.append(d)
    print(f"  real sentinel-1: {ok}, placeholder: {placeholder}, unavailable: {len(unavailable)}")
    if unavailable:
        print(f"  unavailable: {unavailable}")
