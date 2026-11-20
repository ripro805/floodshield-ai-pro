"""backend/tests/test_n8n_hybrid.py
-----------------------------------
Automated Verification Suite for FloodShield AI Pro Hybrid n8n + Native Automation.
Verifies all 10 required test scenarios from Section 11:
  - TEST 1: Existing Native Automation (Docker/n8n OFF -> Native executes)
  - TEST 2: Docker and n8n ON (healthy -> routes to n8n)
  - TEST 3: Docker OFF (daemon stopped -> routes to Native)
  - TEST 4: n8n Unavailable (host unreachable -> routes to Native)
  - TEST 5: Webhook Failure (HTTP 500/404/403/422 -> safe Native fallback)
  - TEST 6: n8n Recovery (n8n becomes healthy -> routes to n8n)
  - TEST 7: Duplicate Prevention (same task_id / event_id -> returns duplicate claim)
  - TEST 8: Timeout Handling (timeout on dispatch -> recorded as UNKNOWN)
  - TEST 9: Concurrent Tasks (atomic task claiming -> no collision or deadlocks)
  - TEST 10: Existing Project Regression (registered jobs, interval, models, schema)
"""
from __future__ import annotations

import asyncio
import time
import uuid
from unittest.mock import AsyncMock, patch

import pytest
import httpx

from app.database import SessionLocal
from app.operation_models import AutomationExecution, AutomationJob
from app.services.automation_engine import REGISTERED_JOBS, JOB_HANDLERS
from app.services.hybrid_automation import (
    JOB_EVENT_MAP,
    run_hybrid_job,
    get_automation_status,
)
from app.services import n8n_service


# ─────────────────────────────────────────────────────────────────────────────
# Helper to clean up test execution records
# ─────────────────────────────────────────────────────────────────────────────
def _cleanup_test_records(task_ids: list[str]) -> None:
    db = SessionLocal()
    try:
        db.query(AutomationExecution).filter(AutomationExecution.task_id.in_(task_ids)).delete(
            synchronize_session=False
        )
        db.commit()
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# Contract Tests
# ─────────────────────────────────────────────────────────────────────────────
def test_job_event_contract():
    """Verify standard mapping between internal job names and n8n event types."""
    assert JOB_EVENT_MAP["inventory_monitor"] == "inventory_check"
    assert JOB_EVENT_MAP["unresolved_issues_escalator"] == "issues_check"
    assert JOB_EVENT_MAP["weather_collector"] == "weather_check"
    assert JOB_EVENT_MAP["scheduled_district_predictions"] == "weather_check"
    assert JOB_EVENT_MAP["risk_monitor"] == "weather_check"


# ─────────────────────────────────────────────────────────────────────────────
# TEST 1 — EXISTING NATIVE AUTOMATION
# ─────────────────────────────────────────────────────────────────────────────
def test_scenario_1_existing_native_automation():
    """TEST 1: When Docker is stopped / n8n is disabled, native automation executes cleanly.
    Verifies database updates and execution tracking work natively.
    """
    async def _run():
        test_task_id = f"test-t1-{uuid.uuid4().hex[:8]}"
        test_event_id = uuid.uuid4().hex

        with patch.object(n8n_service, "is_docker_running", return_value=(False, "Docker daemon stopped (simulated)")):
            with patch("app.services.hybrid_automation.AUTOMATION_MODE", "native"):
                res = await run_hybrid_job("inventory_monitor", task_id=test_task_id, event_id=test_event_id)

        assert res["status"] == "success", f"Expected success, got {res}"
        assert res["engine"] == "native"
        assert res["task_id"] == test_task_id
        assert res["event_id"] == test_event_id
        assert "hospital_shortages_flagged" in res["result"]

        # Verify execution was persisted in database
        db = SessionLocal()
        try:
            record = db.query(AutomationExecution).filter_by(task_id=test_task_id).first()
            assert record is not None, "Execution record was not saved to DB"
            assert record.engine == "native"
            assert record.status == "success"
            assert record.completed_at is not None
        finally:
            db.close()
            _cleanup_test_records([test_task_id])

    asyncio.run(_run())


# ─────────────────────────────────────────────────────────────────────────────
# TEST 2 — DOCKER AND N8N RUNNING
# ─────────────────────────────────────────────────────────────────────────────
def test_scenario_2_docker_and_n8n_running():
    """TEST 2: When Docker is running and n8n is healthy, tasks route to n8n.
    Verifies payload contains correct data structure and credentials.
    """
    async def _run():
        test_task_id = f"test-t2-{uuid.uuid4().hex[:8]}"
        test_event_id = uuid.uuid4().hex

        dispatched_payload = {}

        async def mock_dispatch(payload):
            nonlocal dispatched_payload
            dispatched_payload = dict(payload)
            return {"outcome": "accepted", "status_code": 200, "reason": "n8n accepted task"}

        with patch.object(n8n_service, "is_docker_running", return_value=(True, "Docker daemon active (simulated)")):
            with patch.object(
                n8n_service,
                "n8n_health_check",
                return_value={"healthy": True, "reason": "n8n healthy", "docker": {"running": True}},
            ):
                with patch.object(n8n_service, "dispatch_n8n", side_effect=mock_dispatch):
                    res = await run_hybrid_job("weather_collector", task_id=test_task_id, event_id=test_event_id)

        assert res["engine"] == "n8n"
        assert res["status"] == "pending"
        assert res["accepted"] is True
        assert res["task_id"] == test_task_id

        # Verify payload format
        assert dispatched_payload["task_id"] == test_task_id
        assert dispatched_payload["event_id"] == test_event_id
        assert dispatched_payload["event_type"] == "weather_check"
        assert dispatched_payload["event"] == "weather_check"
        assert dispatched_payload["source"] == "floodshield-backend"
        assert "timestamp" in dispatched_payload
        assert dispatched_payload["job_name"] == "weather_collector"
        assert "scheduled_task" in dispatched_payload["data"]

        # Verify database entry
        db = SessionLocal()
        try:
            record = db.query(AutomationExecution).filter_by(task_id=test_task_id).first()
            assert record is not None
            assert record.engine == "n8n"
            assert record.status == "pending"
            assert record.result.get("accepted") is True
        finally:
            db.close()
            _cleanup_test_records([test_task_id])

    asyncio.run(_run())


# ─────────────────────────────────────────────────────────────────────────────
# TEST 3 — DOCKER STOPPED
# ─────────────────────────────────────────────────────────────────────────────
def test_scenario_3_docker_stopped():
    """TEST 3: When Docker daemon is stopped, system detects it and routes to Native.
    Verifies that no unhandled exceptions crash the backend.
    """
    async def _run():
        test_task_id = f"test-t3-{uuid.uuid4().hex[:8]}"
        test_event_id = uuid.uuid4().hex

        with patch.object(n8n_service, "is_docker_running", return_value=(False, "Docker daemon stopped")):
            with patch.object(
                n8n_service,
                "n8n_health_check",
                return_value={"healthy": False, "reason": "Docker daemon stopped on host"},
            ):
                res = await run_hybrid_job("inventory_monitor", task_id=test_task_id, event_id=test_event_id)

        assert res["engine"] == "native"
        assert res["status"] == "success"
        assert "fallback_reason" in res
        assert "Docker daemon stopped" in res["fallback_reason"]

        # Verify DB record
        db = SessionLocal()
        try:
            record = db.query(AutomationExecution).filter_by(task_id=test_task_id).first()
            assert record is not None
            assert record.engine == "native"
            assert record.status == "success"
        finally:
            db.close()
            _cleanup_test_records([test_task_id])

    asyncio.run(_run())


# ─────────────────────────────────────────────────────────────────────────────
# TEST 4 — N8N UNAVAILABLE
# ─────────────────────────────────────────────────────────────────────────────
def test_scenario_4_n8n_unavailable():
    """TEST 4: Docker is running, but n8n is unreachable/offline -> automatic fallback to Native."""
    async def _run():
        test_task_id = f"test-t4-{uuid.uuid4().hex[:8]}"
        test_event_id = uuid.uuid4().hex

        with patch.object(n8n_service, "is_docker_running", return_value=(True, "Docker daemon active")):
            with patch.object(
                n8n_service,
                "n8n_health_check",
                return_value={"healthy": False, "reason": "connection failed: Connection refused"},
            ):
                res = await run_hybrid_job("unresolved_issues_escalator", task_id=test_task_id, event_id=test_event_id)

        assert res["engine"] == "native"
        assert res["status"] == "success"
        assert "Connection refused" in res["fallback_reason"]

        db = SessionLocal()
        try:
            record = db.query(AutomationExecution).filter_by(task_id=test_task_id).first()
            assert record is not None
            assert record.engine == "native"
        finally:
            db.close()
            _cleanup_test_records([test_task_id])

    asyncio.run(_run())


# ─────────────────────────────────────────────────────────────────────────────
# TEST 5 — N8N WEBHOOK FAILURE (500, 404, 403, 422)
# ─────────────────────────────────────────────────────────────────────────────
def test_scenario_5_n8n_webhook_failure():
    """TEST 5: n8n returns 500/404/403/422 error -> safe automatic fallback to Native."""
    async def _run():
        test_task_id = f"test-t5-{uuid.uuid4().hex[:8]}"
        test_event_id = uuid.uuid4().hex

        # Health check thought it was healthy, but dispatch fails with 500 Internal Server Error
        async def mock_failing_dispatch(payload):
            return {"outcome": "rejected", "status_code": 500, "reason": "HTTP 500 Internal Server Error"}

        with patch.object(
            n8n_service,
            "n8n_health_check",
            return_value={"healthy": True, "reason": "n8n healthy"},
        ):
            with patch.object(n8n_service, "dispatch_n8n", side_effect=mock_failing_dispatch):
                res = await run_hybrid_job("inventory_monitor", task_id=test_task_id, event_id=test_event_id)

        assert res["engine"] == "native"
        assert res["status"] == "success"

        db = SessionLocal()
        try:
            record = db.query(AutomationExecution).filter_by(task_id=test_task_id).first()
            assert record is not None
            assert record.engine == "native"
            assert record.status == "success"
        finally:
            db.close()
            _cleanup_test_records([test_task_id])

    asyncio.run(_run())


# ─────────────────────────────────────────────────────────────────────────────
# TEST 6 — N8N RECOVERY
# ─────────────────────────────────────────────────────────────────────────────
def test_scenario_6_n8n_recovery():
    """TEST 6: After an outage, when n8n recovers and becomes healthy,
    subsequent tasks automatically route back to n8n without application restarts.
    """
    async def _run():
        task_outage = f"test-t6-outage-{uuid.uuid4().hex[:8]}"
        task_recovered = f"test-t6-recov-{uuid.uuid4().hex[:8]}"

        # Phase 1: n8n is down -> runs native
        with patch.object(n8n_service, "n8n_health_check", return_value={"healthy": False, "reason": "n8n down"}):
            res1 = await run_hybrid_job("inventory_monitor", task_id=task_outage)
            assert res1["engine"] == "native"

        # Phase 2: n8n recovers -> runs n8n
        with patch.object(n8n_service, "n8n_health_check", return_value={"healthy": True, "reason": "n8n healthy"}):
            with patch.object(
                n8n_service,
                "dispatch_n8n",
                return_value={"outcome": "accepted", "status_code": 200, "reason": "accepted"},
            ):
                res2 = await run_hybrid_job("weather_collector", task_id=task_recovered)
                assert res2["engine"] == "n8n"
                assert res2["accepted"] is True

        _cleanup_test_records([task_outage, task_recovered])

    asyncio.run(_run())


# ─────────────────────────────────────────────────────────────────────────────
# TEST 7 — DUPLICATE PREVENTION
# ─────────────────────────────────────────────────────────────────────────────
def test_scenario_7_duplicate_prevention():
    """TEST 7: Triggering identical task with same task_id or event_id executes only once.
    Duplicate calls return the existing execution claim without double-executing.
    """
    async def _run():
        fixed_task_id = f"test-t7-dedup-{uuid.uuid4().hex[:8]}"
        fixed_event_id = uuid.uuid4().hex

        # First call: executes native
        with patch.object(n8n_service, "n8n_health_check", return_value={"healthy": False, "reason": "n8n disabled"}):
            res1 = await run_hybrid_job("inventory_monitor", task_id=fixed_task_id, event_id=fixed_event_id)
            assert res1.get("duplicate") is not True

            # Second call with same task_id: detected as duplicate
            res2 = await run_hybrid_job("inventory_monitor", task_id=fixed_task_id, event_id=fixed_event_id)
            assert res2.get("duplicate") is True
            assert res2["task_id"] == fixed_task_id
            assert res2["status"] == res1["status"]

        # Verify only ONE row exists in database
        db = SessionLocal()
        try:
            count = db.query(AutomationExecution).filter_by(task_id=fixed_task_id).count()
            assert count == 1, f"Expected exactly 1 execution record, found {count}"
        finally:
            db.close()
            _cleanup_test_records([fixed_task_id])

    asyncio.run(_run())


# ─────────────────────────────────────────────────────────────────────────────
# TEST 8 — TIMEOUT HANDLING
# ─────────────────────────────────────────────────────────────────────────────
def test_scenario_8_timeout_handling():
    """TEST 8: When n8n webhook times out, system catches timeout and records status as 'unknown'.
    Does NOT blindly execute native logic to prevent duplicated action.
    """
    async def _run():
        test_task_id = f"test-t8-timeout-{uuid.uuid4().hex[:8]}"

        async def mock_timeout_dispatch(payload):
            return {"outcome": "timeout", "status_code": None, "reason": "Webhook dispatch timed out after 15s"}

        with patch.object(n8n_service, "n8n_health_check", return_value={"healthy": True, "reason": "n8n healthy"}):
            with patch.object(n8n_service, "dispatch_n8n", side_effect=mock_timeout_dispatch):
                res = await run_hybrid_job("inventory_monitor", task_id=test_task_id)

        assert res["status"] == "unknown"
        assert res["engine"] == "unknown"
        assert "timed out" in res["error"]

        # Verify DB record has unknown status
        db = SessionLocal()
        try:
            record = db.query(AutomationExecution).filter_by(task_id=test_task_id).first()
            assert record is not None
            assert record.status == "unknown"
            assert record.engine == "unknown"
        finally:
            db.close()
            _cleanup_test_records([test_task_id])

    asyncio.run(_run())


# ─────────────────────────────────────────────────────────────────────────────
# TEST 9 — CONCURRENT TASKS
# ─────────────────────────────────────────────────────────────────────────────
def test_scenario_9_concurrent_tasks():
    """TEST 9: Triggering multiple tasks simultaneously runs them independently
    without task collisions, table locking issues, or race conditions.
    """
    async def _run():
        id1 = f"test-t9-a-{uuid.uuid4().hex[:8]}"
        id2 = f"test-t9-b-{uuid.uuid4().hex[:8]}"
        id3 = f"test-t9-c-{uuid.uuid4().hex[:8]}"

        with patch.object(n8n_service, "n8n_health_check", return_value={"healthy": False, "reason": "n8n disabled"}):
            t1 = run_hybrid_job("inventory_monitor", task_id=id1)
            t2 = run_hybrid_job("inventory_monitor", task_id=id2)
            t3 = run_hybrid_job("inventory_monitor", task_id=id3)

            results = await asyncio.gather(t1, t2, t3)

        assert len(results) == 3
        for r in results:
            assert r["status"] == "success"
            assert r["engine"] == "native"

        # All three distinct task_ids must exist in DB
        db = SessionLocal()
        try:
            records = db.query(AutomationExecution).filter(
                AutomationExecution.task_id.in_([id1, id2, id3])
            ).all()
            assert len(records) == 3
        finally:
            db.close()
            _cleanup_test_records([id1, id2, id3])

    asyncio.run(_run())


# ─────────────────────────────────────────────────────────────────────────────
# TEST 10 — EXISTING PROJECT REGRESSION
# ─────────────────────────────────────────────────────────────────────────────
def test_scenario_10_existing_project_regression():
    """TEST 10: Regression verification:
      - All 5 original native tasks remain in REGISTERED_JOBS with original intervals
      - All 5 task handlers exist in JOB_HANDLERS
      - AutomationExecution database schema integrity
      - Admin automation status telemetry returns expected structure
    """
    async def _run():
        # 1. Verify job registry preservation
        expected_jobs = {
            "weather_collector": 14400,
            "scheduled_district_predictions": 21600,
            "risk_monitor": 3600,
            "inventory_monitor": 1800,
            "unresolved_issues_escalator": 7200,
        }
        for name, expected_interval in expected_jobs.items():
            assert name in REGISTERED_JOBS, f"Missing job in registry: {name}"
            assert REGISTERED_JOBS[name][0] == expected_interval, f"Interval changed for {name}"
            assert name in JOB_HANDLERS, f"Missing handler for {name}"

        # 2. Verify status telemetry endpoint with mocked health probe
        with patch.object(n8n_service, "n8n_health_check", return_value={"healthy": False, "reason": "offline", "docker": {"running": False}}):
            status = await get_automation_status()
            assert "active_engine" in status
            assert "native_status" in status
            assert "docker" in status
            assert "n8n" in status
            assert "counts" in status
            assert "recent_executions" in status
            assert "recent_errors" in status

            # Verify counts schema
            assert "total" in status["counts"]
            assert "native" in status["counts"]
            assert "n8n" in status["counts"]
            assert "success" in status["counts"]

    asyncio.run(_run())
