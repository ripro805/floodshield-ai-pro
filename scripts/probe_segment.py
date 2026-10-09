"""Roundtrip /satellite/ingest + /satellite/segment via httpx; print
the real input/output stats so we can verify the U-Net is not getting
an all-zeros chip (when GEE is up) and is not silently returning 0.0
for any other reason (NaN-guard fallback)."""
import json
import sys
import time
import httpx
import os
os.environ.setdefault("PYTHONPATH", ".")

# 1) log in
BASE = "http://127.0.0.1:8000"
email = f"seg-{int(time.time())}@example.com"
password = "Probe123!@#"
with httpx.Client(base_url=BASE, timeout=30) as cx:
    r = cx.post("/auth/signup", json={"email": email, "password": password, "full_name": "Seg", "role": "admin"})
    r.raise_for_status()
    r = cx.post("/auth/login", json={"email": email, "password": password})
    r.raise_for_status()
    tok = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {tok}"}

    # 2) ingest
    r = cx.get("/satellite/ingest", params={"district": "Feni"}, headers=headers, timeout=60)
    r.raise_for_status()
    ingest = r.json()
    chip = ingest["pixel_values"]
    print(f"ingest district={ingest['district']} shape={ingest['shape']} source={ingest['source']}")
    # 3) inspect
    flat = [v for row in chip for px in row for v in px]
    mn, mx = min(flat), max(flat)
    nz = sum(1 for v in flat if v != 0)
    print(f"VV min={mn} max={mx} nonzero={nz}/{len(flat)}")

    # 4) segment
    r = cx.post("/satellite/segment", json=chip, headers=headers, timeout=240)
    r.raise_for_status()
    seg = r.json()
    print(f"segment result={json.dumps(seg)}")
