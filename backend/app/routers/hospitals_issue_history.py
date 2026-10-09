"""
/hospitals/{hospital_id}/issue-history -- the unified timeline used
by the per-hospital detail modal.

Distinct from GET /hospitals/{id}/issues (which is a flat list of
reports) -- the history view merges (a) every report event and
(b) every status transition into a single chronological stream,
so an operator can read "reported by X at T, acked by Y at T+2h,
resolved by Z at T+5h" without joining tables client-side.

Read-only, any authenticated user.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth_deps import get_current_user
from app.auth_models import User
from app.database import get_db
from app.reference_models import Hospital, HospitalIssueReport

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/hospitals",
    tags=["Hospital Issue History"],
    dependencies=[Depends(get_current_user)],
)


EventKind = Literal[
    "reported",
    "ack",
    "resolved",
    "dismissed",
]


class HistoryEvent(BaseModel):
    """A single point in the timeline.

    `kind` says what happened; `at` is the wall-clock time.  The
    reporter / actor fields are best-effort: a deleted user leaves
    a NULL actor_id but the role / email may still be on the report.
    """
    issue_id: str
    kind: EventKind
    at: str
    actor_role: Optional[str] = None
    actor_email: Optional[str] = None
    category: str
    description: str
    status: str


class IssueHistoryResponse(BaseModel):
    hospital_id: str
    hospital_name: str
    district: Optional[str] = None
    total: int
    events: List[HistoryEvent]


def _iso(dt) -> str:
    if dt is None:
        return ""
    if isinstance(dt, datetime):
        return dt.isoformat()
    return str(dt)


def _build_events(row: HospitalIssueReport) -> List[HistoryEvent]:
    """One row -> up to four events (reported, ack, resolved,
    dismissed).  We only emit events whose timestamp is non-null.
    """
    out: List[HistoryEvent] = []
    out.append(HistoryEvent(
        issue_id=str(row.id),
        kind="reported",
        at=_iso(row.created_at),
        actor_role=row.reporter_role,
        actor_email=None,
        category=row.category,
        description=row.description,
        status=row.status,
    ))
    if row.ack_at is not None:
        out.append(HistoryEvent(
            issue_id=str(row.id),
            kind="ack",
            at=_iso(row.ack_at),
            actor_role=None,
            actor_email=None,
            category=row.category,
            description="",
            status=row.status,
        ))
    if row.resolved_at is not None:
        out.append(HistoryEvent(
            issue_id=str(row.id),
            kind="resolved",
            at=_iso(row.resolved_at),
            actor_role=None,
            actor_email=None,
            category=row.category,
            description="",
            status=row.status,
        ))
    if row.dismissed_at is not None:
        out.append(HistoryEvent(
            issue_id=str(row.id),
            kind="dismissed",
            at=_iso(row.dismissed_at),
            actor_role=None,
            actor_email=None,
            category=row.category,
            description="",
            status=row.status,
        ))
    return out


@router.get(
    "/{hospital_id}/issue-history",
    response_model=IssueHistoryResponse,
    summary="Per-hospital chronological issue timeline (read-only)",
)
def issue_history(
    hospital_id: str,
    limit: int = 200,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IssueHistoryResponse:
    try:
        hid = UUID(hospital_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid hospital_id format")

    h = db.query(Hospital).filter(Hospital.id == hid).first()
    if h is None:
        raise HTTPException(status_code=404, detail="Hospital not found")

    rows = (
        db.query(HospitalIssueReport)
        .filter(HospitalIssueReport.hospital_id == hid)
        .order_by(HospitalIssueReport.created_at.desc())
        .limit(min(max(limit, 1), 500))
        .all()
    )

    events: List[HistoryEvent] = []
    for r in rows:
        events.extend(_build_events(r))

    # Newest first across the merged stream.
    events.sort(key=lambda e: e.at, reverse=True)

    return IssueHistoryResponse(
        hospital_id=str(hid),
        hospital_name=h.name,
        district=h.district,
        total=len(rows),
        events=events,
    )
