"""
/hospitals -- Operational hospital-inventory endpoints (health_worker,
hospital, ngo, government, admin).

The /recommend endpoint reads `district_hospital_aggregates`, but until
this router was added there was no path for an operational user to push
a *fresh* stock reading into the table when a new shipment arrives or
beds are emptied.  This endpoint updates BOTH:

  - the per-hospital `hospitals` row (raw inventory for the facility)
  - the per-district `district_hospital_aggregates` rollup
    (so the next /recommend call sees the change)

recomputed in the same transaction so the dashboard never sees a
half-updated state.

Every PATCH also writes a row to `hospital_updates` (Gap A audit trail)
and stamps `last_edited_by_id` / `last_edited_at` on the Hospital row
itself, so the UI card footer can show "last edited by X 3 minutes ago"
without a join.

GET  /hospitals                    -- list (filter by district)
GET  /hospitals/{hospital_id}      -- single hospital
GET  /hospitals/{hospital_id}/history  -- audit log (admin/operational)
PATCH /hospitals/{hospital_id}     -- update one or more inventory fields
"""
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.auth_deps import require_roles, get_current_user
from app.auth_models import User, UserRole
from app.reference_models import Hospital, DistrictHospitalAggregate, HospitalUpdate

router = APIRouter(prefix="/hospitals", tags=["Hospitals"])

OPERATIONAL_ROLES = (
    UserRole.health_worker, UserRole.hospital, UserRole.ngo,
    UserRole.government, UserRole.admin,
)


def _editor_to_dict(editor: Optional[User]) -> Optional[dict]:
    if editor is None:
        return None
    return {
        "id": str(editor.id),
        "email": editor.email,
        "full_name": editor.full_name,
        "role": editor.role.value,
    }


def _hospital_to_dict(h: Hospital) -> dict:
    return {
        "id": str(h.id),
        "name": h.name,
        "district": h.district,
        "district_id": str(h.district_id) if h.district_id else None,
        "hospital_type": h.hospital_type,
        "upazila": h.upazila,
        "address": h.address,
        "phone": h.phone,
        "beds": h.beds,
        "beds_occupied": h.beds_occupied,
        "doctors": h.doctors,
        "nurses": h.nurses,
        "ors_stock": h.ors_stock,
        "iv_saline_stock": h.iv_saline_stock,
        "antibiotics_stock": h.antibiotics_stock,
        "occupancy_percent": h.occupancy_percent,
        "latitude": h.latitude,
        "longitude": h.longitude,
        "data_source": h.data_source,
        "coordinates_source": h.coordinates_source,
        "address_source": h.address_source,
        # Capacity status is derived in the directory router from
        # the per-row occupancy + beds; for the PATCH / hospitals
        # endpoint we surface a simple "Unknown" stub so the frontend
        # gets a stable shape.  The Directory's GET uses the richer
        # capacity_status from the Pydantic schema.
        "capacity_status": None,
        "last_updated": h.last_updated.isoformat() if h.last_updated else None,
        "created_at": h.created_at.isoformat() if h.created_at else None,
        "last_edited_at": h.last_edited_at.isoformat() if h.last_edited_at else None,
        "last_edited_by_id": str(h.last_edited_by_id) if h.last_edited_by_id else None,
    }


@router.get("", response_model=List[dict])
def list_hospitals(
    district: Optional[str] = Query(None, description="Filter by district name"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List hospitals, optionally filtered to a single district.

    Open to all authenticated users so the public dashboard can show
    "where is the nearest facility" without an admin role.
    """
    q = db.query(Hospital)
    if district:
        q = q.filter(Hospital.district.ilike(f"%{district}%"))
    rows = q.order_by(Hospital.district.asc(), Hospital.name.asc()).limit(limit).all()
    return [_hospital_to_dict(r) for r in rows]


@router.get("/{hospital_id}", response_model=dict)
def get_hospital(hospital_id: str, db: Session = Depends(get_db)):
    try:
        hid = UUID(hospital_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid hospital_id format")
    row = db.query(Hospital).filter(Hospital.id == hid).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Hospital not found")
    return _hospital_to_dict(row)


# Fields a hospital staff member is allowed to update in-place.  Static
# metadata (name, lat/long, hospital_type) is intentionally NOT included --
# those changes should be a deliberate admin action, not a side effect of
# an inventory edit.
UPDATABLE_INVENTORY_FIELDS = {
    "beds",
    "doctors",
    "nurses",
    "ors_stock",
    "iv_saline_stock",
    "antibiotics_stock",
    "occupancy_percent",
}

# Fields hospital staff (health_worker / hospital / ngo / government)
# may update in addition to inventory.  These are the
# "fix-the-record" fields: a typo in the phone number, a corrected
# upazila, the real bed count for tonight.  The static metadata --
# name, type, coordinates, district -- is admin-only because changing
# it is a structural decision, not an operational one.
UPDATABLE_OPS_METADATA_FIELDS = {
    "phone",
    "address",
    "upazila",
    "beds_occupied",
}

# Admin-only "fix the record" fields.  Changing the name or moving
# the pin are deliberate structural changes that we want to log
# clearly and never do by accident from an inventory edit.
UPDATABLE_ADMIN_METADATA_FIELDS = {
    "name",
    "hospital_type",
    "latitude",
    "longitude",
}


class HospitalInventoryPatch(BaseModel):
    """PATCH payload for hospital inventory + metadata fields.

    Every field is optional; the request only updates the fields the
    caller explicitly sends.  Numeric fields are validated >= 0.

    Field groups (enforced server-side based on caller role):
      - inventory: any operational role
      - ops metadata (phone, address, upazila, beds_occupied):
        any operational role
      - admin metadata (name, hospital_type, lat, lng): admin only

    A 422 is returned if the payload contains a field the caller's
    role is not allowed to write -- we never silently drop a field
    a user thought they sent.
    """
    # Inventory (existing)
    beds: Optional[int] = Field(None, ge=0)
    doctors: Optional[int] = Field(None, ge=0)
    nurses: Optional[int] = Field(None, ge=0)
    ors_stock: Optional[int] = Field(None, ge=0)
    iv_saline_stock: Optional[int] = Field(None, ge=0)
    antibiotics_stock: Optional[int] = Field(None, ge=0)
    occupancy_percent: Optional[float] = Field(None, ge=0, le=100)

    # Ops metadata (phone / address / upazila / live bed count)
    phone: Optional[str] = Field(
        None,
        max_length=40,
        description="Contact phone.  Empty string clears the field.",
    )
    address: Optional[str] = Field(None, max_length=500)
    upazila: Optional[str] = Field(None, max_length=120)
    beds_occupied: Optional[int] = Field(
        None,
        ge=0,
        description=(
            "Live count of patients currently in beds.  If set, the "
            "rollup uses this for occupancy instead of the static "
            "occupancy_percent field."
        ),
    )

    # Admin metadata
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    hospital_type: Optional[str] = Field(None, max_length=80)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)


@router.patch(
    "/{hospital_id}",
    response_model=dict,
    dependencies=[Depends(require_roles(*OPERATIONAL_ROLES))],
    summary="Update hospital inventory and refresh district rollup",
)
def update_hospital_inventory(
    hospital_id: str,
    payload: HospitalInventoryPatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update one or more inventory fields on a hospital facility and
    recompute the district rollup so /recommend sees the new numbers.

    Restricted to operational roles.  Hospital and health_worker users
    can update any hospital in their own district; admin / government
    can update any hospital.  A user with role=citizen hits 403 before
    even reaching this handler.

    Side effects: writes a `hospital_updates` audit row and stamps
    `last_edited_at` + `last_edited_by_id` on the hospital row.
    """
    try:
        hid = UUID(hospital_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid hospital_id format")

    hospital = db.query(Hospital).filter(Hospital.id == hid).first()
    if hospital is None:
        raise HTTPException(status_code=404, detail="Hospital not found")

    # Enforce per-district write for non-admin operational roles.  An
    # admin / government operator can update any district.
    if current_user.role not in (UserRole.admin, UserRole.government):
        if current_user.district and current_user.district.strip().lower() != hospital.district.strip().lower():
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Your account is registered to district '{current_user.district}'; "
                    f"you can only update hospitals in your own district."
                ),
            )

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail="Provide at least one field to update.")

    # Field-level role guard.  A field a caller isn't allowed to write
    # is a 422 (not a silent drop) so the UI can surface the error.
    admin_only = UPDATABLE_ADMIN_METADATA_FIELDS
    ops_ok = UPDATABLE_OPS_METADATA_FIELDS | UPDATABLE_INVENTORY_FIELDS
    is_admin = current_user.role == UserRole.admin
    for field_name in updates:
        if field_name in admin_only and not is_admin:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Field '{field_name}' is admin-only; your role "
                    f"({current_user.role.value}) cannot change it."
                ),
            )
        if field_name not in ops_ok and field_name not in admin_only:
            raise HTTPException(
                status_code=422,
                detail=f"Field '{field_name}' is not editable through this endpoint.",
            )

    # Capture *only the actually-changed* fields for the audit log so the
    # log is small and useful.
    changes: dict = {}
    for field_name, value in updates.items():
        old = getattr(hospital, field_name)
        if old != value:
            changes[field_name] = {"from": old, "to": value}
        setattr(hospital, field_name, value)

    # First operator edit on a seed row stamps the address_source /
    # coordinates_source as 'manual_update' (if it was a synthetic
    # 'synthetic_seed') so the UI's "Sample data" badge disappears
    # for fields a human has touched.
    if "address" in changes and hospital.address_source == "synthetic_seed":
        hospital.address_source = "manual_update"
    if ("latitude" in changes or "longitude" in changes) and hospital.coordinates_source == "synthetic_seed":
        hospital.coordinates_source = "manual_update"

    # An admin structural edit (name, hospital_type, lat, lng) flips
    # the data_source from 'seed' to 'manual_update' so the entire row
    # stops showing the "Sample data" badge.  We never downgrade
    # 'admin_import' or 'manual_update'.
    if is_admin and admin_only.intersection(changes) and hospital.data_source in ("seed", None, ""):
        hospital.data_source = "manual_update"

    if not changes:
        # PATCH with only no-op changes -- still record the call (or
        # 422?).  We return 200 with the existing state so the UI gets
        # a clean round-trip.
        return {
            "hospital": _hospital_to_dict(hospital),
            "district_aggregate": None,
            "audit_id": None,
            "changed_fields": [],
        }

    # Recompute the per-district rollup in the same transaction so the
    # /recommend endpoint sees the new numbers immediately.
    agg = (
        db.query(DistrictHospitalAggregate)
        .filter(DistrictHospitalAggregate.district == hospital.district)
        .first()
    )
    if agg is None:
        agg = DistrictHospitalAggregate(district=hospital.district)
        db.add(agg)

    counts = (
        db.query(
            func.coalesce(func.sum(Hospital.beds), 0),
            func.coalesce(func.sum(Hospital.doctors), 0),
            func.coalesce(func.sum(Hospital.nurses), 0),
            func.coalesce(func.sum(Hospital.ors_stock), 0),
            func.coalesce(func.sum(Hospital.iv_saline_stock), 0),
            func.coalesce(func.sum(Hospital.antibiotics_stock), 0),
            func.coalesce(func.avg(Hospital.occupancy_percent), 0.0),
            func.count(Hospital.id),
        )
        .filter(Hospital.district == hospital.district)
        .first()
    )
    agg.beds, agg.doctors, agg.nurses = int(counts[0]), int(counts[1]), int(counts[2])
    agg.ors_stock, agg.iv_saline_stock, agg.antibiotics_stock = int(counts[3]), int(counts[4]), int(counts[5])
    # Weighted-mean occupancy that prefers the live beds_occupied when
    # a hospital has reported one, otherwise falls back to the
    # static occupancy_percent.  This lets an ops user set
    # beds_occupied=120 on a 200-bed hospital and have the rollup
    # reflect the live situation immediately, while the per-row
    # occupancy_percent stays as the static seed value.
    live_rows = (
        db.query(
            Hospital.beds,
            Hospital.beds_occupied,
            Hospital.occupancy_percent,
        )
        .filter(Hospital.district == hospital.district)
        .all()
    )
    weighted_num = 0.0
    weighted_den = 0.0
    fallback_num = 0.0
    fallback_count = 0
    for beds, occupied, occ_pct in live_rows:
        if beds is None or beds <= 0:
            continue
        if occupied is not None:
            weighted_num += float(occupied)
            weighted_den += float(beds)
        else:
            fallback_num += float(occ_pct or 0.0)
            fallback_count += 1
    if weighted_den > 0:
        agg.occupancy_percent = round(100.0 * weighted_num / weighted_den, 2)
    elif fallback_count > 0:
        agg.occupancy_percent = round(fallback_num / fallback_count, 2)
    else:
        agg.occupancy_percent = float(counts[6])
    agg.hospital_count = int(counts[7])

    # Audit trail
    now = datetime.now(timezone.utc)
    hospital.last_edited_at = now
    hospital.last_edited_by_id = current_user.id

    audit_row = HospitalUpdate(
        hospital_id=hospital.id,
        editor_id=current_user.id,
        changes=changes,
        district_aggregate={
            "beds": agg.beds,
            "doctors": agg.doctors,
            "nurses": agg.nurses,
            "ors_stock": agg.ors_stock,
            "iv_saline_stock": agg.iv_saline_stock,
            "antibiotics_stock": agg.antibiotics_stock,
            "occupancy_percent": round(float(agg.occupancy_percent), 2),
            "hospital_count": agg.hospital_count,
        },
    )
    db.add(audit_row)
    db.commit()
    db.refresh(hospital)
    db.refresh(agg)
    db.refresh(audit_row)

    return {
        "hospital": _hospital_to_dict(hospital),
        "district_aggregate": {
            "district": agg.district,
            "beds": agg.beds,
            "doctors": agg.doctors,
            "nurses": agg.nurses,
            "ors_stock": agg.ors_stock,
            "iv_saline_stock": agg.iv_saline_stock,
            "antibiotics_stock": agg.antibiotics_stock,
            "occupancy_percent": round(float(agg.occupancy_percent), 2),
            "hospital_count": agg.hospital_count,
        },
        "audit_id": str(audit_row.id),
        "changed_fields": list(changes.keys()),
    }


@router.get(
    "/{hospital_id}/history",
    response_model=dict,
    summary="Audit log of inventory edits to a hospital",
)
def get_hospital_history(
    hospital_id: str,
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the most recent PATCH events for one hospital.

    Open to any authenticated user (the data is non-sensitive: it just
    says "at <time>, <editor_email> changed ors_stock from 50 to 200"),
    so the operational UI can show "last edited by X" without a
    special role.  Admin audit consumers can query the full table via
    /admin endpoints (future).
    """
    try:
        hid = UUID(hospital_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid hospital_id format")
    hospital = db.query(Hospital).filter(Hospital.id == hid).first()
    if hospital is None:
        raise HTTPException(status_code=404, detail="Hospital not found")

    rows = (
        db.query(HospitalUpdate)
        .filter(HospitalUpdate.hospital_id == hid)
        .order_by(HospitalUpdate.created_at.desc())
        .limit(limit)
        .all()
    )

    # Bulk-load editors
    editor_ids = {r.editor_id for r in rows if r.editor_id is not None}
    editors: dict = {}
    if editor_ids:
        for u in db.query(User).filter(User.id.in_(editor_ids)).all():
            editors[u.id] = u

    return {
        "hospital_id": str(hospital.id),
        "hospital_name": hospital.name,
        "last_edited_at": hospital.last_edited_at.isoformat() if hospital.last_edited_at else None,
        "last_edited_by": _editor_to_dict(editors.get(hospital.last_edited_by_id)) if hospital.last_edited_by_id else None,
        "count": len(rows),
        "items": [
            {
                "id": str(r.id),
                "editor": _editor_to_dict(editors.get(r.editor_id)) if r.editor_id else None,
                "changes": r.changes,
                "district_aggregate": r.district_aggregate,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }
