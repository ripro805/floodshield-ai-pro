"""
The `chat_messages` table stores the conversational history for the chatbot.
Allows the chatbot to maintain context across multiple turns and enables
future analytics/moderation features.
"""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, Enum as SQLEnum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class ChatIntentType(str, enum.Enum):
    disease_info = "disease_info"
    flood_safety = "flood_safety"
    hospital_info = "hospital_info"
    emergency = "emergency"
    incident_report = "incident_report"
    general = "general"


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    conversation_id = Column(String, nullable=False, index=True)
    role = Column(String, nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    detected_intent = Column(SQLEnum(ChatIntentType), nullable=True)
    referenced_disease = Column(String, nullable=True)
    used_live_data = Column(String, default="false")  # "true" or "false" for JSON compatibility
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
