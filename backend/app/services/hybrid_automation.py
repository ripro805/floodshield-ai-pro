"""backend/app/services/hybrid_automation.py
-----------------------------------------
Centralized Hybrid Automation Controller.

Implements Cases A through G:
  - CASE A: Docker ON + n8n healthy + workflow available -> execute through n8n
  - CASE B: Docker OFF -> execute through existing Native Automation
  - CASE C: Docker ON + n8n unavailable -> execute through existing Native Automation
  - CASE D: n8n webhook connection failure -> execute through existing Native Automation
  - CASE E: n8n workflow inactive / 404 / 422 -> execute through existing Native Automation
  - CASE F: n8n request times out -> record UNKNOWN, avoid blind double execution
  - CASE G: Docker/n8n recovers -> automatically route future eligible tasks to n8n
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Any
from sqlalchemy.exc import IntegrityError
from sqlalchemy import desc

from app.config import AUTOMATION_MODE, N8N_ENABLED
from app.database import SessionLocal
from app.operation_models import AutomationExecution
from app.services.automation_engine import run_single_job
from app.services import n8n_service

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


JOB_EVENT_MAP = {
    "weather_collector": "weather_check",
    "scheduled_district_predictions": "weather_check",
    "risk_monitor": "weather_check",
    "inventory_monitor": "inventory_check",
    "unresolved_issues_escalator": "issues_check",
}


async def run_hybrid_job(
    job_name: str,
    task_id: Optional[str] = None,
    event_id: Optional[str] = None,
) -> dict:
    """Execute an automation job using intelligent hybrid routing with atomic claiming."""
    task_id = task_id or f"{job_name}:{uuid.uuid4().hex}"
    event_id = event_id or uuid.uuid4().hex

    # ── 1. Idempotency Check & Atomic Claim ────────────────────────────────────
    db = SessionLocal()
    try:
        existing = db.query(AutomationExecution).filter(
            (AutomationExecution.task_id == task_id) | (AutomationExecution.event_id == event_id)
        ).first()
        if existing:
            logger.info("Duplicate task detected for task_id=%s, returning existing record", task_id)
            return {
                "job_name": existing.job_name,
                "status": existing.status,
                "engine": existing.engine,
                "task_id": existing.task_id,
                "event_id": existing.event_id,
                "result": existing.result,
                "duplicate": True,
            }

        claim = AutomationExecution(
            task_id=task_id,
            event_id=event_id,
            job_name=job_name,
            engine="unknown",
            status="running",
            started_at=_utc_now(),
        )
        db.add(claim)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            existing = db.query(AutomationExecution).filter(
                (AutomationExecution.task_id == task_id) | (AutomationExecution.event_id == event_id)
            ).first()
            if existing:
                return {
                    "job_name": existing.job_name,
                    "status": existing.status,
                    "engine": existing.engine,
                    "task_id": existing.task_id,
                    "event_id": existing.event_id,
                    "result": existing.result,
                    "duplicate": True,
                }
            raise
    finally:
        db.close()

    # ── 2. Determine Availability & Route ──────────────────────────────────────
    use_n8n = AUTOMATION_MODE in ("auto", "n8n")
    health = await n8n_service.n8n_health_check() if use_n8n else {"healthy": False, "reason": "n8n disabled by mode"}

    if health.get("healthy"):
        payload = {
            "task_id": task_id,
            "event_id": event_id,
            "event_type": JOB_EVENT_MAP.get(job_name, "general_automation"),
            "event": JOB_EVENT_MAP.get(job_name, "general_automation"),
            "timestamp": _utc_now().isoformat(),
            "source": "floodshield-backend",
            "job_name": job_name,
            "data": {
                "scheduled_task": job_name,
                "dispatched_at": _utc_now().isoformat(),
            },
        }

        dispatch = await n8n_service.dispatch_n8n(payload)

        # CASE A: n8n accepted the task
        if dispatch["outcome"] == "accepted":
            db = SessionLocal()
            try:
                execution = db.query(AutomationExecution).filter(AutomationExecution.task_id == task_id).first()
                if execution:
                    execution.engine = "n8n"
                    execution.status = "pending"
                    execution.result = {
                        "accepted": True,
                        "execution_verified": False,
                        "status_code": dispatch.get("status_code"),
                        "workflow": "floodshield-monitoring",
                    }
                    execution.completed_at = None
                    db.commit()
            finally:
                db.close()

            logger.info("Task %s accepted by n8n workflow", task_id)
            return {
                "job_name": job_name,
                "status": "pending",
                "engine": "n8n",
                "task_id": task_id,
                "event_id": event_id,
                "accepted": True,
            }

        # CASE F: n8n timed out after dispatch -- UNCERTAIN OUTCOME
        # Do NOT blindly execute native logic to prevent duplicate execution!
        if dispatch["outcome"] == "timeout":
            db = SessionLocal()
            try:
                execution = db.query(AutomationExecution).filter(AutomationExecution.task_id == task_id).first()
                if execution:
                    execution.engine = "unknown"
                    execution.status = "unknown"
                    execution.error = dispatch["reason"]
                    db.commit()
            finally:
                db.close()

            logger.warning("Task %s dispatch to n8n timed out; marked as unknown", task_id)
            return {
                "job_name": job_name,
                "status": "unknown",
                "engine": "unknown",
                "task_id": task_id,
                "event_id": event_id,
                "error": dispatch["reason"],
            }

        # CASE D/E: n8n rejected or connection failed before acceptance
        logger.info("n8n dispatch failed (%s); falling back to native automation", dispatch.get("reason"))

    # ── 3. Native Automation Fallback Execution ────────────────────────────────
    # Preserves 100% of the original native automation handlers
    native = await run_single_job(job_name)

    db = SessionLocal()
    try:
        execution = db.query(AutomationExecution).filter(AutomationExecution.task_id == task_id).first()
        if execution:
            execution.engine = "native"
            execution.status = native["status"]
            execution.result = native
            execution.error = native.get("error")
            execution.completed_at = _utc_now()
            db.commit()
    finally:
        db.close()

    native["task_id"] = task_id
    native["event_id"] = event_id
    native["engine"] = "native"
    native["fallback_reason"] = health.get("reason", "n8n unavailable")
    return native


async def get_automation_status() -> dict:
    """Return consolidated telemetry for admin monitoring dashboard."""
    health = await n8n_service.n8n_health_check(force=True)
    db = SessionLocal()
    try:
        executions = db.query(AutomationExecution).order_by(desc(AutomationExecution.started_at)).all()
        
        counts = {
            "total": len(executions),
            "n8n": sum(1 for item in executions if item.engine == "n8n"),
            "native": sum(1 for item in executions if item.engine == "native"),
            "success": sum(1 for item in executions if item.status == "success"),
            "failed": sum(1 for item in executions if item.status == "failed"),
            "unknown": sum(1 for item in executions if item.status == "unknown"),
            "pending": sum(1 for item in executions if item.status == "pending"),
            "retries": sum(1 for item in executions if item.status in ("failed", "unknown")),
        }

        recent = [
            {
                "task_id": item.task_id,
                "job_name": item.job_name,
                "engine": item.engine,
                "status": item.status,
                "error": item.error,
                "started_at": item.started_at.isoformat() if item.started_at else None,
                "completed_at": item.completed_at.isoformat() if item.completed_at else None,
            }
            for item in executions[:20]
        ]

        recent_errors = [
            {
                "task_id": item.task_id,
                "job_name": item.job_name,
                "engine": item.engine,
                "error": item.error,
                "timestamp": item.started_at.isoformat() if item.started_at else None,
            }
            for item in executions if item.error
        ][:5]

        last_success_record = (
            db.query(AutomationExecution)
            .filter(AutomationExecution.status == "success")
            .order_by(desc(AutomationExecution.completed_at))
            .first()
        )
        last_success = (
            last_success_record.completed_at.isoformat()
            if last_success_record and last_success_record.completed_at
            else None
        )

    finally:
        db.close()

    checked_at = health.get("checked_at")
    return {
        "active_engine": "n8n" if health.get("healthy") else "native",
        "native_status": "available",
        "docker": health.get("docker", {"running": False, "status": "unknown"}),
        "n8n": {
            "enabled": N8N_ENABLED,
            "healthy": health.get("healthy", False),
            "reason": health.get("reason", "unknown"),
            "status_code": health.get("status_code"),
            "last_health_check": checked_at.isoformat() if checked_at else None,
        },
        "counts": counts,
        "recent_executions": recent,
        "recent_errors": recent_errors,
        "last_successful_execution": last_success,
    }
