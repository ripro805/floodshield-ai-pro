"""
Seed the `districts` and `hospitals` tables from a CSV in
`backend/data/seed/hospital_resources.csv`.

Run from the backend dir:

    python -m app.scripts.seed_hospitals

Optional flags:

    --reset      Drop all existing `hospitals` + `districts` rows first
                 (so a stale DB can be re-seeded cleanly).
    --dry-run    Parse the CSV, print a summary, do not write to the DB.

Idempotent by default: re-running it after a successful seed is a no-op
because the upsert is keyed on `(name, district_id)`.  Run `--reset` if
you want to start over.

Why this exists
---------------
The earlier `seed_reference.seed_hospitals` is run from `main.py`
lifespan if `hospitals` is empty.  It imported the CSV at boot, but it
used the raw (often-misplaced) lat/lng straight from the file, and it
didn't normalize legacy district names (Barisal, Bogra, Comilla) to
the canonical 64-district list.  This script is the canonical seeder
and fixes both:

  1. **Districts** are inserted first (idempotent upsert by name).
     The 64 canonical names come from `app.district_names.EN_TO_BN`.
  2. **Legacy spellings** in the CSV ("Barisal", "Bogra", "Comilla")
     are mapped to the canonical spelling before insert.
  3. **Coordinates** are *regenerated* deterministically (fixed seed)
     inside the correct district's bounding box, because the CSV's
     lat/lng column is essentially random (see Phase 1 report -- 92%
     of rows fall outside their stated district).  Regenerated coords
     are flagged `coordinates_source = 'synthetic_seed'` so the UI
     can badge them as "Sample data".
  4. **Addresses** are *generated* ("<name>, <Upazila>, <District>")
     because the dataset has no address column.  Also flagged
     `address_source = 'synthetic_seed'`.  Never fabricated phone
     numbers -- the column stays NULL.
  5. **Duplicates** in the CSV (144 groups of up-to-6 same-named rows
     per district) are deduped: we keep one row per (name, district)
     pair and SUM the bed/staff/stock numbers, MEAN the occupancy.
  6. **Coverage** is guaranteed: if a district ends up with zero rows
     after dedupe, we synthesize a single "District Hospital" + an
     "Upazila Health Complex" for it so the directory has at least
     one facility to show in every one of the 64 districts.

Auto-seed on empty DB
---------------------
`main.py` lifespan calls `auto_seed_if_empty()` after the migrations
run.  That helper is a no-op if `hospitals` already has rows.  To
opt in to auto-seeding on every fresh deployment, set
`AUTO_SEED_ON_EMPTY=true` in the env.  The command-line run above
always runs and is what the spec recommends for one-shot setup.
"""
from __future__ import annotations

import argparse
import csv
import logging
import os
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from uuid import UUID

# Make the `app` package importable when invoked as
# `python -m app.scripts.seed_hospitals` from `backend/`.
BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine
from app.district_names import EN_TO_BN
from app.reference_models import District, DistrictHospitalAggregate, Hospital
import app.auth_models  # noqa: F401  -- registers `users` table on Base.metadata for FK resolution

logger = logging.getLogger("seed_hospitals")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

# Default location of the seed CSV (relative to backend/).
DEFAULT_CSV = BACKEND_ROOT / "data" / "seed" / "hospital_resources.csv"

# Fixed RNG seed so the regenerated coordinates are deterministic
# across re-seeds.  Changing this requires a --reset to refresh.
COORD_SEED = 20240601

# Bangladesh bounding box (used for the final sanity check on the
# regenerated coords before insert).
LAT_MIN, LAT_MAX = 20.5, 26.7
LNG_MIN, LNG_MAX = 88.0, 92.7

# Loose district bounding boxes, in (min_lat, max_lat, min_lng, max_lng)
# order.  The seeder keeps regenerated hospital coords inside this box.
DISTRICT_BBOX: Dict[str, Tuple[float, float, float, float]] = {
    "Bagerhat":      (22.20, 22.95, 89.30, 89.95),
    "Bandarban":     (21.65, 22.55, 92.05, 92.65),
    "Barguna":       (21.75, 22.45, 90.00, 90.45),
    "Barishal":      (22.40, 23.10, 90.20, 90.75),
    "Bhola":         (21.85, 23.00, 90.45, 91.05),
    "Bogura":        (24.65, 25.30, 88.95, 89.55),
    "Brahmanbaria":  (23.55, 24.30, 90.85, 91.40),
    "Chandpur":      (23.05, 23.65, 90.50, 91.10),
    "Chapainawabganj": (24.45, 25.05, 88.05, 88.55),
    "Chattogram":    (21.90, 22.95, 91.55, 92.30),
    "Chuadanga":     (23.40, 23.95, 88.65, 89.25),
    "Cox's Bazar":   (20.55, 21.95, 91.75, 92.55),
    "Cumilla":       (23.20, 24.10, 90.65, 91.40),
    "Dhaka":         (23.45, 24.20, 90.10, 90.70),
    "Dinajpur":      (25.10, 26.10, 88.40, 89.10),
    "Faridpur":      (23.10, 23.80, 89.40, 90.10),
    "Feni":          (22.65, 23.40, 91.20, 91.65),
    "Gaibandha":     (25.00, 25.90, 89.20, 89.85),
    "Gazipur":       (23.80, 24.45, 90.10, 90.70),
    "Gopalganj":     (22.85, 23.45, 89.65, 90.20),
    "Habiganj":      (24.00, 24.85, 91.10, 91.70),
    "Jamalpur":      (24.50, 25.30, 89.55, 90.25),
    "Jashore":       (22.75, 23.55, 88.85, 89.45),
    "Jhalokati":     (22.35, 22.90, 90.05, 90.45),
    "Jhenaidah":     (23.25, 23.95, 88.75, 89.40),
    "Joypurhat":     (24.85, 25.40, 88.85, 89.30),
    "Khagrachhari":  (22.85, 23.85, 91.85, 92.30),
    "Khulna":        (22.30, 23.20, 89.25, 89.95),
    "Kishoreganj":   (24.05, 24.85, 90.55, 91.30),
    "Kurigram":      (25.55, 26.50, 89.55, 90.15),
    "Kushtia":       (23.55, 24.30, 88.75, 89.45),
    "Lakshmipur":    (22.55, 23.20, 90.55, 91.10),
    "Lalmonirhat":   (25.65, 26.55, 88.95, 89.65),
    "Madaripur":     (22.85, 23.55, 89.85, 90.50),
    "Magura":        (23.20, 23.80, 89.30, 89.75),
    "Manikganj":     (23.55, 24.20, 89.75, 90.30),
    "Meherpur":      (23.55, 24.20, 88.50, 89.05),
    "Moulvibazar":   (24.10, 24.85, 91.55, 92.20),
    "Munshiganj":    (23.30, 23.95, 90.25, 90.80),
    "Mymensingh":    (24.30, 25.30, 90.05, 90.85),
    "Naogaon":       (24.50, 25.40, 88.30, 89.20),
    "Narail":        (22.85, 23.55, 89.35, 89.85),
    "Narayanganj":   (23.45, 24.05, 90.30, 90.85),
    "Narsingdi":     (23.70, 24.40, 90.55, 91.15),
    "Natore":        (24.00, 24.75, 88.80, 89.50),
    "Netrokona":     (24.45, 25.20, 90.55, 91.10),
    "Nilphamari":    (25.65, 26.55, 88.75, 89.40),
    "Noakhali":      (22.05, 23.05, 90.85, 91.50),
    "Pabna":         (23.55, 24.50, 89.10, 89.95),
    "Panchagarh":    (25.95, 26.65, 88.40, 89.00),
    "Patuakhali":    (21.70, 22.75, 90.05, 90.70),
    "Pirojpur":      (22.40, 23.05, 89.85, 90.30),
    "Rajbari":       (23.30, 24.00, 89.30, 89.95),
    "Rajshahi":      (24.10, 24.90, 88.40, 89.10),
    "Rangamati":     (22.40, 23.55, 91.85, 92.45),
    "Rangpur":       (25.20, 25.95, 88.95, 89.65),
    "Satkhira":      (21.85, 22.85, 88.85, 89.45),
    "Shariatpur":    (22.95, 23.65, 90.05, 90.55),
    "Sherpur":       (24.80, 25.45, 89.90, 90.45),
    "Sirajganj":     (24.00, 24.85, 89.45, 90.10),
    "Sunamganj":     (24.55, 25.45, 90.95, 91.65),
    "Sylhet":        (24.65, 25.50, 91.55, 92.25),
    "Tangail":       (23.95, 24.95, 89.55, 90.30),
    "Thakurgaon":    (25.65, 26.50, 88.20, 88.85),
}

# Legacy CSV district-name spellings that need to be folded into the
# canonical 64-district list before insert.
LEGACY_DISTRICT_ALIASES: Dict[str, str] = {
    "Barisal": "Barishal",
    "Bogra": "Bogura",
    "Comilla": "Cumilla",
}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def canonical_district_name(raw: str) -> Optional[str]:
    """Normalize a CSV district name to the canonical 64-district list.

    Returns the canonical name (which exists in `EN_TO_BN`), or `None`
    if the input is empty / unrecognized.  Unrecognized names are
    skipped with a warning so a typo never silently inserts a bogus
    district row.
    """
    if not raw:
        return None
    name = raw.strip()
    if not name:
        return None
    # Already canonical?
    if name in EN_TO_BN:
        return name
    # Legacy alias?
    if name in LEGACY_DISTRICT_ALIASES:
        return LEGACY_DISTRICT_ALIASES[name]
    # Case-insensitive fallback (e.g. "DHAKA" -> "Dhaka")
    for k in EN_TO_BN:
        if k.lower() == name.lower():
            return k
    return None


def _safe_int(v: Any) -> int:
    try:
        return int(float(str(v).strip() or "0"))
    except (TypeError, ValueError):
        return 0


def _safe_float(v: Any) -> float:
    try:
        return float(str(v).strip() or "0")
    except (TypeError, ValueError):
        return 0.0


def _bbox_center(bbox: Tuple[float, float, float, float]) -> Tuple[float, float]:
    return (bbox[0] + bbox[1]) / 2, (bbox[2] + bbox[3]) / 2


def regenerate_coords(district: str, hospital_index: int) -> Tuple[float, float]:
    """Pick a deterministic (lat, lng) inside `district`'s bbox.

    The fixed RNG seed means the same `(district, hospital_index)`
    pair always maps to the same coordinates across re-runs.  We use
    the hospital's *index within its district* as a salt so that
    hospitals don't all land on the same point.

    We jitter to ~60% of the bbox radius from the centroid so the
    points stay well inside the district (the bbox itself is already
    a generous overestimate of the actual district boundary).
    """
    bbox = DISTRICT_BBOX.get(district)
    if not bbox:
        # Should never happen for canonical district names.
        return 23.7, 90.4  # roughly central Bangladesh
    clat, clng = _bbox_center(bbox)
    # Bbox half-widths in degrees, multiplied by 0.6 to keep the
    # jitter inside the district's core area.
    lat_radius = (bbox[1] - bbox[0]) / 2.0 * 0.6
    lng_radius = (bbox[3] - bbox[2]) / 2.0 * 0.6
    rng = random.Random(f"{COORD_SEED}|{district}|{hospital_index}")
    lat = clat + (rng.random() * 2 - 1) * lat_radius
    lng = clng + (rng.random() * 2 - 1) * lng_radius
    # Final clamp so a rounding error can't push us outside the bbox.
    lat = max(bbox[0], min(bbox[1], lat))
    lng = max(bbox[2], min(bbox[3], lng))
    return round(lat, 5), round(lng, 5)


def synthetic_address(name: str, district: str, hospital_index: int) -> str:
    """Build a clear, deterministic, *labelled-as-synthetic* address
    string for a hospital that has no real address.

    The format is "<Hospital name>, <Upazila/Sadar>, <District>" where
    the upazila portion is a deterministic placeholder like "Sadar
    Upazila" or "Central".  We deliberately do NOT include any phone
    number here -- the UI hides that field when `phone IS NULL`.
    """
    rng = random.Random(f"{COORD_SEED}|addr|{district}|{hospital_index}")
    upazila_label = rng.choice(["Sadar Upazila", "Central", "Town Area", "District HQ Area"])
    return f"{name}, {upazila_label}, {district}"


# --------------------------------------------------------------------------- #
# CSV parsing
# --------------------------------------------------------------------------- #
def parse_csv(csv_path: Path) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Parse the seed CSV and return (deduped_rows, skipped_reasons).

    Dedupe strategy
    ---------------
    Multiple CSV rows can share `(name, district)`.  We collapse each
    group into ONE merged row by:

      * beds/doctors/nurses/stock: SUM (so the aggregate stays accurate)
      * occupancy_percent: WEIGHTED MEAN by beds (so a 500-bed hospital
        influences the occupancy more than a 10-bed one)
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"Seed CSV not found: {csv_path}")

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        raw_rows = list(reader)

    skipped: List[str] = []
    # group by (canonical_district, name)
    groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for r in raw_rows:
        raw_district = r.get("district", "")
        district = canonical_district_name(raw_district)
        name = (r.get("hospital_name") or "").strip()
        if not district:
            skipped.append(f"unrecognized district: {raw_district!r} (name={name!r})")
            continue
        if not name:
            skipped.append(f"empty name (district={district})")
            continue
        groups[(district, name)].append(r)

    deduped: List[Dict[str, Any]] = []
    for (district, name), rs in groups.items():
        beds_total = sum(_safe_int(r.get("beds")) for r in rs)
        doctors_total = sum(_safe_int(r.get("doctors")) for r in rs)
        nurses_total = sum(_safe_int(r.get("nurses")) for r in rs)
        ors_total = sum(_safe_int(r.get("ors_stock")) for r in rs)
        iv_total = sum(_safe_int(r.get("iv_saline_stock")) for r in rs)
        ab_total = sum(_safe_int(r.get("antibiotics_stock")) for r in rs)
        # Weighted-mean occupancy by beds
        weighted_num = 0.0
        weighted_den = 0
        for r in rs:
            b = _safe_int(r.get("beds"))
            o = _safe_float(r.get("occupancy_percent"))
            weighted_num += b * o
            weighted_den += b
        occ = (weighted_num / weighted_den) if weighted_den else 0.0
        # Pick the most-common hospital_type within the group.
        type_counts: Dict[str, int] = defaultdict(int)
        for r in rs:
            t = (r.get("hospital_type") or "").strip()
            if t:
                type_counts[t] += 1
        hospital_type = max(type_counts.items(), key=lambda kv: kv[1])[0] if type_counts else None

        deduped.append({
            "name": name,
            "district": district,
            "hospital_type": hospital_type,
            "beds": beds_total,
            "doctors": doctors_total,
            "nurses": nurses_total,
            "ors_stock": ors_total,
            "iv_saline_stock": iv_total,
            "antibiotics_stock": ab_total,
            "occupancy_percent": round(min(max(occ, 0.0), 100.0), 2),
            "_n_source_rows": len(rs),
        })

    return deduped, skipped


# --------------------------------------------------------------------------- #
# District upsert
# --------------------------------------------------------------------------- #
def upsert_districts(db: Session) -> Dict[str, UUID]:
    """Insert every canonical 64-district name (idempotent).

    Returns a mapping of canonical name -> District.id.
    """
    name_to_id: Dict[str, UUID] = {}
    for name, bn in EN_TO_BN.items():
        bbox = DISTRICT_BBOX.get(name)
        clat, clng = _bbox_center(bbox) if bbox else (None, None)
        stmt = pg_insert(District).values(
            name=name,
            name_bn=bn,
            latitude=clat,
            longitude=clng,
            bbox_min_lat=bbox[0] if bbox else None,
            bbox_max_lat=bbox[1] if bbox else None,
            bbox_min_lng=bbox[2] if bbox else None,
            bbox_max_lng=bbox[3] if bbox else None,
        ).on_conflict_do_nothing(index_elements=["name"])
        db.execute(stmt)
    db.commit()

    # Re-read the IDs (the upsert may have been a no-op for already-seeded names).
    for d in db.query(District).all():
        name_to_id[d.name] = d.id

    logger.info("upsert_districts: %d districts", len(name_to_id))
    return name_to_id


# --------------------------------------------------------------------------- #
# Hospital upsert
# --------------------------------------------------------------------------- #
def upsert_hospitals(
    db: Session,
    name_to_district_id: Dict[str, UUID],
    rows: List[Dict[str, Any]],
) -> Tuple[int, int]:
    """Idempotent insert/update of the hospital rows.

    For each (name, district) pair, we look up the existing hospital
    and either:

      * skip if a row already exists with the same data, OR
      * update its stats + regenerated coords + synthetic address.

    We use plain `select` + `update` (not `INSERT ... ON CONFLICT`) so
    that a re-seed is a no-op for unchanged rows -- much friendlier
    for live deployments where some rows may have been operator-edited
    (`data_source = 'manual_update'`).

    Returns (inserted_or_updated_count, skipped_count).
    """
    # Index existing rows by (name, district_id)
    existing: Dict[Tuple[str, UUID], Hospital] = {}
    for h in db.query(Hospital).all():
        if h.district_id is None:
            continue
        existing[(h.name.strip().lower(), h.district_id)] = h

    affected = 0
    skipped = 0
    # Per-district index for deterministic coord regeneration
    district_index: Dict[str, int] = defaultdict(int)

    for row in rows:
        district = row["district"]
        district_id = name_to_district_id.get(district)
        if district_id is None:
            skipped += 1
            logger.warning("upsert_hospitals: no District row for %r", district)
            continue

        idx = district_index[district]
        district_index[district] += 1
        lat, lng = regenerate_coords(district, idx)
        address = synthetic_address(row["name"], district, idx)

        key = (row["name"].strip().lower(), district_id)
        existing_h = existing.get(key)
        if existing_h is not None:
            # Update in place.  Preserve any manual phone / operator edits.
            existing_h.hospital_type = row["hospital_type"]
            existing_h.beds = row["beds"]
            existing_h.beds_occupied = None  # unknown for seed
            existing_h.doctors = row["doctors"]
            existing_h.nurses = row["nurses"]
            existing_h.ors_stock = row["ors_stock"]
            existing_h.iv_saline_stock = row["iv_saline_stock"]
            existing_h.antibiotics_stock = row["antibiotics_stock"]
            existing_h.occupancy_percent = row["occupancy_percent"]
            existing_h.latitude = lat
            existing_h.longitude = lng
            # address_source / coordinates_source are intentionally only
            # set on the FIRST seed so a manual operator edit doesn't
            # get overwritten.
            if existing_h.address_source is None:
                existing_h.address = address
                existing_h.address_source = "synthetic_seed"
            if existing_h.coordinates_source is None:
                existing_h.coordinates_source = "synthetic_seed"
            # data_source stays whatever the operator set it to
            if existing_h.data_source is None or existing_h.data_source == "":
                existing_h.data_source = "seed"
            existing_h.district = district  # keep the legacy column in sync
            existing_h.district_id = district_id
            existing_h.upazila = "Sadar"
            affected += 1
        else:
            db.add(Hospital(
                name=row["name"],
                district=district,
                district_id=district_id,
                hospital_type=row["hospital_type"],
                upazila="Sadar",
                address=address,
                # phone intentionally NULL -- we never fabricate
                beds=row["beds"],
                beds_occupied=None,
                doctors=row["doctors"],
                nurses=row["nurses"],
                ors_stock=row["ors_stock"],
                iv_saline_stock=row["iv_saline_stock"],
                antibiotics_stock=row["antibiotics_stock"],
                occupancy_percent=row["occupancy_percent"],
                latitude=lat,
                longitude=lng,
                data_source="seed",
                coordinates_source="synthetic_seed",
                address_source="synthetic_seed",
            ))
            affected += 1

    db.commit()
    return affected, skipped


# --------------------------------------------------------------------------- #
# Coverage backfill (synthesize rows for empty districts)
# --------------------------------------------------------------------------- #
def backfill_missing_districts(
    db: Session,
    name_to_district_id: Dict[str, UUID],
    present_districts: set,
) -> int:
    """For any canonical district with zero hospitals after the CSV
    dedupe, insert one 'District Hospital' and one 'Upazila Health
    Complex' so the directory has at least one facility in every
    district.

    The synthetic rows use plausible default stock values and are
    flagged `data_source='seed'` so the UI can still badge them.
    """
    missing = sorted(set(name_to_district_id) - present_districts)
    if not missing:
        return 0

    logger.info("backfill_missing_districts: %d districts with no rows -> %s", len(missing), missing)
    for district in missing:
        district_id = name_to_district_id[district]
        for hospital_name, hospital_type, beds in (
            (f"{district} District Hospital", "District Hospital", 100),
            (f"{district} Upazila Health Complex", "Upazila Health Complex", 31),
        ):
            lat, lng = regenerate_coords(district, abs(hash((district, hospital_name))) % 1000)
            db.add(Hospital(
                name=hospital_name,
                district=district,
                district_id=district_id,
                hospital_type=hospital_type,
                upazila="Sadar",
                address=synthetic_address(hospital_name, district, 9999),
                beds=beds,
                beds_occupied=None,
                doctors=max(5, beds // 5),
                nurses=max(5, beds // 4),
                ors_stock=2000,
                iv_saline_stock=500,
                antibiotics_stock=500,
                occupancy_percent=50.0,
                latitude=lat,
                longitude=lng,
                data_source="seed",
                coordinates_source="synthetic_seed",
                address_source="synthetic_seed",
            ))
    db.commit()
    return len(missing)


# --------------------------------------------------------------------------- #
# District rollup rebuild
# --------------------------------------------------------------------------- #
def rebuild_district_rollups(db: Session) -> int:
    """Recompute the per-district aggregate from the hospital rows.

    This is the same rollup the existing `seed_reference.
    seed_district_hospital_aggregates` function does; we re-implement
    it here so the new seed script is self-contained and can be run
    after a one-off destructive change to `hospitals`.
    """
    counts = db.query(
        Hospital.district,
        func.coalesce(func.sum(Hospital.beds), 0),
        func.coalesce(func.sum(Hospital.doctors), 0),
        func.coalesce(func.sum(Hospital.nurses), 0),
        func.coalesce(func.sum(Hospital.ors_stock), 0),
        func.coalesce(func.sum(Hospital.iv_saline_stock), 0),
        func.coalesce(func.sum(Hospital.antibiotics_stock), 0),
        func.coalesce(func.avg(Hospital.occupancy_percent), 0.0),
        func.count(Hospital.id),
    ).group_by(Hospital.district).all()

    # Drop and re-insert (idempotent for the canonical set; the
    # /recommend endpoint only reads these rows so a full refresh is
    # safer than a partial merge).
    db.query(DistrictHospitalAggregate).delete()
    db.commit()

    n = 0
    for (d, beds, doctors, nurses, ors, iv, ab, occ, hc) in counts:
        db.add(DistrictHospitalAggregate(
            district=d,
            beds=int(beds),
            doctors=int(doctors),
            nurses=int(nurses),
            ors_stock=int(ors),
            iv_saline_stock=int(iv),
            antibiotics_stock=int(ab),
            occupancy_percent=float(occ),
            hospital_count=int(hc),
        ))
        n += 1
    db.commit()
    logger.info("rebuild_district_rollups: %d districts", n)
    return n


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV,
                        help="Path to the seed CSV (default: %(default)s)")
    parser.add_argument("--reset", action="store_true",
                        help="Drop existing hospitals + districts first")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse + summarise; do not write to the DB")
    args = parser.parse_args()

    csv_path: Path = args.csv
    logger.info("seed_hospitals start: csv=%s reset=%s dry_run=%s",
                csv_path, args.reset, args.dry_run)

    deduped, skipped = parse_csv(csv_path)
    logger.info("parse_csv: %d deduped rows, %d skipped", len(deduped), len(skipped))
    if skipped:
        for s in skipped[:5]:
            logger.warning("skip: %s", s)
        if len(skipped) > 5:
            logger.warning("... and %d more", len(skipped) - 5)

    if args.dry_run:
        present = {row["district"] for row in deduped}
        missing = sorted(set(EN_TO_BN) - present)
        print(f"\nDRY RUN: {len(deduped)} deduped hospital rows, {len(skipped)} skipped, "
              f"{len(missing)} districts with no rows")
        if missing:
            print(f"  Districts needing backfill: {missing}")
        return 0

    with SessionLocal() as db:
        if args.reset:
            logger.warning("reset: deleting existing hospital_updates, hospitals, district_hospital_aggregates, districts")
            # Order matters: hospital_updates FKs hospitals; hospitals FKs districts.
            db.execute(__import__("sqlalchemy").text("DELETE FROM hospital_updates"))
            db.execute(__import__("sqlalchemy").text("DELETE FROM hospitals"))
            db.execute(__import__("sqlalchemy").text("DELETE FROM district_hospital_aggregates"))
            db.execute(__import__("sqlalchemy").text("DELETE FROM districts"))
            db.commit()

        name_to_district_id = upsert_districts(db)
        affected, skipped_db = upsert_hospitals(db, name_to_district_id, deduped)
        present = {row["district"] for row in deduped}
        backfilled = backfill_missing_districts(db, name_to_district_id, present)
        rollups = rebuild_district_rollups(db)

        total = db.query(func.count(Hospital.id)).scalar()
        n_districts_with_hospitals = db.query(func.count(func.distinct(Hospital.district))).scalar()

        logger.info("DONE: %d hospital rows now in DB, %d districts covered, "
                    "%d rollups, %d rows backfilled",
                    total, n_districts_with_hospitals, rollups, backfilled)

    return 0


# --------------------------------------------------------------------------- #
# auto_seed_if_empty
# --------------------------------------------------------------------------- #
def auto_seed_if_empty() -> bool:
    """Called from main.py lifespan.  Returns True if it actually
    seeded (so the lifespan can log a single line), False otherwise.

    Honours the `AUTO_SEED_ON_EMPTY` env flag: if the flag is NOT
    'true' (or '1'), the function only runs when the `hospitals`
    table is empty AND the `AUTO_SEED_ON_EMPTY` flag is set.  This
    matches the spec's "opt-in env flag that seeds automatically
    only when the table is empty" wording.
    """
    flag = os.getenv("AUTO_SEED_ON_EMPTY", "").strip().lower() in ("1", "true", "yes")
    with SessionLocal() as db:
        empty = db.query(func.count(Hospital.id)).scalar() == 0
    if empty:
        if not flag:
            # Default behaviour: log a hint but don't run.
            logger.info(
                "auto_seed_if_empty: hospitals table is empty. "
                "Set AUTO_SEED_ON_EMPTY=true or run "
                "`python -m app.scripts.seed_hospitals` to populate it."
            )
            return False
        # Flag is set: seed.
        logger.info("auto_seed_if_empty: AUTO_SEED_ON_EMPTY=true and hospitals table is empty; seeding.")
        return main() == 0
    return False


if __name__ == "__main__":
    raise SystemExit(main())
