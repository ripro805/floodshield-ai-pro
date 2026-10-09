"""District and upazila lookup backed by the locations table.

The data is seeded from `data/climate_dataset_fixed.xlsx` on backend startup
(see app.services.seed_reference.seed_locations).  Reads hit the DB so
production deploys behave identically to local dev without needing the
xlsx files inside the container.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.reference_models import Location
from app.schemas import LocationSearchResponse
from app.district_names import all_pairs as _all_district_pairs

router = APIRouter(prefix="/api/locations", tags=["Location Search"])


def _all_locations(db: Session) -> list[dict[str, str]]:
    rows = db.query(Location).all()
    out: list[dict[str, str]] = []
    for row in rows:
        if row.kind == "district":
            out.append({"name": row.district, "district": row.district, "kind": "district"})
        elif row.upazila:
            out.append({"name": row.upazila, "district": row.district, "kind": "upazila"})
    return out


@router.get("/search", response_model=LocationSearchResponse)
def search_locations(
    q: str = Query(..., min_length=2, max_length=80),
    db: Session = Depends(get_db),
):
    term = q.casefold().strip()
    locations = _all_locations(db)
    matches = [
        item for item in locations
        if term in item["name"].casefold() or term in item["district"].casefold()
    ]
    return LocationSearchResponse(query=q, results=matches[:25])


@router.get("/bangla")
def bangla_districts():
    """Return the canonical 64-district English -> Bangla name table.

    Open to all callers (no auth): this is static reference data, not
    sensitive.  The frontend caches the result once and uses it to
    render the data-status table with a Bangla subtitle next to each
    English district name.
    """
    pairs = _all_district_pairs()
    return {"count": len(pairs), "pairs": pairs}
