"""
/hospitals/{id}/issues -- per-hospital issue-report inbox.

Distinct from the chatbot's free-text `/chatbot/report-incident`
(which is the community-report stream) and the admin CSV import.
This is a structured, per-hospital inbox for "the phone number is
wrong", "this facility is closed", "the doctor is not available",
etc.  Both citizens and operational users can submit; admins
read/reply in a future admin UI.

Why a dedicated table:
  - A hospital has many issues; a community report is a one-off
    incident.  Keeping them in one table would force every query
    to filter on `hospital_id IS NOT NULL`.
  - Admins need to query "all open issues for Feni District
    Hospital" in one shot -- that needs an index on (hospital_id,
    status).

The endpoint is open to any authenticated user.  We don't want
citizens to need a special role to flag a wrong phone number.
"""
from __future__ import annotations

import logging
from typing import Optional, List
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.auth_deps import get_current_user
from app.auth_models import User
from app.database import get_db
from app.reference_models import Hospital, HospitalIssueReport

logger = logging.getLogger(__name__)

# Fixed vocabulary so admins can filter the inbox without parsing
# free text.  Keep this list small and explicit -- every option is
# a real, distinct action an admin would take.
ALLOWED_CATEGORIES = {
    "phone_wrong",
    "address_wrong",
    "name_wrong",
    "closed",
    "no_doctor",
    "no_stock",
    "coordinates_wrong",
    "other",
}

ALLOWED_STATUSES = {"open", "ack", "resolved", "dismissed"}

router = APIRouter(
    prefix="/hospitals",
    tags=["Hospital Issue Reports"],
    dependencies=[Depends(get_current_user)],
)


class IssueCreate(BaseModel):
    category: str = Field(..., description="One of ALLOWED_CATEGORIES.")
    description: str = Field(..., min_length=4, max_length=1000)


class IssueOut(BaseModel):
    id: str
    hospital_id: str
    category: str
    description: str
    status: str
    reporter_role: Optional[str] = None
    created_at: str


def _to_issue_out(r: HospitalIssueReport) -> IssueOut:
    return IssueOut(
        id=str(r.id),
        hospital_id=str(r.hospital_id),
        category=r.category,
        description=r.description,
        status=r.status,
        reporter_role=r.reporter_role,
        created_at=r.created_at.isoformat() if r.created_at else "",
    )


@router.post(
    "/{hospital_id}/issues",
    response_model=IssueOut,
    status_code=status.HTTP_201_CREATED,
    summary="Report an issue with a specific hospital (open to all auth'd users)",
)
def create_hospital_issue(
    hospital_id: str,
    payload: IssueCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IssueOut:
    # Validate category against the fixed vocabulary.
    if payload.category not in ALLOWED_CATEGORIES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"category must be one of: {sorted(ALLOWED_CATEGORIES)}"
            ),
        )

    # Verify the hospital exists so we don't accumulate orphan issues
    # from typos in the URL.
    try:
        from uuid import UUID
        hid = UUID(hospital_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid hospital_id format")

    if db.query(Hospital).filter(Hospital.id == hid).first() is None:
        raise HTTPException(status_code=404, detail="Hospital not found")

    issue = HospitalIssueReport(
        hospital_id=hid,
        reporter_id=current_user.id,
        category=payload.category,
        description=payload.description.strip(),
        reporter_role=current_user.role.value if current_user.role else None,
        status="open",
        created_at=datetime.now(timezone.utc),
    )
    db.add(issue)
    db.commit()
    db.refresh(issue)
    logger.info(
        "hospital_issue created: hospital=%s category=%s reporter=%s",
        hid, payload.category, current_user.email,
    )
    return _to_issue_out(issue)


@router.get(
    "/{hospital_id}/issues",
    response_model=List[IssueOut],
    summary="List the open / recent issues reported for a hospital",
)
def list_hospital_issues(
    hospital_id: str,
    status_filter: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[IssueOut]:
    """List issues for a hospital, newest first.  Used by the
    detail modal's "Recent reports" panel and the future admin
    inbox.  Open to all auth'd users so a citizen can see whether
    the phone-number typo they were about to report was already
    flagged by someone else."""
    try:
        from uuid import UUID
        hid = UUID(hospital_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid hospital_id format")

    q = db.query(HospitalIssueReport).filter(HospitalIssueReport.hospital_id == hid)
    if status_filter:
        if status_filter not in ALLOWED_STATUSES:
            raise HTTPException(
                status_code=422,
                detail=f"status must be one of: {sorted(ALLOWED_STATUSES)}",
            )
        q = q.filter(HospitalIssueReport.status == status_filter)
    rows = q.order_by(desc(HospitalIssueReport.created_at)).limit(min(limit, 200)).all()
    return [_to_issue_out(r) for r in rows]
