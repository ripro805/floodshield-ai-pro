"""
/admin/hospitals/import -- admin-only CSV import for the Hospital
Directory.

Accepts a CSV file upload that matches the schema in
`backend/data/seed/hospital_resources.csv` (district, hospital_name,
beds, doctors, nurses, ors_stock, iv_saline_stock, antibiotics_stock,
plus the optional address / upazila / phone columns).  Runs the same
parse / dedupe / upsert pipeline as the standalone seeder
(`python -m app.scripts.seed_hospitals --reset`).

Why expose this as an endpoint?
-------------------------------
  - Lets an admin re-import a corrected government CSV without
    shelling onto the server.
  - Reuses every dedupe / synthetic-address / weighted-occupancy
    guarantee the CLI seeder has.
  - Returns a structured summary so the UI can show "imported
    262 facilities across 64 districts" and the `skipped` reasons
    are surfaced for the admin to investigate.

The endpoint is admin-only -- it wipes / rewrites hospital rows.
"""
from __future__ import annotations

import csv
import io
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth_deps import require_roles
from app.auth_models import UserRole
from app.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin/hospitals",
    tags=["Admin Hospital Import"],
    dependencies=[Depends(require_roles(UserRole.admin))],
)

# Reasonable upper bound for an admin-uploaded CSV.  The seed file is
# ~50 KB, so 10 MB is plenty of room for a national export while still
# rejecting accidental megabyte-class uploads.
_MAX_BYTES = 10 * 1024 * 1024


class ImportSummary(BaseModel):
    """Response shape for the import endpoint.

    `deduped_rows`  = the number of unique (name, district) groups
                      the CSV produced after the weighted-mean merge.
    `districts`     = the number of canonical districts represented.
    `hospitals_affected` = rows inserted or updated.
    `rollups_built` = DistrictHospitalAggregate rows recomputed.
    `backfilled`    = synthetic rows added to cover empty districts
                      (only happens when `reset=True` or with the
                      standard seeder's coverage guarantee).
    `skipped`       = the first 50 parse-skip reasons; the full list
                      is in the server log.
    `data_source`   = "admin_import" -- stamped on every row so the
                      UI's "Sample data" badge disappears.
    """
    deduped_rows: int
    districts: int
    hospitals_affected: int
    rollups_built: int
    backfilled: int
    skipped: list[str]
    data_source: str = "admin_import"


def _parse_only(path: Path) -> tuple[list[dict], list[str]]:
    """Run the same dedupe the CLI seeder uses, but WITHOUT touching
    the database.  Returns (deduped_rows, skipped_reasons)."""
    from app.scripts.seed_hospitals import parse_csv
    return parse_csv(path)


@router.post(
    "/import",
    response_model=ImportSummary,
    summary="Import (or replace) the hospital directory from a CSV",
)
async def import_hospitals_csv(
    file: UploadFile = File(..., description="CSV with at least columns: district, hospital_name, beds"),
    reset: bool = Form(
        False,
        description="If true, wipe every existing hospital before inserting. "
                    "Coverage backfill is skipped -- a partial CSV will leave empty districts.",
    ),
    db: Session = Depends(get_db),
):
    # ─── 1. Validate the upload ──────────────────────────────────────
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload must be a .csv file",
        )

    # Buffer the upload so we can both check the size and write to a
    # temp file (csv.DictReader needs a real file with newlines).
    contents = await file.read()
    if len(contents) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV is empty",
        )
    if len(contents) > _MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"CSV exceeds {_MAX_BYTES // (1024 * 1024)} MB cap",
        )

    # Sanity-check the first non-blank line looks like a header.
    head = contents[:2048].decode("utf-8", errors="replace")
    first_line = next(
        (ln for ln in head.splitlines() if ln.strip()), ""
    ).lower()
    if "district" not in first_line or "hospital_name" not in first_line:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "CSV header is missing required columns.  "
                "Expected at least: district, hospital_name.  "
                "Optional: beds, doctors, nurses, ors_stock, "
                "iv_saline_stock, antibiotics_stock, address, upazila, phone."
            ),
        )

    # ─── 2. Persist to a temp file so the existing parse_csv() ─────
    with tempfile.NamedTemporaryFile(
        delete=False, suffix=".csv", mode="wb"
    ) as tmp:
        tmp.write(contents)
        tmp_path = Path(tmp.name)

    try:
        deduped, skipped = _parse_only(tmp_path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except (KeyError, csv.Error) as e:
        # csv.Error = bad header; KeyError = unexpected column
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CSV could not be parsed: {e}",
        )
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass

    if not deduped:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "CSV had no usable rows after dedupe. "
                f"First few skip reasons: {skipped[:3]}"
            ),
        )

    # ─── 3. Apply the import (same pipeline as the CLI) ─────────────
    # Import lazily so the seed module's required side-effect imports
    # (`app.auth_models` for the users-table FK resolution) run in the
    # same order as the CLI.
    from app.scripts.seed_hospitals import (
        upsert_districts,
        upsert_hospitals,
        backfill_missing_districts,
        rebuild_district_rollups,
    )

    try:
        if reset:
            # Drop every hospital row before re-applying.  We use a
            # single DELETE rather than upsert_hospitals(..., reset=True)
            # to keep the seeder's hot path free of admin-specific
            # branching.
            from app.reference_models import Hospital, DistrictHospitalAggregate
            db.query(Hospital).delete()
            db.commit()
            logger.info("admin/import reset: deleted all hospitals")

        # Reuse the CLI's per-row upsert path so data_source gets
        # stamped to the right value.  We override the source below
        # for every row that was just inserted.
        name_to_id = upsert_districts(db)
        affected, _skipped_upsert = upsert_hospitals(db, name_to_id, deduped)

        # Re-stamp the data_source so the UI's "Sample data" badge
        # doesn't appear on a real admin import.  We stamp rows
        # whose (name, district_id) match the import batch, not the
        # whole table -- the latter would clobber every other
        # operator's "manual_update" rows.
        if affected:
            from app.reference_models import Hospital
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            import_pairs = [
                (row["name"].strip(), name_to_id[row["district"]])
                for row in deduped
                if row["district"] in name_to_id
            ]
            for name, district_id in import_pairs:
                db.query(Hospital).filter(
                    Hospital.name == name,
                    Hospital.district_id == district_id,
                ).update(
                    {Hospital.data_source: "admin_import",
                     Hospital.last_updated: now},
                    synchronize_session=False,
                )
            db.commit()

        # Coverage backfill only when not wiping -- but the
        # backfill helper takes "districts already present in the
        # database", not "districts in THIS csv batch".  If we
        # passed the csv batch, an admin importing 1 new district
        # would trigger a re-seed of the other 63, which is the
        # wrong behaviour.  So we union the import batch with the
        # current DB state before asking backfill to fill gaps.
        #
        # We use raw text() SQL here because the SQLAlchemy session
        # can serve a stale cached result for the distinct(district)
        # column query if the session has been used to upsert rows
        # earlier in this same request -- and we absolutely do NOT
        # want a "no rows found" cache to trigger a 128-row
        # backfill on top of an already-populated DB.
        backfilled = 0
        if not reset:
            from sqlalchemy import text
            from app.reference_models import Hospital
            db.execute(text("SELECT 1"))  # force session refresh
            # Expire all cached Hospital instances so a fresh
            # SELECT below can't be served from the identity map.
            db.expire_all()
            db_present = {
                row[0] for row in db.execute(
                    text("SELECT DISTINCT district FROM hospitals WHERE district IS NOT NULL")
                ).fetchall()
            }
            csv_present = {row["district"] for row in deduped}
            present = db_present | csv_present
            backfilled = backfill_missing_districts(db, name_to_id, present)

        rollups = rebuild_district_rollups(db)
    except Exception as exc:  # pragma: no cover -- logged + surfaced
        db.rollback()
        logger.exception("admin/import failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Import failed and was rolled back: {exc}",
        )

    districts = len({row["district"] for row in deduped})
    return ImportSummary(
        deduped_rows=len(deduped),
        districts=districts,
        hospitals_affected=int(affected or 0),
        rollups_built=int(rollups or 0),
        backfilled=int(backfilled),
        skipped=skipped[:50],
    )


@router.get(
    "/import/template",
    summary="Download a small example CSV that matches the import schema",
)
def import_template_csv():
    """Tiny CSV that demonstrates the required + optional columns.
    Useful for admins hand-editing a government export."""
    from fastapi.responses import PlainTextResponse
    sample = (
        "district,hospital_name,beds,doctors,nurses,ors_stock,"
        "iv_saline_stock,antibiotics_stock,address,upazila,phone\n"
        # Canonical 64-district name -- legacy spellings are auto-normalised
        # server-side (Barisal->Barishal, Bogra->Bogura, Comilla->Cumilla).
        "Dhaka,Dhaka Medical College Hospital,1700,250,800,5000,3000,2000,"
        "Secretariat Rd,Shahbagh,+880-2-55165000\n"
        "Chattogram,Chattogram Medical College Hospital,1313,180,650,4000,2500,1500,"
        "K B Fazlul Kader Rd,Panchlaish,+880-31-619500\n"
        "Khulna,Khulna Medical College Hospital,500,80,260,1500,900,500,"
        "Boyra Main Rd,Sadar,+880-41-760555\n"
        "Barishal,Sher-e-Bangla Medical College Hospital,600,75,240,1200,800,400,"
        "Band Rd,Sadar,+880-431-2173499\n"
        # Below: minimal row to show the seeder will backfill coordinates
        "Rangamati,Rangamati Sadar Hospital,250,30,120,800,500,200,,,\n"
    )
    return PlainTextResponse(
        content=sample,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="hospital_directory_template.csv"'},
    )
