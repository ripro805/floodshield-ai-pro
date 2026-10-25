"""backend/app/routers/automation_admin.py
----------------------------------------
Admin management endpoints for backend automation jobs and system audit logs.
  - GET  /admin/jobs                  List all automation jobs and performance health
  - POST /admin/jobs/{job_name}/run-now Trigger immediate background job execution
  - GET  /admin/audit-logs            View recent system audit event trail
"""
from __future__ import annotations

import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.auth_deps import get_current_user
from app.auth_models import User
from app.operation_models import AutomationJob, AuditEvent
from app.services.automation_engine import run_single_job, ensure_jobs_registered

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin & Automation Monitoring"])


@router.get("/jobs")
def list_automation_jobs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """View status, execution history, and error logs of all native automation jobs."""
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Restricted to system administrators.")

    ensure_jobs_registered(db)
    jobs = db.query(AutomationJob).order_by(AutomationJob.job_name).all()
    return [
        {
            "id": str(j.id),
            "job_name": j.job_name,
            "description": j.description,
            "interval_seconds": j.interval_seconds,
            "status": j.status,
            "last_run_at": j.last_run_at.isoformat() if j.last_run_at else None,
            "next_run_at": j.next_run_at.isoformat() if j.next_run_at else None,
            "last_duration_seconds": j.last_duration_seconds,
            "last_error": j.last_error,
            "total_runs": j.total_runs,
            "success_runs": j.success_runs,
            "failure_runs": j.failure_runs,
            "is_active": j.is_active,
            "updated_at": j.updated_at.isoformat() if j.updated_at else None,
        }
        for j in jobs
    ]


@router.post("/jobs/{job_name}/run-now")
async def trigger_job_run(
    job_name: str,
    current_user: User = Depends(get_current_user),
):
    """Manually invoke an automation job on demand."""
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Restricted to system administrators.")

    try:
        result = await run_single_job(job_name)
        return {"message": f"Job '{job_name}' completed", "details": result}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Job execution failed: {exc}")


@router.get("/audit-logs")
def list_audit_logs(
    resource_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Inspect immutable audit log of administrative and operational actions."""
    if current_user.role not in ("admin", "government"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized.")

    query = db.query(AuditEvent)
    if resource_type:
        query = query.filter(AuditEvent.resource_type == resource_type)

    logs = query.order_by(desc(AuditEvent.created_at)).limit(limit).all()
    return [
        {
            "id": str(log.id),
            "user_email": log.user_email,
            "user_role": log.user_role,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "details": log.details,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]
