"""Audit trail for model predictions used by reports and alert review."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, JSON, String
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class PredictionHistory(Base):
    __tablename__ = "prediction_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    model_name = Column(String(40), nullable=False, index=True)
    district = Column(String(120), nullable=True, index=True)
    risk_level = Column(String(20), nullable=True, index=True)
    probability = Column(Float, nullable=True)
    input_data = Column(JSON, nullable=False)
    output_data = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
