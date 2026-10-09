"""
The `weekly_history` table stores one row per district per week, recording
the actual observed environmental + case-count data used to feed the
LSTM forecast model (Model 3).

Design notes:
- `week_ending` is a date (not datetime) -- one row per district per week,
  the Sunday ending that ISO week.
- All environmental fields mirror WeeklyObservation from schemas.py exactly,
  so the forecast router can read rows straight into its expected shape.
- Rows are inserted by admin/operational users (or an automated ingestion
  script); regular citizens can only read.
- Unique constraint on (district, week_ending) prevents duplicate entries.
"""
import uuid
from datetime import datetime, timezone, date

from sqlalchemy import Column, String, Float, Date, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class WeeklyHistory(Base):
    __tablename__ = "weekly_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    district = Column(String, nullable=False, index=True)
    week_ending = Column(Date, nullable=False, index=True)

    # --- Feature columns match WeeklyObservation in schemas.py exactly ---
    weekly_cases = Column(Float, nullable=False)
    rainfall_mm = Column(Float, nullable=False)
    temperature_c = Column(Float, nullable=False)
    flood_depth_cm = Column(Float, nullable=False)
    sanitation_score = Column(Float, nullable=False)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("district", "week_ending", name="uq_district_week"),
    )
