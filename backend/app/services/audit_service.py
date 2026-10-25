"""backend/app/services/audit_service.py
-----------------------------------
Centralized, immutable audit event logging for operational actions:
- Inventory adjustments
- Resource allocations & requisitions
- Official alert publications
- Campaign lifecycle updates
- Hospital capacity alterations
- Role promotions / administrative actions
"""
from __future__ import annotations

import logging
from typing import Any, Optional
from sqlalchemy.orm import Session

from app.auth_models import User
from app.operation_models import AuditEvent

logger = logging.getLogger(__name__)


def log_audit_event(
    db: Session,
    user: Optional[User] = None,
    action: str = "",
    resource_type: str = "",
    resource_id: Optional[str] = None,
    before_state: Optional[dict[str, Any]] = None,
    after_state: Optional[dict[str, Any]] = None,
    details: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_email: Optional[str] = None,
    user_role: Optional[str] = None,
) -> Optional[AuditEvent]:
    """Records an audit event in the `audit_events` table.

    Safe: If audit logging fails for any reason, it logs a warning and does
    not crash the calling transaction.
    """
    try:
        email = user.email if user else (user_email or "system")
        if user:
            role_val = user.role.value if hasattr(user.role, "value") else str(user.role)
        else:
            role_val = str(user_role or "system")

        event = AuditEvent(
            user_email=email,
            user_role=role_val,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id is not None else None,
            before_state=before_state,
            after_state=after_state,
            details=details,
            ip_address=ip_address,
        )
        db.add(event)
        # Flush so the event ID is populated if needed, but leave commit to caller
        db.flush()
        return event
    except Exception as exc:
        logger.warning("Failed to record audit event (%s on %s): %s", action, resource_type, exc)
        return None
