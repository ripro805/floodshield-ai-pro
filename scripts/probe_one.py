"""Print the satellite section for one district (Dhaka) to confirm
placeholder is visible in the response."""
import json, time, httpx
BASE = "http://127.0.0.1:8000"
email = f"one-{int(time.time())}@example.com"
with httpx.Client(base_url=BASE, timeout=30) as cx:
    cx.post("/auth/signup", json={"email": email, "password": "Probe123!@#", "full_name": "One", "role": "admin"}).raise_for_status()
    r = cx.post("/auth/login", json={"email": email, "password": "Probe123!@#"})
    r.raise_for_status()
    tok = r.json()["access_token"]
    r = cx.get("/assessment/Dhaka", headers={"Authorization": f"Bearer {tok}"}, timeout=60)
    r.raise_for_status()
    body = r.json()
    print(json.dumps(body["satellite_extent"], indent=2))
