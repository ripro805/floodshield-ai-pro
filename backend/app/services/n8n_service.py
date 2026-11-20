"""backend/app/services/n8n_service.py
-----------------------------------
Centralized n8n Webhook Integration and Docker/n8n Availability Detection Service.

Provides:
  - is_docker_running(): Dynamic detection of Docker daemon status
  - n8n_health_check(): Cached health & connectivity probe for the n8n endpoint
  - dispatch_n8n(): Structured event delivery with timeout & outcome classification
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any, Tuple

import httpx

from app.config import (
    N8N_ENABLED,
    N8N_HEALTH_CACHE_SECONDS,
    N8N_TIMEOUT,
    N8N_WEBHOOK_URL,
    N8N_WEBHOOK_HEADER_NAME,
    N8N_WEBHOOK_SECRET,
)

logger = logging.getLogger(__name__)

# Cache for Docker availability probe
_docker_cache: dict[str, Any] = {
    "running": None,
    "status": "not checked",
    "checked_at": None,
}

# Cache for n8n health probe
_health_cache: dict[str, Any] = {
    "healthy": False,
    "checked_at": None,
    "reason": "not checked",
    "status_code": None,
    "docker": {"running": False, "status": "not checked"},
}


def is_docker_running(force: bool = False) -> Tuple[bool, str]:
    """Dynamically determine whether Docker daemon is active and responsive.

    Checks container indicators, host daemon sockets/pipes, and CLI info.
    Supports MOCK_DOCKER_RUNNING environment variable for test environments.
    """
    now = datetime.now(timezone.utc)
    if not force and _docker_cache["checked_at"] is not None:
        age = (now - _docker_cache["checked_at"]).total_seconds()
        if age < N8N_HEALTH_CACHE_SECONDS and _docker_cache["running"] is not None:
            return _docker_cache["running"], _docker_cache["status"]

    # 1. Environment simulation override (for deterministic integration testing)
    mock_env = os.getenv("MOCK_DOCKER_RUNNING")
    if mock_env is not None:
        running = mock_env.strip().lower() in ("1", "true", "yes", "on")
        status = "Docker daemon running (simulated)" if running else "Docker daemon stopped (simulated)"
        _docker_cache.update({"running": running, "status": status, "checked_at": now})
        return running, status

    # 2. Check if currently running inside a Docker container
    if os.path.exists("/.dockerenv") or os.getenv("RUNNING_IN_DOCKER") == "true":
        status = "Running inside Docker container"
        _docker_cache.update({"running": True, "status": status, "checked_at": now})
        return True, status

    # 3. Check CLI binary responsiveness
    docker_bin = shutil.which("docker")
    if docker_bin:
        try:
            res = subprocess.run(
                [docker_bin, "info", "--format", "{{.ServerVersion}}"],
                capture_output=True,
                text=True,
                timeout=1.8,
            )
            if res.returncode == 0:
                ver = res.stdout.strip()
                status = f"Docker daemon active (v{ver})" if ver else "Docker daemon active"
                _docker_cache.update({"running": True, "status": status, "checked_at": now})
                return True, status
            status = "Docker CLI present but daemon is stopped"
            _docker_cache.update({"running": False, "status": status, "checked_at": now})
            return False, status
        except Exception:
            pass  # Fall through to socket check

    # 4. Check named pipe (Windows) or UNIX domain socket (Linux/macOS)
    if sys.platform == "win32":
        if os.path.exists(r"\\.\pipe\docker_engine"):
            status = "Docker daemon active (named pipe active)"
            _docker_cache.update({"running": True, "status": status, "checked_at": now})
            return True, status
    else:
        if os.path.exists("/var/run/docker.sock") and os.access("/var/run/docker.sock", os.R_OK):
            status = "Docker daemon active (socket active)"
            _docker_cache.update({"running": True, "status": status, "checked_at": now})
            return True, status

    status = "Docker daemon not running on host"
    _docker_cache.update({"running": False, "status": status, "checked_at": now})
    return False, status


async def n8n_health_check(force: bool = False) -> dict:
    """Probe the configured n8n webhook without leaking secrets or URLs.

    Distinguishes:
      - Docker availability
      - Endpoint reachability
      - Authentication validation
      - Workflow acceptance vs rejection
    """
    now = datetime.now(timezone.utc)
    if not force and _health_cache["checked_at"] is not None:
        age = (now - _health_cache["checked_at"]).total_seconds()
        if age < N8N_HEALTH_CACHE_SECONDS:
            return dict(_health_cache)

    docker_running, docker_status = is_docker_running(force=force)

    # If disabled by configuration
    if not N8N_ENABLED:
        result = {
            "healthy": False,
            "checked_at": now,
            "reason": "n8n integration disabled (N8N_ENABLED=false)",
            "status_code": None,
            "docker": {"running": docker_running, "status": docker_status},
        }
        _health_cache.clear()
        _health_cache.update(result)
        return dict(result)

    # If webhook URL is missing
    if not N8N_WEBHOOK_URL:
        result = {
            "healthy": False,
            "checked_at": now,
            "reason": "n8n webhook URL not configured",
            "status_code": None,
            "docker": {"running": docker_running, "status": docker_status},
        }
        _health_cache.clear()
        _health_cache.update(result)
        return dict(result)

    # Probe the configured webhook endpoint
    headers = {}
    if N8N_WEBHOOK_SECRET:
        headers[N8N_WEBHOOK_HEADER_NAME] = N8N_WEBHOOK_SECRET

    probe_payload = {
        "task_id": "health-check",
        "event_id": "health-check",
        "event_type": "health_check",
        "event": "health_check",
        "timestamp": now.isoformat(),
        "source": "floodshield-backend",
        "data": {"ping": True},
    }

    try:
        async with httpx.AsyncClient(timeout=min(N8N_TIMEOUT, 5.0), follow_redirects=False) as client:
            response = await client.post(N8N_WEBHOOK_URL, headers=headers, json=probe_payload)

        status_code = response.status_code
        if 200 <= status_code < 300:
            result = {
                "healthy": True,
                "checked_at": now,
                "reason": "webhook accepted request",
                "status_code": status_code,
                "docker": {"running": docker_running, "status": docker_status},
            }
        elif status_code in (401, 403):
            result = {
                "healthy": False,
                "checked_at": now,
                "reason": f"webhook authentication failed (HTTP {status_code} - verify N8N_WEBHOOK_SECRET)",
                "status_code": status_code,
                "docker": {"running": docker_running, "status": docker_status},
            }
        elif status_code in (404, 410):
            result = {
                "healthy": False,
                "checked_at": now,
                "reason": f"webhook endpoint not found or workflow inactive (HTTP {status_code})",
                "status_code": status_code,
                "docker": {"running": docker_running, "status": docker_status},
            }
        elif status_code == 422:
            result = {
                "healthy": False,
                "checked_at": now,
                "reason": "workflow rejected health payload format (HTTP 422)",
                "status_code": status_code,
                "docker": {"running": docker_running, "status": docker_status},
            }
        else:
            result = {
                "healthy": False,
                "checked_at": now,
                "reason": f"webhook returned HTTP {status_code}",
                "status_code": status_code,
                "docker": {"running": docker_running, "status": docker_status},
            }

    except httpx.TimeoutException:
        result = {
            "healthy": False,
            "checked_at": now,
            "reason": f"webhook response timed out after {min(N8N_TIMEOUT, 5.0)}s",
            "status_code": None,
            "docker": {"running": docker_running, "status": docker_status},
        }
    except httpx.HTTPError as exc:
        logger.warning("n8n health probe failed: %s", type(exc).__name__)
        result = {
            "healthy": False,
            "checked_at": now,
            "reason": f"webhook connection failed ({type(exc).__name__})",
            "status_code": None,
            "docker": {"running": docker_running, "status": docker_status},
        }

    _health_cache.clear()
    _health_cache.update(result)
    return dict(result)


async def dispatch_n8n(payload: dict) -> dict:
    """Dispatch an event payload to the n8n webhook and classify the outcome.

    Outcomes:
      - 'accepted': HTTP 2xx
      - 'rejected': HTTP 4xx/5xx (safe for native fallback)
      - 'timeout': Request timed out after dispatch (requires UNKNOWN status to prevent duplicate execution)
      - 'connection_error': Host unreachable before transmission
    """
    if not N8N_ENABLED or not N8N_WEBHOOK_URL:
        return {"outcome": "rejected", "reason": "n8n integration not enabled or URL missing"}

    headers = {}
    if N8N_WEBHOOK_SECRET:
        headers[N8N_WEBHOOK_HEADER_NAME] = N8N_WEBHOOK_SECRET

    try:
        async with httpx.AsyncClient(timeout=N8N_TIMEOUT, follow_redirects=False) as client:
            response = await client.post(N8N_WEBHOOK_URL, headers=headers, json=payload)

        status_code = response.status_code
        if 200 <= status_code < 300:
            return {"outcome": "accepted", "status_code": status_code}

        if status_code in (401, 403):
            return {
                "outcome": "rejected",
                "reason": f"authentication failed (HTTP {status_code})",
                "status_code": status_code,
            }

        if status_code in (404, 410):
            return {
                "outcome": "rejected",
                "reason": f"workflow unavailable (HTTP {status_code})",
                "status_code": status_code,
            }

        if status_code == 422:
            return {
                "outcome": "rejected",
                "reason": "workflow rejected payload schema (HTTP 422)",
                "status_code": status_code,
            }

        return {
            "outcome": "rejected",
            "reason": f"webhook returned HTTP {status_code}",
            "status_code": status_code,
        }

    except httpx.TimeoutException:
        # Crucial: Request dispatched, server didn't answer within timeout.
        # Outcome is uncertain -- do not blindly double-execute natively!
        return {
            "outcome": "timeout",
            "reason": f"dispatch timed out after {N8N_TIMEOUT}s (execution outcome unknown)",
        }
    except httpx.HTTPError as exc:
        return {
            "outcome": "connection_error",
            "reason": f"connection failed: {type(exc).__name__}",
        }
