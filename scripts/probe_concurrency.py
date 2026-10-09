"""Verify two concurrent assessment requests don't cross-contaminate.
This is a coarse server-side check: the real "no stale result under
the wrong district" guarantee is enforced by the React Query key
(primitives only), but it doesn't hurt to confirm the API itself
returns the right payload for the right district."""
import asyncio
import time
import httpx

BASE = "http://127.0.0.1:8000"

async def main():
    async with httpx.AsyncClient(base_url=BASE, timeout=120) as cx:
        # log in
        email = f"race-{int(time.time())}@example.com"
        r = await cx.post("/auth/signup", json={"email": email, "password": "Probe123!@#", "full_name": "Race", "role": "admin"})
        r.raise_for_status()
        r = await cx.post("/auth/login", json={"email": email, "password": "Probe123!@#"})
        r.raise_for_status()
        tok = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {tok}"}

        # Fire 3 district requests concurrently (simulating a fast-switch)
        districts = ["Feni", "Dhaka", "Sylhet"]
        t0 = time.time()
        results = await asyncio.gather(*(cx.get(f"/assessment/{d}", headers=headers) for d in districts))
        elapsed = time.time() - t0
        for d, r in zip(districts, results):
            body = r.json()
            ok = body["district"] == d
            flood = body["flood"]["data"]["flood_probability"]
            print(f"  request {d:<8} -> status={r.status_code} district={body['district']} (match={ok}) flood_probability={flood}")
        print(f"3 concurrent assessments in {elapsed:.2f}s")

asyncio.run(main())
