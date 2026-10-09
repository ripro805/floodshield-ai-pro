# Deploy Notes — Reference Data Now Lives in the DB

All runtime reference data is now stored in the connected Postgres database.
The backend auto-seeds on every cold start; the xlsx/csv files in `data/` only
serve as the **source of truth** that the seeder reads.

## Tables auto-created on startup

| Table                          | Source file (read on seed)                              | Rows |
| ------------------------------ | ------------------------------------------------------- | ---- |
| `locations`                    | `data/climate_dataset_fixed.xlsx`                       | 363  |
| `district_env`                 | `data/climate_dataset_fixed.xlsx` (latest per district) | 64   |
| `hospitals`                    | `data/hospital_resources_csv.xls`                       | 500  |
| `district_hospital_aggregates` | derived from `hospitals`                                | 64   |
| `knowledge_articles`           | `data/medical_knowledge_base_fixed.xlsx`                | 6    |
| `community_reports`            | `data/community_reports_dataset.csv.xls`                | 10000 |
| `satellite_extents`            | `data/geo_exports/*.geojson`                            | n    |

## Behaviour on a fresh deploy

1. `Base.metadata.create_all()` runs first, creating every table the routers expect.
2. `seed_reference_data_if_empty()` runs next. Each seeder:
   - Skips itself if the destination table already has rows (so production
     data is never overwritten).
   - Logs the rows added on a cold start.
3. `seed_weekly_history_if_empty()` runs after, ensuring each district has
   8 weeks of synthetic-but-plausible observations.

## What lives in the DB now (and what doesn't)

**Reads from Postgres:**
- District + upazila search (`/api/locations/search`)
- Latest per-district environmental snapshot (`/api/weather`)
- District-level disease hotspots (`/predict/hotspots`)
- Hospital stock + recommendations (`/recommend`, `/predict/risk/all-districts`,
  `/predict/full-assessment`)
- Medical knowledge corpus for the chatbot (`/chatbot/message`)
- Community reports dataset (available for analytics and incident
  classification tuning)
- Satellite registry + GeoJSON payloads (`/satellite/flood-extent`)

**Still on disk / HuggingFace:**
- Trained model artifacts (`.pkl`, `.keras`, `flood_segmentation_unet.keras`,
  etc.) — loaded at startup by `models_loader.py`. These are large binaries
  that don't belong in a relational DB.

## How to add more satellite exports

Either:
1. Drop a new `flood_extent_<district>.geojson` into `data/geo_exports/`
   and redeploy — the seeder ingests it on next cold start.
2. Insert directly into `satellite_extents` via the database console.

## How to refresh the reference data

The seeders only insert when a table is empty. To force a re-seed:

```sql
TRUNCATE TABLE locations          RESTART IDENTITY;
TRUNCATE TABLE district_env       RESTART IDENTITY;
TRUNCATE TABLE hospitals          RESTART IDENTITY;
TRUNCATE TABLE district_hospital_aggregates RESTART IDENTITY;
TRUNCATE TABLE knowledge_articles RESTART IDENTITY;
TRUNCATE TABLE community_reports  RESTART IDENTITY;
TRUNCATE TABLE satellite_extents  RESTART IDENTITY;
```

Then restart the backend. The seeders will repopulate on startup.

## Important: this is why deploys now Just Work

- Local dev, Docker, Railway, Render, etc. all see the same dataset — the
  DB is the single source of truth, not files in the container.
- Files like `data/hospital_resources_csv.xls` are read on startup by the
  seeder. If you change them, TRUNCATE the corresponding table and restart.
- The seeder is **idempotent**: running it twice never duplicates rows and
  never overwrites production data.

## How to verify the seed ran on startup

Check the backend log for lines like:

```
seed_locations: added 363 rows
seed_district_env: added 64 rows
seed_hospitals: added 500 rows
seed_district_hospital_aggregates: rebuilt 64 rows
seed_knowledge: added 6 rows
seed_community_reports: added 10000 rows
seed_satellite_extents: added 1 rows
```

If you don't see those lines, the seed files weren't found (most likely
the `data/` directory wasn't included in your Docker image — see the
Dockerfile notes below).

## Dockerfile notes

If you build a slim image, ensure the `data/` directory is copied alongside
the backend code. Add to your Dockerfile:

```dockerfile
COPY data/ /app/data/
COPY backend/ /app/
```

`/app/data/` is `backend/data/` inside the container. The seeder also
checks `../data/` relative to `DATA_DIR`, so mounting the repo's `data/`
folder at `/app/../data/` (e.g. `/data/`) also works.