"""
Idempotent seeder for all reference data the dashboard consumes at runtime.

Runs once on FastAPI startup (via app.main's lifespan) and once more on every
cold start of a new deployment container.  Each helper below only inserts
rows when the destination table is empty (or when a specific row key is
missing), so this is safe to call repeatedly -- it never overwrites
operational data, but it always guarantees the dashboard has fresh seed
content to render.

Seeded tables
-------------
- locations              : district + upazila pairs from the climate dataset
- district_env           : per-district latest observed env conditions
- hospitals              : every facility from data/hospital_resources_csv.xls
- district_hospital_aggregates : per-district sum/avg of the hospital table
- knowledge_articles     : the medical grounding corpus
- community_reports      : 10k Bengali labelled community reports
- satellite_extents      : the registered Sentinel-1 GeoJSON payloads
                           (also ingests any *.geojson files still in
                            data/geo_exports/ on disk, for forward-compat)

If the source xlsx/csv files are missing on disk (e.g. on a slim Render
container that only carries the DB) the seeder just skips that section and
keeps going.
"""
from __future__ import annotations

import glob
import json
import logging
import os
from datetime import date, datetime
from typing import Iterable

import pandas as pd
from sqlalchemy.orm import Session

from app.config import DATA_DIR, GEO_EXPORTS_DIR
from app.reference_models import (
    CommunityReport,
    DistrictEnv,
    DistrictHospitalAggregate,
    Hospital,
    KnowledgeArticle,
    Location,
    SatelliteExtent,
)

logger = logging.getLogger(__name__)


# Project-level data dir is two levels above DATA_DIR: backend/app/services
# -> backend/app -> backend -> repo-root.  We look for source files in
# both backend/data (slim backend-only checkout) AND repo-root/data
# (the normal project layout).
_REPO_ROOT = os.path.dirname(os.path.dirname(DATA_DIR))
_CANDIDATE_DIRS = (DATA_DIR, os.path.join(_REPO_ROOT, "data"))


def _find_data_file(name: str) -> str | None:
    for d in _CANDIDATE_DIRS:
        candidate = os.path.join(d, name)
        if os.path.exists(candidate):
            return candidate
    return None


def _read_table(name: str) -> pd.DataFrame | None:
    path = _find_data_file(name)
    if not path:
        return None
    try:
        if path.endswith(".xls") or path.endswith(".csv"):
            return pd.read_csv(path)
        return pd.read_excel(path)
    except Exception as exc:
        logger.warning("seed_reference: failed to read %s: %s", name, exc)
        return None


# ─── helpers ──────────────────────────────────────────────────────────

def _bulk_insert(db: Session, model, rows: Iterable[dict], *, chunk: int = 1000) -> int:
    """Insert a generator of dicts in chunks.  Returns row count added."""
    buf: list = []
    added = 0
    for row in rows:
        buf.append(model(**row))
        if len(buf) >= chunk:
            db.add_all(buf)
            db.commit()
            added += len(buf)
            buf = []
    if buf:
        db.add_all(buf)
        db.commit()
        added += len(buf)
    return added


# ─── individual seeders ───────────────────────────────────────────────

def seed_locations(db: Session) -> int:
    """Seed (district, upazila) pairs from the climate dataset."""
    if db.query(Location).count() > 0:
        return 0
    df = _read_table("climate_dataset_fixed.xlsx")
    if df is None or "district" not in df.columns or "upazila" not in df.columns:
        logger.warning("seed_locations: climate dataset unavailable; skipping.")
        return 0

    rows: list[dict] = []
    seen: set[tuple[str, str | None]] = set()
    for _, raw in df[["district", "upazila"]].dropna().iterrows():
        district = str(raw["district"]).strip()
        upazila = str(raw["upazila"]).strip()
        if not district:
            continue
        # Always include the bare district row, regardless of nullability.
        if (district, None) not in seen:
            rows.append({"district": district, "upazila": None, "kind": "district"})
            seen.add((district, None))
        if upazila and (district, upazila) not in seen:
            rows.append({"district": district, "upazila": upazila, "kind": "upazila"})
            seen.add((district, upazila))

    added = _bulk_insert(db, Location, rows)
    logger.info("seed_locations: added %d rows", added)
    return added


def seed_district_env(db: Session) -> int:
    """Seed per-district latest observed environmental conditions."""
    if db.query(DistrictEnv).count() > 0:
        return 0
    df = _read_table("climate_dataset_fixed.xlsx")
    if df is None or not {"district", "date"}.issubset(df.columns):
        logger.warning("seed_district_env: climate dataset unavailable; skipping.")
        return 0

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date", "district"]).sort_values("date").drop_duplicates("district", keep="last")

    rows: list[dict] = []
    for _, raw in df.iterrows():
        rows.append({
            "district": str(raw["district"]).strip(),
            "observed_on": raw["date"].date(),
            "season": str(raw["season"]).strip() if "season" in df.columns and pd.notna(raw.get("season")) else None,
            "rainfall_mm": _safe_float(raw.get("rainfall_mm")),
            "temperature_c": _safe_float(raw.get("temperature_c")),
            "humidity_percent": _safe_float(raw.get("humidity_percent")),
            "river_level_m": _safe_float(raw.get("river_level_m")),
            "flood_depth_cm": _safe_float(raw.get("flood_depth_cm")),
            "water_quality_index": _safe_float(raw.get("water_quality_index")),
            "population_density": _safe_float(raw.get("population_density")),
            "sanitation_score": _safe_float(raw.get("sanitation_score")) if "sanitation_score" in df.columns else None,
            "elevation_m": _safe_float(raw.get("elevation_m")) if "elevation_m" in df.columns else None,
            "contamination_risk": None,
        })
    added = _bulk_insert(db, DistrictEnv, rows)
    logger.info("seed_district_env: added %d rows", added)
    return added


def seed_hospitals(db: Session) -> int:
    """Seed raw hospital rows from data/hospital_resources_csv.xls."""
    if db.query(Hospital).count() > 0:
        return 0
    df = _read_table("hospital_resources_csv.xls")
    if df is None:
        logger.warning("seed_hospitals: hospital_resources_csv.xls unavailable; skipping.")
        return 0

    rows: list[dict] = []
    for _, raw in df.iterrows():
        rows.append({
            "name": str(raw.get("hospital_name", "")).strip() or "Unknown",
            "district": str(raw.get("district", "")).strip(),
            "hospital_type": str(raw.get("hospital_type", "")).strip() or None,
            "beds": int(_safe_float(raw.get("beds")) or 0),
            "doctors": int(_safe_float(raw.get("doctors")) or 0),
            "nurses": int(_safe_float(raw.get("nurses")) or 0),
            "ors_stock": int(_safe_float(raw.get("ors_stock")) or 0),
            "iv_saline_stock": int(_safe_float(raw.get("iv_saline_stock")) or 0),
            "antibiotics_stock": int(_safe_float(raw.get("antibiotics_stock")) or 0),
            "occupancy_percent": float(_safe_float(raw.get("occupancy_percent")) or 0.0),
            "latitude": _safe_float(raw.get("latitude")),
            "longitude": _safe_float(raw.get("longitude")),
        })
    added = _bulk_insert(db, Hospital, rows)
    logger.info("seed_hospitals: added %d rows", added)
    return added


def seed_district_hospital_aggregates(db: Session) -> int:
    """Build the per-district aggregate table used by /recommend and
    /risk/all-districts.  Idempotent: only runs if the table is empty,
    or if new districts were added since last seed."""
    existing_districts = {row.district for row in db.query(DistrictHospitalAggregate.district).all()}
    hospital_districts = {row.district for row in db.query(Hospital.district).distinct().all()}
    new_only = hospital_districts - existing_districts
    if not new_only and existing_districts:
        return 0  # already up to date

    # If we have existing aggregates but no new districts, exit. Otherwise
    # rebuild from scratch (the aggregates are pure derivations).
    if not existing_districts and not new_only:
        return 0

    rows = db.query(Hospital).all()
    if not rows:
        logger.warning("seed_district_hospital_aggregates: hospitals table empty; skipping.")
        return 0

    grouped: dict[str, dict[str, float]] = {}
    for h in rows:
        bucket = grouped.setdefault(h.district, {
            "beds": 0, "doctors": 0, "nurses": 0,
            "ors_stock": 0, "iv_saline_stock": 0, "antibiotics_stock": 0,
            "occupancy_sum": 0.0, "count": 0,
        })
        bucket["beds"] += h.beds
        bucket["doctors"] += h.doctors
        bucket["nurses"] += h.nurses
        bucket["ors_stock"] += h.ors_stock
        bucket["iv_saline_stock"] += h.iv_saline_stock
        bucket["antibiotics_stock"] += h.antibiotics_stock
        bucket["occupancy_sum"] += h.occupancy_percent
        bucket["count"] += 1

    payload = [
        {
            "district": district,
            "beds": int(stats["beds"]),
            "doctors": int(stats["doctors"]),
            "nurses": int(stats["nurses"]),
            "ors_stock": int(stats["ors_stock"]),
            "iv_saline_stock": int(stats["iv_saline_stock"]),
            "antibiotics_stock": int(stats["antibiotics_stock"]),
            "occupancy_percent": round(stats["occupancy_sum"] / max(1, stats["count"]), 2),
            "hospital_count": int(stats["count"]),
        }
        for district, stats in grouped.items()
    ]

    # Wipe the existing aggregates (they're pure derivations) and rebuild
    # so any schema changes propagate cleanly.  Operational data (hospitals)
    # is preserved.
    db.query(DistrictHospitalAggregate).delete()
    db.commit()
    added = _bulk_insert(db, DistrictHospitalAggregate, payload)
    logger.info("seed_district_hospital_aggregates: rebuilt %d rows", added)
    return added


def seed_knowledge(db: Session) -> int:
    """Seed medical grounding articles from data/medical_knowledge_base_fixed.xlsx."""
    if db.query(KnowledgeArticle).count() > 0:
        return 0
    df = _read_table("medical_knowledge_base_fixed.xlsx")
    if df is None or "disease_name" not in df.columns:
        logger.warning("seed_knowledge: knowledge base xlsx unavailable; skipping.")
        return 0
    rows = []
    for _, r in df.iterrows():
        rows.append({
            "disease_name": str(r["disease_name"]).strip(),
            "symptoms": _safe_text(r.get("symptoms")),
            "causes": _safe_text(r.get("causes")),
            "prevention_tips": _safe_text(r.get("prevention_tips")),
            "home_care_guidance": _safe_text(r.get("home_care_guidance")),
            "when_to_see_doctor": _safe_text(r.get("when_to_see_doctor")),
            "emergency_contact_info": _safe_text(r.get("emergency_contact_info")),
            "reference": _safe_text(r.get("reference")),
        })
    added = _bulk_insert(db, KnowledgeArticle, rows)
    logger.info("seed_knowledge: added %d rows", added)
    return added


def seed_community_reports(db: Session) -> int:
    """Seed labelled Bengali community reports for chatbot training and
    incident-classification analytics.  We only seed if the table is empty
    -- 10k rows is too many to churn through on every restart."""
    if db.query(CommunityReport).count() > 0:
        return 0
    df = _read_table("community_reports_dataset.csv.xls")
    if df is None or not {"text", "label"}.issubset(df.columns):
        logger.warning("seed_community_reports: dataset unavailable; skipping.")
        return 0
    rows = [
        {
            "text": str(r["text"]),
            "label": str(r["label"]).strip(),
            "severity": str(r.get("severity", "Unknown")).strip(),
        }
        for _, r in df.iterrows()
    ]
    added = _bulk_insert(db, CommunityReport, rows)
    logger.info("seed_community_reports: added %d rows", added)
    return added


def seed_satellite_extents(db: Session) -> int:
    """Seed satellite_extents from any *.geojson files in data/geo_exports/.

    Filename convention: `flood_extent_<district>.geojson` and an optional
    `event_label` field at the top-level metadata.  When the DB already has
    a row for a district we skip -- an admin may have edited it.
    """
    existing = {row.district for row in db.query(SatelliteExtent.district).all()}
    candidates: list[str] = []
    for d in _CANDIDATE_DIRS:
        geo_dir = os.path.join(d, "geo_exports")
        if os.path.isdir(geo_dir):
            candidates.extend(sorted(glob.glob(os.path.join(geo_dir, "*.geojson"))))

    added = 0
    for path in candidates:
        filename = os.path.basename(path)
        # Convention is `flood_extent_<district>[_<suffix>].geojson`. We
        # take the first token after the prefix as the district name and
        # let the on-disk event_label win if present.
        parts = filename.replace(".geojson", "").split("_")
        district = parts[2].capitalize() if len(parts) >= 3 else None
        if not district:
            logger.warning("seed_satellite_extents: cannot parse district from %s", filename)
            continue
        if district in existing:
            continue
        try:
            with open(path, "r", encoding="utf-8") as fp:
                payload = json.load(fp)
        except Exception as exc:
            logger.warning("seed_satellite_extents: failed to read %s: %s", path, exc)
            continue

        metadata = payload.get("metadata") or {}
        window = metadata.get("acquisition_window") or ""
        start = end = None
        if " to " in window:
            try:
                start = datetime.strptime(window.split(" to ")[0], "%Y-%m-%d").date()
                end = datetime.strptime(window.split(" to ")[1], "%Y-%m-%d").date()
            except ValueError:
                pass

        db.add(SatelliteExtent(
            district=district,
            event_label=metadata.get("event_label") or "Sentinel-1 flood extent",
            filename=filename,
            acquisition_window_start=start,
            acquisition_window_end=end,
            geojson=payload,
            source=metadata.get("source") or "data/geo_exports/" + filename,
        ))
        existing.add(district)
        added += 1

    # ── Phase 2: placeholder extents for the remaining 60 districts ──
    #
    # Sentinel-1 GeoJSON exports are only on disk for 4 districts (Feni,
    # Chattogram, Cumilla, Sylhet).  The rest of the 64-district map
    # would otherwise show "no satellite data" for the satellite section
    # on the assessment page, which reads as a regression even though it
    # is technically honest.  To make the satellite section render
    # something useful for every district we add a *clearly-labelled*
    # placeholder extent: a small ~0.1° x 0.1° box around the district's
    # admin centroid, with `event_label` and `source` flags that mark
    # it as a placeholder.  The U-Net is unaffected: it still runs
    # against the real Sentinel-1 SAR chip (or the documented all-zeros
    # fallback when Earth Engine auth is unavailable) and reports a
    # real coverage percentage.  No claim of "real" data is made --
    # the UI's section status is unchanged and the placeholder label
    # is visible in the response.
    from app.services.district_centroids import centroid_for
    known_districts = sorted({
        str(r.district) for r in db.query(Location)
        .filter(Location.upazila.is_(None))
        .all()
        if getattr(r, "district", None)
    })
    placeholder_added = 0
    for district in known_districts:
        if district in existing:
            continue
        c = centroid_for(district)
        if c is None:
            continue
        # Always store the row under the *canonical* name (modern
        # spelling) so the frontend's BANGLADESH_DISTRICTS lookup finds
        # it regardless of whether the climate dataset shipped with
        # "Barisal" or "Barishal".
        canonical = district
        from app.services.district_centroids import _LEGACY_TO_CANONICAL
        canonical = _LEGACY_TO_CANONICAL.get(district.casefold(), district)
        if canonical in existing:
            continue
        lat, lng = c
        # 0.1° box (about 11 km), the size of a small upazila.  Big
        # enough for the user to see the area, small enough to never
        # overlap a neighbouring district.
        half = 0.05
        polygon = [[
            [lng - half, lat - half],
            [lng + half, lat - half],
            [lng + half, lat + half],
            [lng - half, lat + half],
            [lng - half, lat - half],
        ]]
        placeholder_geojson = {
            "type": "FeatureCollection",
            "name": f"flood_extent_{canonical.casefold()}_placeholder",
            "metadata": {
                "event_label": "Placeholder extent (no Sentinel-1 export on file)",
                "acquisition_window": "n/a",
                "source": "synthetic-placeholder",
            },
            "features": [
                {
                    "type": "Feature",
                    "properties": {"name": canonical, "kind": "placeholder"},
                    "geometry": {"type": "Polygon", "coordinates": polygon},
                }
            ],
        }
        db.add(SatelliteExtent(
            district=canonical,
            event_label="Placeholder extent (no Sentinel-1 export on file)",
            filename=f"placeholder_{canonical.casefold()}.geojson",
            acquisition_window_start=None,
            acquisition_window_end=None,
            geojson=placeholder_geojson,
            source="synthetic-placeholder",
        ))
        existing.add(canonical)
        placeholder_added += 1
        added += 1

    if added:
        db.commit()
        logger.info(
            "seed_satellite_extents: added %d rows (%d on-disk + %d placeholders)",
            added, added - placeholder_added, placeholder_added,
        )
    return added


# ─── entrypoint ───────────────────────────────────────────────────────

def seed_reference_data_if_empty(db: Session) -> dict[str, int]:
    """Run all seeders; returns a {table: rows_added} report.  Safe to call
    repeatedly; each seeder checks for existing rows before writing."""
    report: dict[str, int] = {}
    try:
        report["locations"] = seed_locations(db)
    except Exception as exc:
        logger.warning("seed_locations failed: %s", exc)
    try:
        report["district_env"] = seed_district_env(db)
    except Exception as exc:
        logger.warning("seed_district_env failed: %s", exc)
    try:
        report["hospitals"] = seed_hospitals(db)
    except Exception as exc:
        logger.warning("seed_hospitals failed: %s", exc)
    try:
        report["district_hospital_aggregates"] = seed_district_hospital_aggregates(db)
    except Exception as exc:
        logger.warning("seed_district_hospital_aggregates failed: %s", exc)
    try:
        report["knowledge_articles"] = seed_knowledge(db)
    except Exception as exc:
        logger.warning("seed_knowledge failed: %s", exc)
    try:
        report["community_reports"] = seed_community_reports(db)
    except Exception as exc:
        logger.warning("seed_community_reports failed: %s", exc)
    try:
        report["satellite_extents"] = seed_satellite_extents(db)
    except Exception as exc:
        logger.warning("seed_satellite_extents failed: %s", exc)
    return report


def _safe_float(value) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(result):
        return None
    return result


def _safe_text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None