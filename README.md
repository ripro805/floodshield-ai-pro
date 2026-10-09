# floodshield-ai-pro
AI-powered flood and disease outbreak early-warning platform for Bangladesh, combining ML prediction, risk scoring, forecasting, and actionable recommendations. It supports real-time weather data, disaster monitoring, resource planning, and scalable health intelligence.

## Reference Data Lives in the Database

All runtime reference data (districts, upazilas, latest per-district environment, hospitals, medical knowledge, community reports, satellite exports) is seeded into the connected Postgres database on every backend cold start. The xlsx/csv/geojson files in `data/` are the **source of truth** that the seeder reads — once the DB is populated, every endpoint reads from Postgres, not the filesystem.

This means:

- Local dev, Docker, Railway, and Render all behave identically — same dataset, no "did you remember to copy data/ to the container?" bugs.
- Reads come from the same connection pool as user data, so the dashboard is fast and consistent.
- Adding a new district, hospital, or satellite export only requires one row insert.

Tables and row counts (auto-seeded from `data/`):

- `locations` → 363 (district + upazila pairs from climate_dataset_fixed.xlsx)
- `district_env` → 64 (latest observed env per district)
- `hospitals` → 500 (hospital_resources_csv.xls)
- `district_hospital_aggregates` → 64 (derived from `hospitals`)
- `knowledge_articles` → 6 (medical_knowledge_base_fixed.xlsx)
- `community_reports` → 10 000 (community_reports_dataset.csv.xls)
- `satellite_extents` → 1 (Feni, from data/geo_exports/, expandable)

See [`backend/DEPLOY_REFERENCE_DATA.md`](backend/DEPLOY_REFERENCE_DATA.md) for the full reference-data architecture, re-seed instructions, and Dockerfile hints.

## Deployment Configuration & Secrets

When deploying the backend (e.g., to Railway or Render), **do not** commit your `.env` file or `ee_service_account.json` to version control.

1. Configure all standard environment variables (e.g., `DATABASE_URL`, `WEATHER_API_KEY`) via the platform's Environment Variables UI.
2. For the **Google Earth Engine Service Account**, the absolute easiest way is to copy the *entire* contents of your `ee_service_account.json` file and paste it into a new environment variable named `GEE_SERVICE_ACCOUNT_JSON` in your deployment platform's dashboard. The backend is configured to automatically read and parse this JSON string, so you don't need to upload any files or write any startup scripts!
