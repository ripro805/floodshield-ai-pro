"""backend/app/routers/reports_export.py
-------------------------------------
Automated Operational Reports & CSV Data Exports:
  - GET /reports/daily-risk/csv          Export risk assessment data
  - GET /reports/hospital-shortages/csv  Export hospital inventory shortages
  - GET /reports/ngo-distribution/csv    Export NGO relief distribution task logs
  - GET /reports/resource-requests/csv   Export government resource requisitions
"""
from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.auth_deps import get_current_user
from app.auth_models import User
from app.operation_models import (
    HospitalInventoryItem, ReliefDistributionTask, ResourceRequest
)
from app.reference_models import Hospital
from app.weather_models import WeatherObservation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["Reports & Data Exports"])


@router.get("/daily-risk/csv")
def export_daily_risk_csv(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export daily environmental and weather risk observations as CSV."""
    if current_user.role not in ("government", "admin", "hospital", "ngo"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized.")

    rows = (
        db.query(WeatherObservation)
        .order_by(desc(WeatherObservation.observed_at))
        .limit(200)
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Recorded At", "Location / District", "Temperature (C)",
        "Humidity (%)", "Rainfall (mm)", "River Level (m)", "Data Source"
    ])

    for r in rows:
        writer.writerow([
            r.observed_at.isoformat() if r.observed_at else "",
            r.location,
            r.temperature,
            r.humidity,
            r.rainfall,
            r.river_level_m or "",
            r.data_source,
        ])

    csv_data = output.getvalue()
    filename = f"floodshield_risk_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/hospital-shortages/csv")
def export_hospital_shortages_csv(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export hospital inventory shortages as CSV."""
    if current_user.role not in ("government", "admin", "hospital"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized.")

    query = (
        db.query(HospitalInventoryItem, Hospital)
        .join(Hospital, HospitalInventoryItem.hospital_id == Hospital.id)
    )
    if current_user.role == "hospital" and current_user.organization:
        query = query.filter(Hospital.name.ilike(f"%{current_user.organization}%"))

    items = query.all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Hospital Name", "District", "Item Name", "Category",
        "Current Stock", "Min Threshold", "Unit", "Critical Shortage Flag", "Batch Number"
    ])

    for item, hosp in items:
        writer.writerow([
            hosp.name,
            hosp.upazila or "National",
            item.item_name,
            item.category,
            item.current_stock,
            item.min_threshold,
            item.unit,
            "YES" if item.current_stock < item.min_threshold else "NO",
            item.batch_number or "",
        ])

    csv_data = output.getvalue()
    filename = f"hospital_inventory_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/ngo-distribution/csv")
def export_ngo_distribution_csv(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export NGO relief distribution task logs as CSV."""
    if current_user.role not in ("government", "admin", "ngo"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized.")

    query = db.query(ReliefDistributionTask)
    if current_user.role == "ngo" and current_user.organization:
        query = query.filter(ReliefDistributionTask.organization_name.ilike(f"%{current_user.organization}%"))

    tasks = query.order_by(desc(ReliefDistributionTask.created_at)).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Task Title", "Organization", "District", "Upazila",
        "Beneficiary Households", "People Reached", "Status",
        "Assigned Team", "Created At", "Completed At"
    ])

    for t in tasks:
        writer.writerow([
            t.title,
            t.organization_name,
            t.district,
            t.upazila or "",
            t.beneficiary_households,
            t.people_reached,
            t.status,
            t.assigned_team or "",
            t.created_at.isoformat() if t.created_at else "",
            t.completed_at.isoformat() if t.completed_at else "",
        ])

    csv_data = output.getvalue()
    filename = f"ngo_distribution_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/resource-requests/csv")
def export_resource_requests_csv(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export government resource requisition summary as CSV."""
    if current_user.role not in ("government", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized.")

    requests = db.query(ResourceRequest).order_by(desc(ResourceRequest.created_at)).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Requester Email", "Requester Role", "Organization",
        "District", "Upazila", "Request Type", "Urgency", "Status",
        "Created At", "Reviewed At"
    ])

    for r in requests:
        writer.writerow([
            str(r.id),
            r.requester_email,
            r.requester_role,
            r.organization_name,
            r.district,
            r.upazila or "",
            r.request_type,
            r.urgency,
            r.status,
            r.created_at.isoformat() if r.created_at else "",
            r.reviewed_at.isoformat() if r.reviewed_at else "",
        ])

    csv_data = output.getvalue()
    filename = f"resource_requests_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
