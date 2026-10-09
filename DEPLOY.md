# Deploy Guide — FloodShield AI

End-to-end instructions for running locally, in Docker, or on Railway/Render.

## TL;DR

```bash
# 1. Backend env (Neon or local Postgres)
cp backend/.env.example backend/.env
# then edit backend/.env and set DATABASE_URL, JWT_SECRET_KEY, etc.

# 2. Local dev (no Docker)
python -m uvicorn app.main:app --reload        # from backend/

# 3. Docker (recommended for parity with prod)
docker compose up --build
# → backend on  http://localhost:8000
# → frontend on http://localhost:3000
```

---

## 1. Database — Neon Postgres (production)

The seeders auto-populate `locations`, `district_env`, `hospitals`,
`district_hospital_aggregates`, `knowledge_articles`, `community_reports`,
and `satellite_extents` on every cold start.

- Existing tables are NOT overwritten (each seeder checks `count() == 0`
  before writing).
- The first time a brand-new deploy starts against an empty schema, you'll
  see log lines like:

  ```
  seed_locations: added 363 rows
  seed_district_env: added 64 rows
  seed_hospitals: added 500 rows
  seed_district_hospital_aggregates: rebuilt 64 rows
  seed_knowledge: added 6 rows
  seed_community_reports: added 10000 rows
  seed_satellite_extents: added 4 rows
  ```

- See [`backend/DEPLOY_REFERENCE_DATA.md`](backend/DEPLOY_REFERENCE_DATA.md)
  for the schema, re-seed SQL, and Dockerfile hints.

## 2. Local Postgres (optional, fully-offline)

If you want to develop without touching Neon, uncomment the `postgres`
service in `docker-compose.yml` and set:

```
DATABASE_URL=postgresql://floodshield:floodshield@postgres:5432/floodshield
```

Then `docker compose up --build` — the seeder will populate everything on
first start.

## 3. Frontend

The frontend reads `NEXT_PUBLIC_API_URL`.  Copy `.env.example` to
`.env.local` and set:

```
NEXT_PUBLIC_API_URL=http://localhost:8000     # local / docker
# NEXT_PUBLIC_API_URL=https://your-app.onrender.com   # production
```

Then either `npm run dev` (local) or rely on the `frontend` compose
service (Docker).

## 4. Docker Compose

```bash
docker compose up --build
```

Two services come up:

| Service    | URL                      | Notes                                       |
|------------|--------------------------|---------------------------------------------|
| `backend`  | http://localhost:8000    | FastAPI + Swagger UI at `/docs`             |
| `frontend` | http://localhost:3000    | Next.js dev server                          |

The `backend` healthcheck waits for `GET /` to be 200 before letting the
frontend start, so you won't see CORS errors or empty data on first load.

### Stop / restart

```bash
docker compose down            # stop + remove containers, keep volumes
docker compose down -v         # stop + remove containers + volumes (wipe DB!)
docker compose restart backend # restart only the backend (after a code change)
```

## 5. Production hosts (Railway / Render / Fly.io)

The general recipe is the same on every PaaS:

1. **Create the Postgres database** (or point at the existing Neon instance).
2. **Set environment variables** in the host's UI:
   - `DATABASE_URL` (the only required one)
   - `JWT_SECRET_KEY` (`openssl rand -hex 32`)
   - `WEATHER_API_KEY`, `LLM_API_KEY`, `HF_TOKEN` (optional but enable features)
   - `GEE_SERVICE_ACCOUNT_JSON` (single-line JSON; enables satellite ingestion)
3. **Build command:** `docker build -f backend/Dockerfile .` (or equivalent)
4. **Start command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. **First boot** will print seed log lines — confirm they ran with the
   expected row counts before declaring the deploy complete.

That's it. There's no migration step — `Base.metadata.create_all()` plus
the idempotent seeders handle the schema and the seed data together.

## 6. Adding more satellite exports

Either:
- Drop a new `flood_extent_<district>.geojson` into `data/geo_exports/`,
  redeploy, and the seeder will pick it up on the next cold start.
- Or insert a row directly into `satellite_extents` via the database console.

The frontend's `/api/satellite/flood-extent` endpoint surfaces whatever
districts the DB has — there's no code change needed.

## 7. Verifying a deploy

After the backend reports `Application startup complete`:

```bash
curl -s http://localhost:8000/ | jq .
# → {"status":"ok","service":"FloodShield AI API","models_loaded":true}

curl -s http://localhost:8000/api/locations/search?q=Feni | jq .
# → 5 results (district + 4 upazilas)

curl -s http://localhost:8000/satellite/flood-extent | jq .
# → {"available_districts":["Chattogram","Cumilla","Feni","Sylhet"]}
```

If any of these fail, check the backend logs first — the seeders log every
step and any path-resolution issue will be obvious.