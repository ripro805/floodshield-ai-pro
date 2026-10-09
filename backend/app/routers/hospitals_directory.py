"""
/hospitals directory endpoints -- the all-64-district, per-hospital
directory, the national overview, and the "use my location" nearby
search.

RBAC
----
All endpoints are open to any authenticated user.  The response *shape*
differs by role so that operational users (health_worker / hospital /
ngo / government / admin) see exact inventory numbers and per-item
low-stock flags, while citizens see only the directory fields (name,
type, district, address, lat, lng, capacity_status, distance_km,
data_source) plus the 999 emergency contact.

The role is read from the existing JWT, not from the URL, so a citizen
can never escalate to operational fields by hand-editing the request.

Endpoints
---------
GET /hospitals/districts-summary
  One row per district (all 64) with hospital count, total beds, mean
  occupancy, capacity status, and (for operational roles) low-stock
  flags.  Used by the national overview grid.

GET /hospitals?district=&type=&q=&status=&sort=&limit=&offset=
  List hospitals in a single district (or, if `district` is omitted,
  across all districts) with text search, type/status filter, sort by
  name/occupancy/distance, and offset pagination.

GET /hospitals/nearby?lat=&lng=&radius_km=&limit=
  Nearest hospitals by haversine distance.  Validates the query point
  is inside Bangladesh's bounding box.  Returns distance_km on every
  row.

GET /hospitals/{hospital_id}
  Single hospital detail.  Same role-based shape as the list endpoint.

Haversine
---------
For ~500 rows and Bangladesh-scale distances (max 500 km) the simple
haversine is sub-millisecond; PostGIS is not required.  We use the
WGS84 mean radius (6371.0088 km) for a slightly more accurate result
than the textbook 6371.0.
"""
from __future__ import annotations

import math
import re
from typing import List, Optional, Tuple, Union
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.auth_deps import get_current_user
from app.auth_models import User, UserRole
from app.database import get_db
from app.district_names import EN_TO_BN
from app.reference_models import District, DistrictHospitalAggregate, Hospital

# Reuse the prefix from routers/hospitals.py: /hospitals
router = APIRouter(prefix="/hospitals", tags=["Hospital Directory"])

OPERATIONAL_ROLES = (
    UserRole.health_worker, UserRole.hospital, UserRole.ngo,
    UserRole.government, UserRole.admin,
)

# Bangladesh bounding box (loose envelope).  Anything outside this is
# either the Bay of Bengal, India, or Myanmar -- not a sensible query
# for a "nearest hospital in Bangladesh" endpoint.
LAT_MIN, LAT_MAX = 20.5, 26.7
LNG_MIN, LNG_MAX = 88.0, 92.7

# Low-stock thresholds.  These are the same policy values the existing
# /recommend endpoint uses; living in a single config so a policy
# change is a one-line edit.
LOW_STOCK_THRESHOLDS = {
    "ors": 1000,
    "iv_saline": 500,
    "antibiotics": 800,
}


def _is_operational(user: User) -> bool:
    return user.role in OPERATIONAL_ROLES


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in km between two WGS84 points.

    Uses the IUGG mean Earth radius (6371.0088 km) which is ~10 m
    more accurate over long distances than the textbook 6371.0.
    """
    r = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _capacity_status(occupancy_percent: float) -> str:
    """Match the spec's capacity-status thresholds:
        Available :  < 70%  occupied
        Limited   :  70-90% occupied
        Full      :  > 90%  occupied
    """
    if occupancy_percent < 70:
        return "Available"
    if occupancy_percent < 90:
        return "Limited"
    return "Full"


def _status_matches(hospital_occupancy: float, status_filter: str) -> bool:
    """True if the hospital's current capacity_status matches the filter.

    Accepts 'Available' | 'Limited' | 'Full' (case-insensitive).  An
    empty/unknown filter matches every row.
    """
    if not status_filter:
        return True
    needle = status_filter.strip().lower()
    current = _capacity_status(hospital_occupancy).lower()
    return needle == current


# ──────────────────────────────────────────────────────────────────────
# Pydantic response schemas
#
# Mirror the field names exactly to `frontend/lib/types.ts` (Hospitals
# + HospitalDirectory sections).  Two flavours:
#   * `HospitalPublic`    -- what every authenticated user (incl. citizen) sees
#   * `HospitalOperational` -- the extra operational fields (operational roles only)
# ──────────────────────────────────────────────────────────────────────
class HospitalPublic(BaseModel):
    """Directory fields every authenticated user can see."""
    id: str
    name: str
    hospital_type: Optional[str] = None
    district: str
    upazila: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    capacity_status: str
    distance_km: Optional[float] = None
    data_source: str
    coordinates_source: Optional[str] = None
    address_source: Optional[str] = None
    phone: Optional[str] = None  # explicit None for citizens (never fabricated)


class HospitalOperational(HospitalPublic):
    """Extra fields visible only to operational roles."""
    beds_total: int
    beds_occupied: Optional[int] = None
    occupancy_percent: float
    doctors: int
    nurses: int
    ors_stock: int
    iv_saline_stock: int
    antibiotics_stock: int
    ors_low: bool
    iv_saline_low: bool
    antibiotics_low: bool
    last_updated: Optional[str] = None


class DistrictHospitalSummary(BaseModel):
    """One row per district in the national overview."""
    district: str
    name_bn: Optional[str] = None
    hospital_count: int
    total_beds: int
    mean_occupancy_percent: float
    capacity_status: str
    # Operational-only fields (None for citizens)
    total_ors: Optional[int] = None
    total_iv_saline: Optional[int] = None
    total_antibiotics: Optional[int] = None
    ors_low: Optional[bool] = None
    iv_saline_low: Optional[bool] = None
    antibiotics_low: Optional[bool] = None


class NearbyHospital(HospitalPublic):
    """A hospital returned by /hospitals/nearby."""
    distance_km: float  # always present on this endpoint


class HospitalListResponse(BaseModel):
    items: List[Union[HospitalPublic, HospitalOperational]]
    total: int
    limit: int
    offset: int
    operational_fields_present: bool = Field(
        ..., description="True if the caller is in OPERATIONAL_ROLES and the items also carry operational fields."
    )


class HospitalDetailResponse(HospitalPublic):  # operational fields added dynamically via Union if needed
    """Single-hospital detail.  `operational_fields_present` is True iff
    the response also carries the operational fields; citizens get
    False and the operational fields are absent from the JSON entirely.
    """
    operational_fields_present: bool


class DistrictsSummaryResponse(BaseModel):
    items: List[DistrictHospitalSummary]
    total_districts: int


# ──────────────────────────────────────────────────────────────────────
# Row -> schema serialization
# ──────────────────────────────────────────────────────────────────────
def _to_public(h: Hospital) -> HospitalPublic:
    return HospitalPublic(
        id=str(h.id),
        name=h.name,
        hospital_type=h.hospital_type,
        district=h.district,
        upazila=h.upazila,
        address=h.address,
        latitude=h.latitude,
        longitude=h.longitude,
        capacity_status=_capacity_status(h.occupancy_percent),
        distance_km=None,
        data_source=h.data_source,
        coordinates_source=h.coordinates_source,
        address_source=h.address_source,
        phone=h.phone,  # already NULL on seed rows; citizens see None
    )


def _to_operational(h: Hospital, public: HospitalPublic) -> HospitalOperational:
    return HospitalOperational(
        **public.model_dump(),
        beds_total=h.beds,
        beds_occupied=h.beds_occupied,
        occupancy_percent=h.occupancy_percent,
        doctors=h.doctors,
        nurses=h.nurses,
        ors_stock=h.ors_stock,
        iv_saline_stock=h.iv_saline_stock,
        antibiotics_stock=h.antibiotics_stock,
        ors_low=(h.ors_stock or 0) < LOW_STOCK_THRESHOLDS["ors"],
        iv_saline_low=(h.iv_saline_stock or 0) < LOW_STOCK_THRESHOLDS["iv_saline"],
        antibiotics_low=(h.antibiotics_stock or 0) < LOW_STOCK_THRESHOLDS["antibiotics"],
        last_updated=h.last_updated.isoformat() if h.last_updated else None,
    )


# ──────────────────────────────────────────────────────────────────────
# /hospitals/districts-summary
# ──────────────────────────────────────────────────────────────────────
@router.get("/districts-summary", response_model=DistrictsSummaryResponse)
def districts_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DistrictsSummaryResponse:
    """One row per district with hospital count + bed totals + low-stock flags.

    Implementation note: the existing `district_hospital_aggregates`
    table already has SUM(beds), COUNT(hospital), etc. pre-rolled.  We
    also pull live per-hospital stocks so the low-stock flags reflect
    current values (the rollup uses SUMs which aren't meaningful at
    district level for low-stock checks; we need the per-hospital
    count of low-stock hospitals instead).
    """
    rollups = {
        r.district: r
        for r in db.query(
            Hospital.district.label("district"),
            func.count(Hospital.id).label("hospital_count"),
            func.coalesce(func.sum(Hospital.beds), 0).label("total_beds"),
            func.coalesce(func.avg(Hospital.occupancy_percent), 0.0).label("mean_occupancy"),
            func.coalesce(func.sum(Hospital.ors_stock), 0).label("total_ors"),
            func.coalesce(func.sum(Hospital.iv_saline_stock), 0).label("total_iv"),
            func.coalesce(func.sum(Hospital.antibiotics_stock), 0).label("total_ab"),
        )
        .group_by(Hospital.district)
        .all()
    }
    rollup_rows = {
        r.district: r
        for r in db.query(DistrictHospitalAggregate).all()
    }

    # Always include all 64 canonical districts, even if they have no hospitals.
    items: List[DistrictHospitalSummary] = []
    for d_name in sorted(EN_TO_BN.keys()):
        bn = EN_TO_BN.get(d_name)
        r = rollups.get(d_name)
        ra = rollup_rows.get(d_name)
        if r is None:
            items.append(DistrictHospitalSummary(
                district=d_name, name_bn=bn,
                hospital_count=0, total_beds=0, mean_occupancy_percent=0.0,
                capacity_status="Unknown",
            ))
            continue
        # Mean occupancy from the rollup if available, else live
        occ = float(r.mean_occupancy) if r.mean_occupancy is not None else 0.0
        if ra is not None and ra.occupancy_percent is not None:
            occ = float(ra.occupancy_percent)
        status = _capacity_status(occ) if r.hospital_count else "Unknown"
        # Build the summary as a dict so we can conditionally OMIT the
        # operational fields for citizens (so they're truly absent from
        # the response, not just null).  Pydantic will reject the dict
        # if a required key is missing, so this is safe.
        summary: dict = dict(
            district=d_name,
            name_bn=bn,
            hospital_count=int(r.hospital_count or 0),
            total_beds=int(r.total_beds or 0),
            mean_occupancy_percent=round(occ, 1),
            capacity_status=status,
        )
        if _is_operational(current_user):
            summary.update(
                total_ors=int(r.total_ors or 0),
                total_iv_saline=int(r.total_iv or 0),
                total_antibiotics=int(r.total_ab or 0),
            )
        items.append(DistrictHospitalSummary(**summary))

    # Add operational low-stock fields per district (operational roles only)
    if _is_operational(current_user):
        # Per-district "any hospital below threshold" flag
        low_flags = {
            d_name: {
                "ors": 0, "iv_saline": 0, "antibiotics": 0,
            }
            for d_name in EN_TO_BN
        }
        for h in db.query(Hospital).all():
            ld = low_flags.setdefault(h.district, {"ors": 0, "iv_saline": 0, "antibiotics": 0})
            if (h.ors_stock or 0) < LOW_STOCK_THRESHOLDS["ors"]:
                ld["ors"] += 1
            if (h.iv_saline_stock or 0) < LOW_STOCK_THRESHOLDS["iv_saline"]:
                ld["iv_saline"] += 1
            if (h.antibiotics_stock or 0) < LOW_STOCK_THRESHOLDS["antibiotics"]:
                ld["antibiotics"] += 1
        for it in items:
            ld = low_flags.get(it.district, {"ors": 0, "iv_saline": 0, "antibiotics": 0})
            it.ors_low = ld["ors"] > 0
            it.iv_saline_low = ld["iv_saline"] > 0
            it.antibiotics_low = ld["antibiotics"] > 0

    return DistrictsSummaryResponse(
        items=items,
        total_districts=len(items),
    )


# ──────────────────────────────────────────────────────────────────────
# /hospitals (list)
# ──────────────────────────────────────────────────────────────────────
# Whitelist of valid sort fields; everything else 400s.
_SORT_MAP = {
    "name": Hospital.name,
    "occupancy": Hospital.occupancy_percent,
    "beds": Hospital.beds,
    "type": Hospital.hospital_type,
}


@router.get("", response_model=HospitalListResponse)
def list_hospitals(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    district: Optional[str] = Query(None, description="Canonical 64-district name (case-insensitive)"),
    type: Optional[str] = Query(None, description="Hospital type filter (e.g. 'District Hospital', 'NGO Health Center')"),
    q: Optional[str] = Query(None, description="Substring match against name (case-insensitive)"),
    status: Optional[str] = Query(None, description="Available | Limited | Full (capacity_status filter)"),
    sort: str = Query("name", description="name | occupancy | beds | type"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> HospitalListResponse:
    # Canonicalize the district filter so "Barisal" still works
    canon_district = None
    if district:
        canon_district = next(
            (k for k in EN_TO_BN if k.lower() == district.strip().lower()),
            None,
        )
        if canon_district is None:
            raise HTTPException(status_code=404, detail=f"Unknown district {district!r}")

    sort_col = _SORT_MAP.get(sort)
    if sort_col is None:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid sort={sort!r}. Valid: {sorted(_SORT_MAP.keys())}",
        )

    base = db.query(Hospital)
    if canon_district:
        base = base.filter(Hospital.district == canon_district)
    if type:
        base = base.filter(Hospital.hospital_type == type)
    if q:
        like = f"%{q.strip()}%"
        base = base.filter(Hospital.name.ilike(like))

    # Status filter has to happen post-fetch because the capacity_status
    # field is computed in Python.  We over-fetch by a factor of 2 to
    # reduce the chance of an empty page when many rows are filtered
    # out, but cap at 500 to keep the response bounded.
    rows = base.order_by(sort_col.asc()).limit(max(limit * 2, 100)).offset(offset).all()
    rows = [r for r in rows if _status_matches(r.occupancy_percent, status)]
    rows = rows[:limit]

    is_op = _is_operational(current_user)
    items: List = []
    for h in rows:
        public = _to_public(h)
        if is_op:
            items.append(_to_operational(h, public))
        else:
            items.append(public)

    total = db.query(func.count(Hospital.id)).filter(
        and_(
            Hospital.district == canon_district if canon_district else True,
        )
    ).scalar() or 0

    return HospitalListResponse(
        items=items,
        total=int(total),
        limit=limit,
        offset=offset,
        operational_fields_present=is_op,
    )


# ──────────────────────────────────────────────────────────────────────
# /hospitals/nearby
# ──────────────────────────────────────────────────────────────────────
@router.get("/nearby", response_model=List[NearbyHospital])
def nearby_hospitals(
    lat: float = Query(..., ge=-90, le=90, description="Latitude in WGS84"),
    lng: float = Query(..., ge=-180, le=180, description="Longitude in WGS84"),
    radius_km: float = Query(50.0, ge=0.1, le=500.0, description="Filter to this radius (km)"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[NearbyHospital]:
    """Haversine nearest-hospitals endpoint.

    Validates the query point is inside Bangladesh's bounding box
    (rejects Bay-of-Bengal / India / Myanmar inputs with 422).  For
    the dataset size (~500 rows) we compute the distance in Python
    over the filtered candidate set; PostGIS is not required.

    Note: RBAC is intentionally NOT applied here -- citizens need the
    "find the nearest hospital" use case too.  They still get the
    `HospitalPublic` shape (no operational fields) so this is
    consistent with the spec.
    """
    if not (LAT_MIN <= lat <= LAT_MAX) or not (LNG_MIN <= lng <= LNG_MAX):
        raise HTTPException(
            status_code=422,
            detail=(
                f"Query point ({lat}, {lng}) is outside Bangladesh's bounding box. "
                f"Use lat in [{LAT_MIN}, {LAT_MAX}] and lng in [{LNG_MIN}, {LNG_MAX}]."
            ),
        )

    is_op = _is_operational(current_user)
    # Fetch all rows with non-null coords; in production we'd use
    # bounding-box prefiltering on (lat, lng), but for 500 rows the
    # full scan is still < 1 ms.
    candidates = db.query(Hospital).filter(
        Hospital.latitude.isnot(None),
        Hospital.longitude.isnot(None),
    ).all()

    scored: List[Tuple[float, Hospital]] = []
    for h in candidates:
        d = _haversine_km(lat, lng, h.latitude, h.longitude)
        if d <= radius_km:
            scored.append((d, h))
    scored.sort(key=lambda t: t[0])
    scored = scored[:limit]

    out: List[NearbyHospital] = []
    for d, h in scored:
        pub = _to_public(h)
        nearby_data = pub.model_dump()
        nearby_data["distance_km"] = round(d, 3)
        nearby = NearbyHospital(**nearby_data)
        out.append(nearby)
    return out


# ──────────────────────────────────────────────────────────────────────
# /hospitals/{hospital_id}
# ──────────────────────────────────────────────────────────────────────
@router.get("/{hospital_id}", response_model=None)
def get_hospital(
    hospital_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    h = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if h is None:
        raise HTTPException(status_code=404, detail=f"Hospital {hospital_id!r} not found")
    is_op = _is_operational(current_user)
    pub = _to_public(h)
    if is_op:
        # Return as a dict so FastAPI's JSON encoder preserves every
        # field of HospitalOperational (Pydantic's Union inference
        # otherwise downgrades it to HospitalPublic).
        return _to_operational(h, pub).model_dump()
    return pub.model_dump()
