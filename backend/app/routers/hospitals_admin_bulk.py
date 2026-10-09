"""
/admin/hospitals/issues/status -- BULK status mutation (admin only).

Distinct from PATCH /admin/hospitals/issues/{issue_id}/status which
is the single-row path used by the per-row "Ack / Resolve / Dismiss"
buttons on the inbox.  This endpoint is the "I picked 8 rows and
hit Acknowledge all" path -- it accepts a list of ids plus the
target status, and is idempotent: unknown ids come back in a
`not_found` array so the UI can show "12 acknowledged, 2 missing".

Limits
------
- 200 ids per call (the inbox caps its visible set at 100, so this
  leaves headroom for "select all on a paginated view" later).
- Only the three admin-writable statuses are accepted -- "open"
  stays reserved for fresh user reports.
- The endpoint returns the count actually written so a partial
  update is observable.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth_deps import get_current_user
from app.auth_models import User, UserRole
from app.database import get_db
from app.reference_models import HospitalIssueReport
from app.routers.hospitals_issues import ALLOWED_STATUSES

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin/hospitals",
    tags=["Admin Hospital Issue Inbox"],
    dependencies=[Depends(get_current_user)],
)

ADMIN_WRITABLE_STATUSES = {"ack", "resolved", "dismissed"}


# ─── Schemas ────────────────────────────────────────────────────────

class BulkStatusUpdate(BaseModel):
    issue_ids: List[str] = Field(..., min_length=1, max_length=200)
    status: str = Field(..., description="One of: ack | resolved | dismissed")


class BulkStatusResponse(BaseModel):
    requested: int
    updated: int
    not_found: List[str]
    status: str
    updated_at: str


def _require_admin(user: User) -> None:
    if user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Admin role required")


@router.post(
    "/issues/status",
    response_model=BulkStatusResponse,
    summary="Bulk set status on many issues (admin)",
)
def bulk_status_update(
    payload: BulkStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BulkStatusResponse:
    _require_admin(current_user)
    if payload.status not in ADMIN_WRITABLE_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"status must be one of: {sorted(ADMIN_WRITABLE_STATUSES)}",
        )

    # Parse + dedupe ids.
    raw_ids = list({i.strip() for i in payload.issue_ids if i and i.strip()})
    if not raw_ids:
        raise HTTPException(status_code=422, detail="issue_ids must not be empty")
    valid_ids: List[UUID] = []
    not_found: List[str] = []
    for raw in raw_ids:
        try:
            valid_ids.append(UUID(raw))
        except ValueError:
            not_found.append(raw)

    # Find which UUIDs actually exist.
    existing = (
        db.query(HospitalIssueReport.id)
        .filter(HospitalIssueReport.id.in_(valid_ids))
        .all()
    )
    existing_set = {row[0] for row in existing}
    for vid in valid_ids:
        if vid not in existing_set:
            not_found.append(str(vid))

    if existing_set:
        # Walk each row to stamp the audit columns.  We deliberately
        # don't do a single .update({}) here because the *_at stamps
        # need to be "first time entered this status" semantics and
        # a bulk .update would clobber the per-row history.
        from datetime import datetime as _dt_now, timezone as _tz
        now = _dt_now.now(_tz.utc)
        rows = (
            db.query(HospitalIssueReport)
            .filter(HospitalIssueReport.id.in_(existing_set))
            .all()
        )
        stamp_col_at: dict[str, str] = {
            "ack": "ack_at", "resolved": "resolved_at", "dismissed": "dismissed_at",
        }
        stamp_col_by: dict[str, str] = {
            "ack": "ack_by", "resolved": "resolved_by", "dismissed": "dismissed_by",
        }
        col_at = stamp_col_at.get(payload.status)
        col_by = stamp_col_by.get(payload.status)
        for r in rows:
            r.status = payload.status
            if col_at and getattr(r, col_at) is None:
                setattr(r, col_at, now)
            if col_by:
                setattr(r, col_by, current_user.id)
        db.commit()

    logger.info(
        "admin %s bulk-updated %d issues -> %s (not_found=%d)",
        current_user.email, len(existing_set), payload.status, len(not_found),
    )

    return BulkStatusResponse(
        requested=len(raw_ids),
        updated=len(existing_set),
        not_found=not_found,
        status=payload.status,
        updated_at=datetime.now(timezone.utc).isoformat(),
    )
