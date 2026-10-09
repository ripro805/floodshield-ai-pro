# FloodShield AI — Backend API

FastAPI backend wrapping all six FloodShield AI models behind a REST API for
the Next.js dashboard, with JWT authentication and role-based access control.

For the current implementation and verified completion boundary, see the repository-root `PROJECT_COMPLETION_STATUS.md`.

## Quick start (local)

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # then fill in your real DATABASE_URL and JWT_SECRET_KEY
uvicorn app.main:app --reload
```

Open **http://127.0.0.1:8000/docs** — every endpoint below can be tried
directly from the browser (Swagger UI). Click **Authorize** (top right) after
logging in via `/auth/login` to try protected endpoints with your token.

## Project structure

```
backend/
├── app/
│   ├── main.py            FastAPI app, CORS, router registration, DB table creation
│   ├── config.py          paths, composite risk weights, DB/JWT settings (from .env)
│   ├── database.py        SQLAlchemy engine/session (points at Neon Postgres)
│   ├── models_loader.py   loads every .pkl/.keras ONCE at startup
│   ├── schemas.py         request/response models (auto-validates input)
│   ├── auth_models.py     the `users` SQLAlchemy table (email, password, role, district)
│   ├── auth_schemas.py    signup/login/token Pydantic models
│   ├── auth_utils.py      password hashing (bcrypt) + JWT create/decode
│   ├── auth_deps.py       get_current_user + require_roles() dependencies
│   └── routers/
│       ├── auth.py        /auth/signup, /auth/login, /auth/me
│       ├── flood.py       /predict/flood        (Model 1)
│       ├── disease.py     /predict/disease       (Model 2)
│       ├── forecast.py    /predict/forecast      (Model 3)
│       ├── risk.py        /predict/risk          (Model 5)
│       ├── recommend.py   /recommend, /predict/full-assessment (Model 6)
│       └── satellite.py   /satellite/flood-extent, /satellite/segment (Model 4)
├── models/                 all trained model artifacts (.pkl, .keras)
├── data/geo_exports/       GeoJSON files exported from Model 4A (Colab)
├── tests/                  19 automated tests (all passing)
├── .env                    real credentials -- gitignored, never commit this
├── .env.example             template for teammates / git
├── requirements.txt
├── Dockerfile
├── .dockerignore
└── README.md                (this file)
```

## Endpoints

| Method | Path | Auth required | Description |
|---|---|---|---|
| GET  | `/` | — | Health check |
| POST | `/auth/signup` | — | Create an account (choose a role) |
| POST | `/auth/login` | — | Get a JWT access token |
| GET  | `/auth/me` | any logged-in user | Who am I / what's my role |
| POST | `/predict/flood` | any logged-in user | Model 1 — binary flood probability |
| POST | `/predict/disease` | any logged-in user | Model 2 — outbreak risk |
| POST | `/predict/forecast` | any logged-in user | Model 3 — 7/14-day case forecast |
| POST | `/predict/risk` | any logged-in user | Model 5 — composite risk score |
| POST | `/recommend` | health_worker / hospital / ngo / government / admin | Model 6 — resource recommendation |
| POST | `/predict/full-assessment` | health_worker / hospital / ngo / government / admin | Model 5 + 6 combined |
| GET  | `/satellite/flood-extent` | any logged-in user | List districts with a satellite export |
| GET  | `/satellite/flood-extent/{district}` | any logged-in user | GeoJSON flood extent |
| POST | `/satellite/segment` | any logged-in user | Model 4B — run U-Net on a SAR chip |

## Role-based access — how it works

Six roles, matching the original product spec: `citizen`, `health_worker`,
`hospital`, `ngo`, `government`, `admin`. One `users` table (role is just a
column), enforced two ways:

- **`require_any_authenticated_user`** — any logged-in role can call it.
  Used on all `/predict/*` and `/satellite/*` endpoints: flood/disease/risk
  early-warning info is useful to everyone, including citizens.
- **`require_roles(*roles)`** — only the listed roles can call it. Used on
  `/recommend` and `/predict/full-assessment`: "deploy an emergency team" /
  "restock ORS" is operational data for hospitals/NGOs/government/health
  workers/admins, not something a citizen account needs to see.

To add a new protected endpoint, add
`dependencies=[Depends(require_roles(UserRole.hospital, UserRole.admin))]`
to that route (see `recommend.py` for a working example).

## Weather API integration (latest update, reviewed)

`/predict/flood` and `/predict/disease` now accept an optional `location`
field. If `rainfall_mm`/`temperature_c`/`humidity_percent` aren't provided
directly, the backend fetches them live from OpenWeatherMap for that
location (`app/services/weather_service.py`), with a 30-minute in-memory
cache and a safe fallback if the API is unreachable.

**Two bugs found and fixed during review** (see `git diff` if you're tracking
this in version control):
1. `models_loader.py` had been changed to force the Keras "torch" backend
   (`os.environ["KERAS_BACKEND"] = "torch"` + `from keras.models import
   load_model`) — this crashed the server on startup with `ModuleNotFoundError:
   No module named 'torch'`, since torch isn't installed. Reverted to
   `from tensorflow.keras.models import load_model`, matching how the models
   were actually trained and saved in Colab.
2. `disease.py`'s `_build_feature_row()` was correctly made `async` (to
   `await` the weather API call), but `risk.py` — which reuses that same
   function for Model 5 — called it without `await`, silently passing a
   coroutine object into `predict_proba()` instead of a DataFrame. This broke
   `/predict/risk` and `/predict/full-assessment` entirely. Fixed by making
   `compute_risk_score()` and its callers `async` all the way through.

**On the "does this work for all 64 districts?" question:** I could not
test live OpenWeatherMap calls from this environment (its network only
reaches an allow-list of domains, not `api.openweathermap.org`) — so this
hasn't been verified end-to-end against the real API. What I could check and
fix: the original code queried `q=location` with **no country code**, which
risks matching a same-named place elsewhere in the world. Added `,BD` to the
query (`q=f"{location},BD"`) to disambiguate. Also added a `"data_source":
"live"` vs `"fallback"` field to the response so the frontend can show
clearly when a prediction is running on a real vs. estimated weather reading
— important for a product where a silent fallback could produce a
misleadingly confident flood/disease alert.

**Recommended next step (not yet done):** some Bangladeshi district names
have alternate official spellings that OpenWeatherMap's geocoder may or may
not recognize (Bogra/Bogura, Comilla/Cumilla, Chittagong/Chattogram,
Jessore/Jashore). The most reliable fix would be querying by **latitude/
longitude** instead of name — Model 4A/4B's GAUL district boundary loop
already fetches exact centroids for all 64 districts, which could be
reused here as a lookup table instead of free-text city name matching.
Happy to build this if you want it before the pitch.

## What I changed to add this (summary)

1. **New files**: `database.py`, `auth_models.py`, `auth_schemas.py`,
   `auth_utils.py`, `auth_deps.py`, `routers/auth.py`.
2. **`config.py`**: added `DATABASE_URL` / `JWT_SECRET_KEY` (read from `.env`
   via `python-dotenv`), plus a startup check that fails loudly if either is
   missing rather than silently misbehaving.
3. **`main.py`**: registered the new `/auth` router, and added
   `Base.metadata.create_all(bind=engine)` to the startup `lifespan` so the
   `users` table is created automatically on first run.
4. **Every existing router** (`flood.py`, `disease.py`, `forecast.py`,
   `risk.py`, `satellite.py`): added
   `dependencies=[Depends(require_any_authenticated_user)]` at the router
   level, so every route in that file now requires a valid token.
5. **`recommend.py`**: used the stricter `require_roles(...)` instead, since
   its output (deploy team, restock supplies) is operational, not general
   public info.
6. **`requirements.txt`**: added `sqlalchemy`, `psycopg2-binary`,
   `python-jose[cryptography]`, `passlib[bcrypt]`, `bcrypt==4.0.1` (pinned —
   see note below), `python-dotenv`.
7. **`.env` / `.env.example` / `.gitignore` / `.dockerignore`**: real
   credentials live only in `.env`, which is excluded from both git and the
   Docker image.
8. **`tests/test_endpoints.py`**: added `auth_headers` / `hospital_headers`
   fixtures, added 7 new auth-specific tests, and updated every pre-existing
   test to send a token (since those endpoints are no longer open).

## Design notes worth knowing before you extend this

- **`bcrypt` is pinned to `4.0.1`.** Newer `bcrypt` releases (5.x) changed an
  internal `__about__` attribute that `passlib` 1.7.4 (last released 2020)
  doesn't know how to read, causing every password hash to fail with a
  confusing "password cannot be longer than 72 bytes" error even for short
  passwords. Pinning `bcrypt==4.0.1` avoids this entirely. If you upgrade
  `passlib` later, re-test before removing this pin.
- **I could not test the real Neon connection from this environment** —
  the network here only reaches a fixed allow-list of domains (pypi, github,
  npm, etc.), not arbitrary Postgres hosts. Every test above (19/19 passing)
  ran against a local SQLite database with the *exact same* SQLAlchemy code
  path, to verify the logic is correct. **Please run `pytest tests/ -v`
  yourself once, pointed at your real `.env`, before deploying** — if
  anything Neon-specific comes up (e.g. connection pooling limits), paste
  the error and I'll fix it.
- **`flood_level_label_encoder.pkl` is unused on purpose.** It's a leftover
  from an earlier 4-class version of Model 1. The model actually loaded now
  is binary (`classes_ == [0, 1]`), so `flood.py` maps 0/1 → "No Flood"/"Flood"
  directly instead of using that encoder.
- **`/predict/forecast` requires the caller to supply the last 8 weeks of
  data.** The per-district scalers were fit in the training notebook against
  a weekly history dataframe that isn't stored anywhere this API can reach.
  Once `predictions_history` (see "Not yet in this backend" below) is
  actually being written to, that table should feed this endpoint
  automatically instead of requiring the frontend to pass 8 weeks manually.
- **`/satellite/segment` expects an already-preprocessed 256×256×2 array**,
  not a raw satellite file — see `satellite.py` docstring for why.
- **Models 5 and 6 are rule-based, not separately trained classifiers** —
  explainable logic is easier to defend to government/hospital stakeholders
  than another black-box model.
- **`Base.metadata.create_all()` is fine for this project's scale** but isn't
  a migration system — if you change `auth_models.py` after the table
  already exists in Neon, you'll need to either drop/recreate it manually or
  introduce Alembic.

## Deployment (Docker)

```bash
docker build -f backend/Dockerfile -t floodshield-backend .
docker run -p 8000:8000 \
  -e DATABASE_URL="your-neon-url" \
  -e JWT_SECRET_KEY="your-secret" \
  floodshield-backend
```

On Railway/Render, set `DATABASE_URL` and `JWT_SECRET_KEY` in the platform's
environment variables UI rather than baking them into the image.

## What's NOT in this backend yet (see execution plan for when)

- Frontend integration (Next.js dashboard calling these endpoints)
- `predictions_history` table (logging real predictions over time, which
  `/predict/forecast` could eventually read from automatically)
- Password reset / email verification flow
- Rate limiting, request logging
- CORS is wide open (`allow_origins=["*"]`) — tighten before production

