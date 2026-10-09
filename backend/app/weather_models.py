"""Durable observations collected by the scheduled weather refresh."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, String
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class WeatherObservation(Base):
    __tablename__ = "weather_observations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    location = Column(String(120), nullable=False, index=True)
    observed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    temperature = Column(Float, nullable=False)
    humidity = Column(Float, nullable=False)
    rainfall = Column(Float, nullable=False)
    river_level_m = Column(Float, nullable=True)
    water_quality_index = Column(Float, nullable=True)
    data_source = Column(String(20), nullable=False)
