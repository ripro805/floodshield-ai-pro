"""
/admin/hospitals/issues -- the admin "issue inbox".

Distinct from the per-hospital GET /hospitals/{id}/issues that
shows the recent-reports panel on the directory's detail modal.
This endpoint is admin-only and exposes the full inbox with
filtering, a status-summary rollup, and an ack/resolve/dismiss
mutation.

RBAC
----
All endpoints require `UserRole.admin`.  The user can flip a
single issue's status to one of:
  - ack       (seen, in progress)
  - resolved  (data was fixed -- the operator should then PATCH
               the hospital to update phone/address/etc., so the
               rollup reflects the change)
  - dismissed (not actionable)
Open is the default; admins should never have to set it back to
"open" because the only path to "open" is a fresh report.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, case

from app.auth_deps import get_current_user
from app.auth_models import User, UserRole
from app.database import get_db
from app.reference_models import Hospital, HospitalIssueReport

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin/hospitals",
    tags=["Admin Hospital Issue Inbox"],
    dependencies=[Depends(get_current_user)],
)

# Re-use the same fixed vocabulary the per-hospital endpoint
# enforces.  Importing it keeps the two surfaces in lockstep.
from app.routers.hospitals_issues import ALLOWED_CATEGORIES, ALLOWED_STATUSES

# Statuses a user is allowed to *write* via PATCH.  "open" is
# excluded because the only way to get an "open" issue is a fresh
# report.
ADMIN_WRITABLE_STATUSES = {"ack", "resolved", "dismissed"}


# ─── Schemas ────────────────────────────────────────────────────────

class IssueRow(BaseModel):
    id: str
    hospital_id: str
    hospital_name: str
    district: Optional[str] = None
    category: str
    description: str
    status: str
    reporter_role: Optional[str] = None
    reporter_email: Optional[str] = None
    created_at: str


class IssueListResponse(BaseModel):
    items: List[IssueRow]
    total: int
    limit: int
    offset: int


class IssueStatusUpdate(BaseModel):
    status: str = Field(..., description="One of: ack | resolved | dismissed")


class IssueStatusResponse(BaseModel):
    id: str
    status: str
    updated_at: str


class StatusBucket(BaseModel):
    status: str
    count: int


class DistrictBucket(BaseModel):
    district: str
    count: int
    open: int
    resolved: int
    dismissed: int


class InboxSummary(BaseModel):
    total: int
    by_status: List[StatusBucket]
    by_district: List[DistrictBucket]
    by_category: List[StatusBucket]


# ─── Helpers ────────────────────────────────────────────────────────

def _require_admin(user: User) -> None:
    if user.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )


def _row_to_dict(r: HospitalIssueReport, h: Hospital | None,
                 reporter: User | None) -> IssueRow:
    return IssueRow(
        id=str(r.id),
        hospital_id=str(r.hospital_id),
        hospital_name=h.name if h else "(deleted hospital)",
        district=h.district if h else None,
        category=r.category,
        description=r.description,
        status=r.status,
        reporter_role=r.reporter_role,
        reporter_email=reporter.email if reporter else None,
        created_at=r.created_at.isoformat() if r.created_at else "",
    )


def _join_hospital(db: Session, r: HospitalIssueReport) -> tuple[Hospital | None, User | None]:
    h = db.query(Hospital).filter(Hospital.id == r.hospital_id).first()
    reporter = db.query(User).filter(User.id == r.reporter_id).first() if r.reporter_id else None
    return h, reporter


# ─── Endpoints ──────────────────────────────────────────────────────

@router.get(
    "/issues",
    response_model=IssueListResponse,
    summary="List every hospital issue report (admin inbox)",
)
def list_issues(
    district: Optional[str] = Query(None, description="Filter by hospital district"),
    status_filter: Optional[str] = Query(None, alias="status", description="One of: open | ack | resolved | dismissed"),
    category: Optional[str] = Query(None, description="One of the fixed category vocabulary"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IssueListResponse:
    _require_admin(current_user)

    if status_filter and status_filter not in ALLOWED_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"status must be one of: {sorted(ALLOWED_STATUSES)}",
        )
    if category and category not in ALLOWED_CATEGORIES:
        raise HTTPException(
            status_code=422,
            detail=f"category must be one of: {sorted(ALLOWED_CATEGORIES)}",
        )

    q = db.query(HospitalIssueReport)
    if status_filter:
        q = q.filter(HospitalIssueReport.status == status_filter)
    if category:
        q = q.filter(HospitalIssueReport.category == category)
    if district:
        # Join to Hospital for the district filter.
        q = q.join(Hospital, Hospital.id == HospitalIssueReport.hospital_id).filter(
            Hospital.district == district
        )
    total = q.count()
    rows = q.order_by(desc(HospitalIssueReport.created_at)).limit(limit).offset(offset).all()

    items: List[IssueRow] = []
    if not rows:
        return IssueListResponse(items=[], total=total, limit=limit, offset=offset)
    # Batch-fetch hospitals + reporters in two queries instead of 2*limit
    # (the previous per-row pattern took 24s for a district-filtered list
    # of 50 rows because each row triggered two extra round-trips).
    hospital_ids = {r.hospital_id for r in rows if r.hospital_id}
    reporter_ids = {r.reporter_id for r in rows if r.reporter_id}
    hospitals = (
        {h.id: h for h in db.query(Hospital).filter(Hospital.id.in_(hospital_ids)).all()}
        if hospital_ids else {}
    )
    reporters = (
        {u.id: u for u in db.query(User).filter(User.id.in_(reporter_ids)).all()}
        if reporter_ids else {}
    )
    for r in rows:
        h = hospitals.get(r.hospital_id)
        reporter = reporters.get(r.reporter_id) if r.reporter_id else None
        items.append(_row_to_dict(r, h, reporter))

    return IssueListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/issues/summary",
    response_model=InboxSummary,
    summary="Inbox counts by status, district, and category",
)
def inbox_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InboxSummary:
    _require_admin(current_user)

    # Total + by-status
    by_status_rows = (
        db.query(HospitalIssueReport.status, func.count(HospitalIssueReport.id))
        .group_by(HospitalIssueReport.status)
        .all()
    )
    by_status = [StatusBucket(status=s, count=int(c)) for s, c in by_status_rows]
    total = sum(b.count for b in by_status)

    # By category
    by_cat_rows = (
        db.query(HospitalIssueReport.category, func.count(HospitalIssueReport.id))
        .group_by(HospitalIssueReport.category)
        .all()
    )
    by_category = [StatusBucket(status=c, count=int(n)) for c, n in by_cat_rows]

    # By district (joined)
    by_dist_rows = (
        db.query(
            Hospital.district,
            func.count(HospitalIssueReport.id),
            func.sum(case((HospitalIssueReport.status == "open", 1), else_=0)),
            func.sum(case((HospitalIssueReport.status == "resolved", 1), else_=0)),
            func.sum(case((HospitalIssueReport.status == "dismissed", 1), else_=0)),
        )
        .join(Hospital, Hospital.id == HospitalIssueReport.hospital_id)
        .group_by(Hospital.district)
        .order_by(desc(func.count(HospitalIssueReport.id)))
        .all()
    )
    by_district = [
        DistrictBucket(
            district=d or "(unknown)",
            count=int(c),
            open=int(o or 0),
            resolved=int(r or 0),
            dismissed=int(di or 0),
        )
        for d, c, o, r, di in by_dist_rows
    ]
    return InboxSummary(
        total=total,
        by_status=by_status,
        by_district=by_district,
        by_category=by_category,
    )



def _stamp_status_audit(row: HospitalIssueReport, new_status: str, actor_id) -> None:
    """Stamp the *_at / *_by audit columns and update row.status.

    The {verb}_at column is set whenever the row ENTERS that status.
    If the row was already in `new_status` we leave the original
    timestamp alone -- this preserves the "first time it was acked"
    semantics and keeps the timeline monotonic.
    """
    from datetime import datetime, timezone as _tz
    now = datetime.now(_tz.utc)
    row.status = new_status
    if new_status == "ack" and row.ack_at is None:
        row.ack_at = now
        row.ack_by = actor_id
    elif new_status == "resolved" and row.resolved_at is None:
        row.resolved_at = now
        row.resolved_by = actor_id
    elif new_status == "dismissed" and row.dismissed_at is None:
        row.dismissed_at = now
        row.dismissed_by = actor_id

@router.patch(
    "/issues/{issue_id}/status",
    response_model=IssueStatusResponse,
    summary="Acknowledge, resolve, or dismiss a single issue (admin)",
)
def update_issue_status(
    issue_id: str,
    payload: IssueStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IssueStatusResponse:
    _require_admin(current_user)
    if payload.status not in ADMIN_WRITABLE_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"status must be one of: {sorted(ADMIN_WRITABLE_STATUSES)}",
        )
    try:
        iid = UUID(issue_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid issue_id format")
    row = db.query(HospitalIssueReport).filter(HospitalIssueReport.id == iid).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Issue not found")
    _stamp_status_audit(row, payload.status, current_user.id)
    db.commit()
    db.refresh(row)
    logger.info(
        "admin %s set issue %s -> %s",
        current_user.email, iid, payload.status,
    )
    return IssueStatusResponse(
        id=str(row.id),
        status=row.status,
        updated_at=datetime.now(timezone.utc).isoformat(),
    )
