"""
/hospitals/districts/{district}/issue-rollup -- the read-only
"open vs. resolved" rollup shown on the District Detail page.

Any signed-in user (incl. citizen) can read this.  We only expose
counts (no description text) so privacy stays tight.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, case

from app.auth_deps import get_current_user
from app.auth_models import User
from app.database import get_db
from app.reference_models import Hospital, HospitalIssueReport

router = APIRouter(
    prefix="/hospitals/districts",
    tags=["Hospital Issue Rollup"],
    dependencies=[Depends(get_current_user)],
)


class CategoryBucket(BaseModel):
    category: str
    count: int


class IssueRollup(BaseModel):
    district: str
    total: int
    open: int
    ack: int
    resolved: int
    dismissed: int
    last_filed_at: str | None
    top_categories: list[CategoryBucket]


@router.get(
    "/{district}/issue-rollup",
    response_model=IssueRollup,
    summary="Read-only per-district hospital issue rollup",
)
def issue_rollup(
    district: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IssueRollup:
    """Counts of every open / ack / resolved / dismissed report filed
    against any hospital in this district, plus the top categories."""
    # The District Detail page already passes the canonical name from
    # the URL; we do a case-insensitive match so a sloppy typed name
    # still hits the right rows.
    canon = district.strip()
    # Try to find a single canonical district whose name matches case-insensitively
    from app.models_loader import models  # not used; just keeps the import warm
    from app.reference_models import District
    if not canon:
        raise HTTPException(status_code=422, detail="Empty district")
    # Direct case-insensitive lookup first; fall back to the raw string.
    dist_row = (
        db.query(District)
        .filter(func.lower(District.name) == func.lower(canon))
        .first()
    )
    if dist_row is not None:
        canon = dist_row.name
    # Single round-trip count grouped by status.
    rows = (
        db.query(HospitalIssueReport.status, func.count(HospitalIssueReport.id))
        .join(Hospital, Hospital.id == HospitalIssueReport.hospital_id)
        .filter(Hospital.district == canon)
        .group_by(HospitalIssueReport.status)
        .all()
    )
    counts = {"open": 0, "ack": 0, "resolved": 0, "dismissed": 0}
    for s, n in rows:
        counts[s] = int(n)
    total = sum(counts.values())

    # Last filed timestamp
    last = (
        db.query(func.max(HospitalIssueReport.created_at))
        .join(Hospital, Hospital.id == HospitalIssueReport.hospital_id)
        .filter(Hospital.district == canon)
        .scalar()
    )
    # Top 3 categories (only open + ack -- the actionable set)
    cat_rows = (
        db.query(
            HospitalIssueReport.category,
            func.count(HospitalIssueReport.id),
        )
        .join(Hospital, Hospital.id == HospitalIssueReport.hospital_id)
        .filter(
            Hospital.district == canon,
            HospitalIssueReport.status.in_(("open", "ack")),
        )
        .group_by(HospitalIssueReport.category)
        .order_by(func.count(HospitalIssueReport.id).desc())
        .limit(3)
        .all()
    )
    return IssueRollup(
        district=canon,
        total=total,
        open=counts["open"],
        ack=counts["ack"],
        resolved=counts["resolved"],
        dismissed=counts["dismissed"],
        last_filed_at=last.isoformat() if last else None,
        top_categories=[CategoryBucket(category=c, count=int(n)) for c, n in cat_rows],
    )
