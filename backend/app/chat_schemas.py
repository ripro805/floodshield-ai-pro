"""
Pydantic schemas for chatbot endpoints.
"""
from typing import Optional, List
from enum import Enum

from pydantic import BaseModel, Field


class LanguageEnum(str, Enum):
    bn = "bn"
    en = "en"
    auto = "auto"


class ChatIntentEnum(str, Enum):
    disease_info = "disease_info"
    flood_safety = "flood_safety"
    hospital_info = "hospital_info"
    emergency = "emergency"
    incident_report = "incident_report"
    general = "general"


class SeverityEnum(str, Enum):
    low = "Low"
    medium = "Medium"
    high = "High"
    critical = "Critical"


class ActionType(str, Enum):
    navigate = "navigate"
    call_endpoint = "call_endpoint"
    emergency_call = "emergency_call"


class SuggestedAction(BaseModel):
    label: str
    action_type: ActionType
    target: str


class UiAction(BaseModel):
    """Server-validated UI action emitted by the agentic assistant.

    Frontend MUST validate the type against a whitelist before executing.
    """
    type: str = Field(
        ...,
        description=(
            "navigate | select_district | run_flood_check | run_full_assessment "
            "| open_satellite_view | open_alerts | open_reports | open_hospital_resources | open_hospital_directory"
        ),
    )
    params: dict = Field(default_factory=dict)


class ChatMessageRequest(BaseModel):
    message: str = Field(..., description="The user's message in Bangla or English")
    conversation_id: Optional[str] = Field(None, description="Null starts a new conversation")
    language: LanguageEnum = Field(LanguageEnum.auto, description="Message language (auto-detect or specify)")


class ChatMessageResponse(BaseModel):
    conversation_id: str
    reply: str
    detected_intent: ChatIntentEnum
    referenced_disease: Optional[str] = None
    used_live_data: bool
    suggested_actions: List[SuggestedAction] = []
    # New (tool-using agent):
    ui_actions: List[UiAction] = Field(default_factory=list)
    tools_used: List[str] = Field(default_factory=list)
    data_sources: List[str] = Field(default_factory=list)


class ReportIncidentRequest(BaseModel):
    text: str = Field(..., description="Free-text description in Bangla or English")
    district: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class ReportIncidentResponse(BaseModel):
    label: str
    severity: SeverityEnum
    recommended_action: str
    alert_created: bool