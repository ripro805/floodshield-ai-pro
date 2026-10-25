"""backend/app/routers/government_coordination.py
------------------------------------------------
Operational endpoints for National Emergency Government Coordination:
  - GET   /government/command-overview          Consolidated emergency metrics
  - GET   /government/resource-requests         List support & supply requisitions
  - POST  /government/resource-requests         Submit support request (Hospital/NGO/Field)
  - PATCH /government/resource-requests/{id}/review Review, approve, reject request
  - POST  /government/resource-allocations      Create allocation & dispatch record
  - PATCH /government/resource-allocations/{id}/status Update dispatch & receipt status
  - GET   /alerts/official                      List official emergency alerts
  - POST  /alerts/official                      Draft new official alert (Bengali + English)
  - POST  /alerts/official/{id}/publish         Publish approved alert
  - PATCH /alerts/official/{id}/cancel          Cancel or withdraw active alert
  - GET   /government/issues-rollup             Consolidated cross-agency incident roll-up
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, or_

from app.database import get_db
from app.auth_deps import get_current_user
from app.auth_models import User
from app.operation_models import (
    ResourceRequest, ResourceAllocation, OfficialAlert,
    HospitalInventoryItem, ReliefCampaign, ReliefDistributionTask,
    FieldVisitLog, FieldTask
)
from app.reference_models import Hospital, CommunityReport, District
from app.services.audit_service import log_audit_event

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Government Emergency Coordination"])


# ──────────────────────────────────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────────────────────────────────

class ResourceRequestCreate(BaseModel):
    request_type: str = Field(..., pattern="^(medicine|iv_fluid|medical_personnel|clean_water|relief_supplies|emergency_evacuation)$")
    district: str
    upazila: Optional[str] = None
    requested_items: List[dict]  # [{"item": "IV Saline Bags", "quantity": 1000, "unit": "bag"}]
    urgency: str = Field(default="urgent", pattern="^(normal|urgent|critical_emergency)$")
    justification: str = Field(..., min_length=10)


class ResourceRequestReview(BaseModel):
    status: str = Field(..., pattern="^(approved|partially_fulfilled|rejected)$")
    review_notes: Optional[str] = None
    allocated_items: Optional[List[dict]] = None


class ResourceAllocationCreate(BaseModel):
    request_id: str
    source_depot_or_facility: str
    destination_facility: str
    allocated_items: List[dict]
    tracking_number: Optional[str] = None


class ResourceAllocationStatusUpdate(BaseModel):
    dispatch_status: str = Field(..., pattern="^(pending_dispatch|dispatched|in_transit|received)$")
    receipt_notes: Optional[str] = None


class OfficialAlertCreate(BaseModel):
    title_bn: str = Field(..., min_length=3)
    title_en: str = Field(..., min_length=3)
    message_bn: str = Field(..., min_length=10)
    message_en: str = Field(..., min_length=10)
    severity: str = Field(default="warning", pattern="^(advisory|warning|critical|evacuation)$")
    target_districts: str  # e.g. "Feni, Sylhet" or "ALL"
    channel: str = Field(default="in_app", pattern="^(in_app|sms|both)$")
    expires_at: Optional[datetime] = None


# ──────────────────────────────────────────────────────────────────────────
# 1. National Command Center Overview
# ──────────────────────────────────────────────────────────────────────────

@router.get("/government/command-overview")
def get_command_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Consolidated national situational metrics for emergency coordinators."""
    if current_user.role not in ("government", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted to government emergency coordinators."
        )

    # 1. Hospital Bed Capacity aggregates
    hospital_stats = db.query(
        func.count(Hospital.id).label("total_hospitals"),
        func.sum(Hospital.beds).label("total_beds"),
        func.sum(Hospital.beds_occupied).label("occupied_beds"),
        func.sum(Hospital.icu_beds_total).label("total_icu"),
        func.sum(Hospital.icu_beds_occupied).label("occupied_icu"),
    ).first()

    total_beds = hospital_stats.total_beds or 0
    occupied_beds = hospital_stats.occupied_beds or 0
    available_beds = max(0, total_beds - occupied_beds)

    total_icu = hospital_stats.total_icu or 0
    occupied_icu = hospital_stats.occupied_icu or 0
    available_icu = max(0, total_icu - occupied_icu)

    # 2. Critical medicine shortages count
    shortage_count = (
        db.query(HospitalInventoryItem)
        .filter(HospitalInventoryItem.current_stock < HospitalInventoryItem.min_threshold)
        .count()
    )

    # 3. NGO relief campaigns & tasks
    active_campaigns = db.query(ReliefCampaign).filter(ReliefCampaign.status == "active").count()
    active_distributions = (
        db.query(ReliefDistributionTask)
        .filter(ReliefDistributionTask.status.in_(["planned", "dispatched", "in_transit"]))
        .count()
    )

    # 4. Pending Resource Requests
    pending_requests = (
        db.query(ResourceRequest)
        .filter(ResourceRequest.status.in_(["pending", "under_review"]))
        .count()
    )

    # 5. Citizen Unverified Reports
    unverified_reports = (
        db.query(CommunityReport)
        .filter(CommunityReport.status == "unverified")
        .count()
    )

    # 6. Active Official Alerts
    active_alerts = db.query(OfficialAlert).filter(OfficialAlert.status == "published").count()

    # 7. Field visits completed
    field_visits_count = db.query(FieldVisitLog).count()

    return {
        "status": "operational",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "hospital_capacity": {
            "total_facilities": hospital_stats.total_hospitals or 0,
            "total_general_beds": total_beds,
            "available_general_beds": available_beds,
            "total_icu_beds": total_icu,
            "available_icu_beds": available_icu,
            "critical_stock_shortages": shortage_count,
        },
        "ngo_operations": {
            "active_campaigns": active_campaigns,
            "active_relief_tasks": active_distributions,
        },
        "coordination": {
            "pending_resource_requests": pending_requests,
            "active_official_alerts": active_alerts,
            "unverified_citizen_reports": unverified_reports,
            "field_investigations_logged": field_visits_count,
        },
    }


# ──────────────────────────────────────────────────────────────────────────
# 2. Resource Requisition & Allocation System
# ──────────────────────────────────────────────────────────────────────────

@router.get("/government/resource-requests")
def list_resource_requests(
    district: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    urgency_filter: Optional[str] = Query(None, alias="urgency"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List resource requests. Requesters see their own; government/admin see all."""
    query = db.query(ResourceRequest)
    if current_user.role not in ("government", "admin"):
        query = query.filter(ResourceRequest.requester_email == current_user.email)

    if district:
        query = query.filter(ResourceRequest.district.ilike(f"%{district}%"))
    if status_filter:
        query = query.filter(ResourceRequest.status == status_filter)
    if urgency_filter:
        query = query.filter(ResourceRequest.urgency == urgency_filter)

    requests = query.order_by(desc(ResourceRequest.created_at)).limit(100).all()
    return [
        {
            "id": str(r.id),
            "requester_email": r.requester_email,
            "requester_role": r.requester_role,
            "organization_name": r.organization_name,
            "district": r.district,
            "upazila": r.upazila,
            "request_type": r.request_type,
            "requested_items": r.requested_items,
            "urgency": r.urgency,
            "justification": r.justification,
            "status": r.status,
            "allocated_items": r.allocated_items,
            "reviewer_email": r.reviewer_email,
            "review_notes": r.review_notes,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
        }
        for r in requests
    ]


@router.post("/government/resource-requests", status_code=status.HTTP_201_CREATED)
def submit_resource_request(
    payload: ResourceRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit a support requisition to the government (Hospital, Health Worker, or NGO)."""
    if current_user.role not in ("hospital", "ngo", "health_worker", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Citizens cannot submit institutional resource requisitions."
        )

    org_name = current_user.organization or f"{current_user.role.title()} User"

    req = ResourceRequest(
        requester_email=current_user.email,
        requester_role=current_user.role,
        organization_name=org_name,
        district=payload.district,
        upazila=payload.upazila,
        request_type=payload.request_type,
        requested_items=payload.requested_items,
        urgency=payload.urgency,
        justification=payload.justification,
        status="pending",
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    log_audit_event(
        db=db,
        user_email=current_user.email,
        user_role=current_user.role,
        action="create",
        resource_type="resource_request",
        resource_id=str(req.id),
        after_state={"type": req.request_type, "urgency": req.urgency, "org": org_name},
        details=f"Resource request filed for {payload.district}: {payload.request_type}",
    )
    return {"message": "Resource request submitted successfully", "request_id": str(req.id)}


@router.patch("/government/resource-requests/{request_id}/review")
def review_resource_request(
    request_id: str,
    payload: ResourceRequestReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Government/Admin official reviews and approves or rejects a resource request."""
    if current_user.role not in ("government", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only government officials may review requests.")

    try:
        r_uuid = uuid.UUID(request_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid request ID.")

    req = db.query(ResourceRequest).filter(ResourceRequest.id == r_uuid).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource request not found.")

    before_state = {"status": req.status}
    req.status = payload.status
    req.reviewer_email = current_user.email
    req.review_notes = payload.review_notes
    if payload.allocated_items:
        req.allocated_items = payload.allocated_items
    req.reviewed_at = datetime.now(timezone.utc)
    db.commit()

    log_audit_event(
        db=db,
        user_email=current_user.email,
        user_role=current_user.role,
        action="review",
        resource_type="resource_request",
        resource_id=str(req.id),
        before_state=before_state,
        after_state={"status": req.status, "reviewer": current_user.email},
        details=f"Request {req.id} set to {payload.status}",
    )
    return {"message": f"Request marked as {payload.status}", "request_id": str(req.id)}


@router.post("/government/resource-allocations", status_code=status.HTTP_201_CREATED)
def create_resource_allocation(
    payload: ResourceAllocationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Dispatch authorized supplies against an approved resource request."""
    if current_user.role not in ("government", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only government officials may allocate resources.")

    try:
        r_uuid = uuid.UUID(payload.request_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid request ID format.")

    req = db.query(ResourceRequest).filter(ResourceRequest.id == r_uuid).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource request not found.")

    allocation = ResourceAllocation(
        request_id=r_uuid,
        allocated_by_email=current_user.email,
        source_depot_or_facility=payload.source_depot_or_facility,
        destination_facility=payload.destination_facility,
        allocated_items=payload.allocated_items,
        tracking_number=payload.tracking_number,
        dispatch_status="dispatched",
        dispatched_at=datetime.now(timezone.utc),
    )
    db.add(allocation)
    db.commit()
    db.refresh(allocation)

    log_audit_event(
        db=db,
        user_email=current_user.email,
        user_role=current_user.role,
        action="allocate",
        resource_type="resource_allocation",
        resource_id=str(allocation.id),
        after_state={"destination": payload.destination_facility, "items": payload.allocated_items},
        details=f"Allocation dispatched to {payload.destination_facility}",
    )
    return {"message": "Resource allocation dispatched successfully", "allocation_id": str(allocation.id)}


# ──────────────────────────────────────────────────────────────────────────
# 3. Official Alert Management (Bilingual)
# ──────────────────────────────────────────────────────────────────────────

@router.get("/alerts/official")
def list_official_alerts(
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List official emergency alerts."""
    query = db.query(OfficialAlert)
    if status_filter:
        query = query.filter(OfficialAlert.status == status_filter)

    alerts = query.order_by(desc(OfficialAlert.created_at)).limit(50).all()
    return [
        {
            "id": str(a.id),
            "title_bn": a.title_bn,
            "title_en": a.title_en,
            "message_bn": a.message_bn,
            "message_en": a.message_en,
            "severity": a.severity,
            "target_districts": a.target_districts,
            "status": a.status,
            "channel": a.channel,
            "sent_sms_count": a.sent_sms_count,
            "created_by_email": a.created_by_email,
            "approved_by_email": a.approved_by_email,
            "published_by_email": a.published_by_email,
            "published_at": a.published_at.isoformat() if a.published_at else None,
            "expires_at": a.expires_at.isoformat() if a.expires_at else None,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in alerts
    ]


@router.post("/alerts/official", status_code=status.HTTP_201_CREATED)
def draft_official_alert(
    payload: OfficialAlertCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Draft a new bilingual official alert."""
    if current_user.role not in ("government", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only government coordinators can draft official alerts.")

    alert = OfficialAlert(
        title_bn=payload.title_bn,
        title_en=payload.title_en,
        message_bn=payload.message_bn,
        message_en=payload.message_en,
        severity=payload.severity,
        target_districts=payload.target_districts,
        channel=payload.channel,
        status="draft",
        created_by_email=current_user.email,
        expires_at=payload.expires_at,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)

    log_audit_event(
        db=db,
        user_email=current_user.email,
        user_role=current_user.role,
        action="create",
        resource_type="official_alert",
        resource_id=str(alert.id),
        after_state={"title_en": alert.title_en, "districts": alert.target_districts},
        details=f"Draft alert created: {alert.title_en}",
    )
    return {"message": "Official alert draft created", "alert_id": str(alert.id)}


@router.post("/alerts/official/{alert_id}/publish")
def publish_official_alert(
    alert_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Authorize and publish an official alert, broadcasting to public portals."""
    if current_user.role not in ("government", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only authorized government officials may publish alerts.")

    try:
        a_uuid = uuid.UUID(alert_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid alert ID.")

    alert = db.query(OfficialAlert).filter(OfficialAlert.id == a_uuid).first()
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found.")

    alert.status = "published"
    alert.approved_by_email = current_user.email
    alert.published_by_email = current_user.email
    alert.published_at = datetime.now(timezone.utc)
    db.commit()

    log_audit_event(
        db=db,
        user_email=current_user.email,
        user_role=current_user.role,
        action="publish",
        resource_type="official_alert",
        resource_id=str(alert.id),
        after_state={"status": "published", "districts": alert.target_districts},
        details=f"Published official alert: {alert.title_en} for {alert.target_districts}",
    )
    return {"message": f"Alert '{alert.title_en}' published successfully", "alert_id": str(alert.id)}


@router.patch("/alerts/official/{alert_id}/cancel")
def cancel_official_alert(
    alert_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cancel or withdraw an official alert."""
    if current_user.role not in ("government", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized.")

    try:
        a_uuid = uuid.UUID(alert_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid alert ID.")

    alert = db.query(OfficialAlert).filter(OfficialAlert.id == a_uuid).first()
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found.")

    alert.status = "cancelled"
    db.commit()
    return {"message": "Alert cancelled.", "alert_id": str(alert.id)}


# ──────────────────────────────────────────────────────────────────────────
# 4. Cross-Agency Issue Roll-up
# ──────────────────────────────────────────────────────────────────────────

@router.get("/government/issues-rollup")
def get_issues_rollup(
    district: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Consolidated cross-agency incident roll-up: community reports, shortages, urgent field logs."""
    if current_user.role not in ("government", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized.")

    # 1. Unverified community reports
    comm_q = db.query(CommunityReport)
    if district:
        comm_q = comm_q.filter(CommunityReport.district.ilike(f"%{district}%"))
    reports = comm_q.order_by(desc(CommunityReport.created_at)).limit(30).all()

    # 2. Urgent field shortages
    field_q = db.query(FieldVisitLog).filter(FieldVisitLog.urgent_shortage_reported.isnot(None))
    if district:
        field_q = field_q.filter(FieldVisitLog.district.ilike(f"%{district}%"))
    field_shortages = field_q.order_by(desc(FieldVisitLog.created_at)).limit(30).all()

    # 3. Hospital inventory critical shortages
    hosp_inv_q = db.query(HospitalInventoryItem, Hospital).join(
        Hospital, HospitalInventoryItem.hospital_id == Hospital.id
    ).filter(HospitalInventoryItem.current_stock < HospitalInventoryItem.min_threshold)
    hosp_shortages = hosp_inv_q.limit(30).all()

    return {
        "community_incidents": [
            {
                "id": str(r.id),
                "text": r.text,
                "label": r.label,
                "severity": r.severity,
                "district": r.district,
                "upazila": r.upazila,
                "status": r.status or "unverified",
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in reports
        ],
        "field_shortages": [
            {
                "id": str(f.id),
                "district": f.district,
                "upazila": f.upazila,
                "location": f.location_name,
                "health_worker": f.health_worker_email,
                "urgent_shortage": f.urgent_shortage_reported,
                "created_at": f.created_at.isoformat() if f.created_at else None,
            }
            for f in field_shortages
        ],
        "hospital_shortages": [
            {
                "item_id": str(item.id),
                "hospital_name": hosp.name,
                "district": hosp.upazila or "National",
                "item_name": item.item_name,
                "current_stock": item.current_stock,
                "min_threshold": item.min_threshold,
                "unit": item.unit,
            }
            for item, hosp in hosp_shortages
        ],
    }
