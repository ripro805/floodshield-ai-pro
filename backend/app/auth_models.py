"""
The `users` table. One table is enough for all six roles from the original
spec -- role is just a column, not a separate table per role -- since every
role shares the same shape (email, password, name) and only differs in what
they're allowed to call (enforced in app/auth_deps.py, not here).
"""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class UserRole(str, enum.Enum):
    citizen = "citizen"
    health_worker = "health_worker"
    hospital = "hospital"
    ngo = "ngo"
    government = "government"
    admin = "admin"


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    role = Column(SQLEnum(UserRole), nullable=False, default=UserRole.citizen)
    district = Column(String, nullable=True)  # relevant for hospital/health_worker/NGO accounts
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
