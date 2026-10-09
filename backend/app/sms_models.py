"""Persisted SMS alert subscriptions."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class SmsSubscription(Base):
    __tablename__ = "sms_subscriptions"
    __table_args__ = (UniqueConstraint("user_id", name="uq_sms_subscription_user"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    phone_number = Column(String(32), nullable=False)
    district = Column(String(120), nullable=True)
    risk_threshold = Column(String(16), nullable=False, default="High")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
