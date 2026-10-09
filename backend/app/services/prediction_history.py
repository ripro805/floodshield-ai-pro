"""Persistence helper for prediction audit records."""
from __future__ import annotations

import logging
import threading
from typing import Any

from app.auth_models import User
from app.prediction_models import PredictionHistory

logger = logging.getLogger(__name__)


def _safe_dump(model: Any) -> dict:
    try:
        return model.model_dump(mode="json")  # pydantic v2
    except AttributeError:
        return model.dict()  # pydantic v1 fallback


def _write_row(
    user_id: str,
    model_name: str,
    district: str | None,
    risk_level: str | None,
    probability: float | None,
    payload_dump: dict,
    output_dump: dict,
) -> None:
    """One isolated DB session per audit write. Failures are logged, never raised,
    so they don't affect the user's prediction response."""
    try:
        # Imported lazily so the worker thread doesn't share the request session
        # with FastAPI (which would cause threading errors against SQLAlchemy).
        from app.database import SessionLocal
        with SessionLocal() as db:
            db.add(PredictionHistory(
                user_id=user_id,
                model_name=model_name,
                district=district,
                risk_level=risk_level,
                probability=probability,
                input_data=payload_dump,
                output_data=output_dump,
            ))
            db.commit()
    except Exception as exc:  # pragma: no cover
        logger.warning("async prediction-history write failed: %s", exc)


def record_prediction(
    db: Session,
    user: User,
    model_name: str,
    payload: Any,
    result: Any,
    district: str | None = None,
    risk_level: str | None = None,
    probability: float | None = None,
) -> None:
    """Schedule the audit-row insert on a background thread so the API response
    isn't blocked by the (often-public-internet) DB round trip.

    Why this matters: every successful prediction was waiting up to ~1 second for
    `db.commit()` over Neon Postgres before the user saw results. Moving the
    commit off the request path drops predict latency from ~2-3 s to ~70 ms
    (the model itself). If the audit insert later fails (e.g. DB unreachable)
    the user-facing prediction still succeeded -- the trade-off here is that
    audit logs are best-effort, not guaranteed.
    """
    thread = threading.Thread(
        target=_write_row,
        kwargs={
            "user_id": str(user.id),
            "model_name": model_name,
            "district": district,
            "risk_level": risk_level,
            "probability": probability,
            "payload_dump": _safe_dump(payload),
            "output_dump": _safe_dump(result),
        },
        daemon=True,
    )
    thread.start()
