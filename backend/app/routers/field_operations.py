"""backend/app/routers/field_operations.py
----------------------------------------
Operational endpoints for Health Worker field activities and Citizen report tracking.

Endpoints:
  - GET   /field/tasks                   List assigned field tasks
  - POST  /field/tasks                   Create new field task
  - PATCH /field/tasks/{id}              Accept, update status, complete task
  - GET   /field/visit-logs              List field visit logs
  - POST  /field/visit-logs              Record field visit & interventions
  - POST  /citizen/reports               Submit citizen incident report
  - GET   /citizen/my-reports            Track citizen's own reports & status
  - PATCH /citizen/reports/{id}/withdraw Withdraw unverified citizen report
  - GET   /citizen/public-alerts         View active public advisories & alerts
  - GET   /citizen/public-hospitals      View hospital public capacity & emergency contacts
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.database import get_db
from app.auth_deps import get_current_user, get_optional_user
from app.auth_models import User
from app.operation_models import FieldTask, FieldVisitLog, OfficialAlert
from app.reference_models import CommunityReport, Hospital, District
from app.services.audit_service import log_audit_event

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Field & Citizen Operations"])


# ──────────────────────────────────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────────────────────────────────

class TaskCreateRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    description: Optional[str] = None
    task_type: str = Field(default="outbreak_investigation")  # outbreak_investigation | ors_distribution | water_testing | emergency_triage | vulnerable_check
    district: str = Field(..., min_length=2, max_length=120)
    upazila: Optional[str] = None
    priority: str = Field(default="medium")  # low | medium | high | critical
    assigned_to_email: str
    deadline: Optional[datetime] = None


class TaskStatusUpdateRequest(BaseModel):
    status: str = Field(..., pattern="^(accepted|in_progress|completed|cancelled)$")
    completion_notes: Optional[str] = None


class VisitLogCreateRequest(BaseModel):
    district: str
    upazila: Optional[str] = None
    location_name: str
    households_visited: int = Field(default=0, ge=0)
    suspected_cases_count: int = Field(default=0, ge=0)
    suspected_diseases: Optional[str] = None
    ors_packets_distributed: int = Field(default=0, ge=0)
    water_purification_tablets_distributed: int = Field(default=0, ge=0)
    referrals_count: int = Field(default=0, ge=0)
    urgent_shortage_reported: Optional[str] = None
    notes: Optional[str] = None


class CitizenReportCreateRequest(BaseModel):
    text: str = Field(..., min_length=5)
    label: str = Field(default="flood_incident")  # flood_incident | water_contamination | disease_cluster | supply_shortage
    severity: str = Field(default="medium")       # low | medium | high | critical
    district: Optional[str] = None
    upazila: Optional[str] = None
    reporter_email: Optional[str] = None
    reporter_phone: Optional[str] = None
    image_url: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


# ──────────────────────────────────────────────────────────────────────────
# 1. Health Worker Field Tasks
# ──────────────────────────────────────────────────────────────────────────

@router.get("/field/tasks")
def list_field_tasks(
    district: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve field tasks. Health workers see tasks assigned to them; government/admin see all."""
    query = db.query(FieldTask)
    if current_user.role == "health_worker":
        query = query.filter(FieldTask.assigned_to_email == current_user.email)
    elif current_user.role not in ("government", "admin", "hospital"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role not authorized to access field task records."
        )

    if district:
        query = query.filter(FieldTask.district.ilike(f"%{district}%"))
    if status_filter:
        query = query.filter(FieldTask.status == status_filter)

    tasks = query.order_by(desc(FieldTask.created_at)).limit(100).all()
    return [
        {
            "id": str(t.id),
            "title": t.title,
            "description": t.description,
            "task_type": t.task_type,
            "district": t.district,
            "upazila": t.upazila,
            "priority": t.priority,
            "status": t.status,
            "assigned_to_email": t.assigned_to_email,
            "assigned_by_email": t.assigned_by_email,
            "deadline": t.deadline.isoformat() if t.deadline else None,
            "completion_notes": t.completion_notes,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        }
        for t in tasks
    ]


@router.post("/field/tasks", status_code=status.HTTP_201_CREATED)
def create_field_task(
    payload: TaskCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new field task. Permitted for health_worker (self-organized), government, and admin."""
    if current_user.role not in ("health_worker", "government", "admin", "hospital"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to assign tasks.")

    task = FieldTask(
        title=payload.title,
        description=payload.description,
        task_type=payload.task_type,
        district=payload.district,
        upazila=payload.upazila,
        priority=payload.priority,
        status="assigned",
        assigned_to_email=payload.assigned_to_email,
        assigned_by_email=current_user.email,
        deadline=payload.deadline,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    log_audit_event(
        db=db,
        user_email=current_user.email,
        user_role=current_user.role,
        action="create",
        resource_type="field_task",
        resource_id=str(task.id),
        after_state={"title": task.title, "assigned_to": task.assigned_to_email},
        details=f"Field task assigned to {payload.assigned_to_email}",
    )
    return {"message": "Field task created successfully", "task_id": str(task.id)}


@router.patch("/field/tasks/{task_id}")
def update_field_task_status(
    task_id: str,
    payload: TaskStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update field task status. Health workers can update their own tasks; admins can update any."""
    try:
        t_uuid = uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid task ID format.")

    task = db.query(FieldTask).filter(FieldTask.id == t_uuid).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Field task not found.")

    if current_user.role == "health_worker" and task.assigned_to_email != current_user.email:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot modify tasks assigned to others.")

    before_state = {"status": task.status}
    task.status = payload.status
    if payload.completion_notes:
        task.completion_notes = payload.completion_notes
    task.updated_at = datetime.now(timezone.utc)
    db.commit()

    log_audit_event(
        db=db,
        user_email=current_user.email,
        user_role=current_user.role,
        action="status_change",
        resource_type="field_task",
        resource_id=str(task.id),
        before_state=before_state,
        after_state={"status": task.status},
        details=f"Task {task.id} updated to {payload.status}",
    )
    return {"message": f"Task status updated to {payload.status}", "task_id": str(task.id)}


# ──────────────────────────────────────────────────────────────────────────
# 2. Health Worker Field Visit Logs
# ──────────────────────────────────────────────────────────────────────────

@router.get("/field/visit-logs")
def list_field_visit_logs(
    district: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List field visit logs. Filtered to health worker's own logs unless government/admin."""
    query = db.query(FieldVisitLog)
    if current_user.role == "health_worker":
        query = query.filter(FieldVisitLog.health_worker_email == current_user.email)
    elif current_user.role not in ("government", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized.")

    if district:
        query = query.filter(FieldVisitLog.district.ilike(f"%{district}%"))

    logs = query.order_by(desc(FieldVisitLog.created_at)).limit(100).all()
    return [
        {
            "id": str(log.id),
            "health_worker_email": log.health_worker_email,
            "district": log.district,
            "upazila": log.upazila,
            "location_name": log.location_name,
            "households_visited": log.households_visited,
            "suspected_cases_count": log.suspected_cases_count,
            "suspected_diseases": log.suspected_diseases,
            "ors_packets_distributed": log.ors_packets_distributed,
            "water_purification_tablets_distributed": log.water_purification_tablets_distributed,
            "referrals_count": log.referrals_count,
            "urgent_shortage_reported": log.urgent_shortage_reported,
            "notes": log.notes,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]


@router.post("/field/visit-logs", status_code=status.HTTP_201_CREATED)
def record_field_visit_log(
    payload: VisitLogCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit a field visit log with household visit counts, disease case clusters, and supplies distributed."""
    if current_user.role not in ("health_worker", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only health workers may submit visit logs.")

    log = FieldVisitLog(
        health_worker_email=current_user.email,
        district=payload.district,
        upazila=payload.upazila,
        location_name=payload.location_name,
        households_visited=payload.households_visited,
        suspected_cases_count=payload.suspected_cases_count,
        suspected_diseases=payload.suspected_diseases,
        ors_packets_distributed=payload.ors_packets_distributed,
        water_purification_tablets_distributed=payload.water_purification_tablets_distributed,
        referrals_count=payload.referrals_count,
        urgent_shortage_reported=payload.urgent_shortage_reported,
        notes=payload.notes,
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    log_audit_event(
        db=db,
        user_email=current_user.email,
        user_role=current_user.role,
        action="create",
        resource_type="field_visit_log",
        resource_id=str(log.id),
        after_state={
            "location": payload.location_name,
            "households": payload.households_visited,
            "cases": payload.suspected_cases_count,
        },
        details=f"Field visit recorded at {payload.location_name}",
    )
    return {"message": "Field visit log recorded successfully", "log_id": str(log.id)}


# ──────────────────────────────────────────────────────────────────────────
# 3. Citizen Incident Reports & Report Tracking
# ──────────────────────────────────────────────────────────────────────────

@router.post("/citizen/reports", status_code=status.HTTP_201_CREATED)
def submit_citizen_report(
    payload: CitizenReportCreateRequest,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
):
    """Submit a citizen incident report (flood, water contamination, disease cluster).

    Treated as 'unverified' by default until reviewed by an authorized health worker or official.
    """
    reporter_email = payload.reporter_email
    if user and not reporter_email:
        reporter_email = user.email

    report = CommunityReport(
        text=payload.text,
        label=payload.label,
        severity=payload.severity,
        district=payload.district,
        upazila=payload.upazila,
        reporter_email=reporter_email,
        reporter_phone=payload.reporter_phone,
        image_url=payload.image_url,
        latitude=payload.latitude,
        longitude=payload.longitude,
        status="unverified",
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    return {
        "message": "Incident report submitted. It is recorded as unverified pending operational review.",
        "report_id": str(report.id),
        "status": report.status,
    }


@router.get("/citizen/my-reports")
def list_citizen_own_reports(
    email: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
):
    """Retrieve all reports submitted by the requesting citizen to track verification status."""
    target_email = email
    if user:
        target_email = user.email

    if not target_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide an email or authenticate to view your reports."
        )

    reports = (
        db.query(CommunityReport)
        .filter(CommunityReport.reporter_email == target_email)
        .order_by(desc(CommunityReport.created_at))
        .limit(50)
        .all()
    )

    return [
        {
            "id": str(r.id),
            "text": r.text,
            "label": r.label,
            "severity": r.severity,
            "district": r.district,
            "upazila": r.upazila,
            "status": r.status or "unverified",
            "image_url": r.image_url,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in reports
    ]


@router.patch("/citizen/reports/{report_id}/withdraw")
def withdraw_citizen_report(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Allow citizen to withdraw their own report before verification."""
    try:
        r_uuid = uuid.UUID(report_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid report ID format.")

    report = db.query(CommunityReport).filter(CommunityReport.id == r_uuid).first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")

    if current_user.role != "admin" and report.reporter_email != current_user.email:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot withdraw a report submitted by someone else.")

    if report.status == "verified":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot withdraw a report that has already been verified by authorities.")

    report.status = "withdrawn"
    db.commit()
    return {"message": "Report successfully withdrawn.", "report_id": str(report.id)}


# ──────────────────────────────────────────────────────────────────────────
# 4. Public Citizen Views (Alerts & Hospital Capacity)
# ──────────────────────────────────────────────────────────────────────────

@router.get("/citizen/public-alerts")
def get_public_alerts(
    district: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Public read-only view of published official alerts."""
    query = db.query(OfficialAlert).filter(OfficialAlert.status == "published")
    if district:
        query = query.filter(
            (OfficialAlert.target_districts.ilike(f"%{district}%")) |
            (OfficialAlert.target_districts == "ALL")
        )
    alerts = query.order_by(desc(OfficialAlert.published_at)).limit(20).all()

    return [
        {
            "id": str(a.id),
            "title_bn": a.title_bn,
            "title_en": a.title_en,
            "message_bn": a.message_bn,
            "message_en": a.message_en,
            "severity": a.severity,
            "target_districts": a.target_districts,
            "published_at": a.published_at.isoformat() if a.published_at else None,
            "expires_at": a.expires_at.isoformat() if a.expires_at else None,
        }
        for a in alerts
    ]


@router.get("/citizen/public-hospitals")
def get_public_hospital_capacity(
    district: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Public read-only view of hospital capacity, operating status, and emergency contacts.

    Private internal medicine inventory is strictly hidden.
    """
    query = db.query(Hospital)
    if district:
        # Resolve district name to district_id or match by name
        dist_row = db.query(District).filter(District.name.ilike(f"%{district}%")).first()
        if dist_row:
            query = query.filter(Hospital.district_id == dist_row.id)

    hospitals = query.limit(50).all()
    results = []
    for h in hospitals:
        total_beds = h.beds or 0
        occupied_beds = h.beds_occupied or 0
        available_beds = max(0, total_beds - occupied_beds)

        icu_total = h.icu_beds_total or 0
        icu_occupied = h.icu_beds_occupied or 0
        icu_available = max(0, icu_total - icu_occupied)

        results.append({
            "id": str(h.id),
            "name": h.name,
            "upazila": h.upazila,
            "address": h.address,
            "phone": h.phone,
            "emergency_contact": h.emergency_contact,
            "operating_status": h.operating_status or "normal",
            "general_beds_available": available_beds,
            "general_beds_total": total_beds,
            "icu_beds_available": icu_available,
            "icu_beds_total": icu_total,
            "last_updated": h.last_updated.isoformat() if h.last_updated else None,
        })
    return results
