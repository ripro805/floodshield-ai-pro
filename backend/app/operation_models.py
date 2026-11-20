"""backend/app/operation_models.py
---------------------------------
Operational models supporting the multi-role disaster and healthcare management layer:
1. Hospital Inventory & Stock Transactions (dynamic multi-item catalog, batch/expiry, audit history)
2. NGO Relief Campaigns, Inventory, and Distribution Tasks
3. Health Worker Field Tasks & Household Visit Logs
4. Government Resource Requisition, Allocation & Bilingual Official Alerts
5. Shared Audit Event Trail
6. Background Automation Job Execution Registry
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, date
from typing import Optional

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Date, DateTime, Text,
    ForeignKey, Index, JSON, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


# ══════════════════════════════════════════════════════════════════════════
# 1. Hospital Dynamic Inventory & Transactions
# ══════════════════════════════════════════════════════════════════════════

class HospitalInventoryItem(Base):
    __tablename__ = "hospital_inventory_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    item_name = Column(String(150), nullable=False, index=True)
    category = Column(String(60), nullable=False, default="medicine")  # medicine | iv_fluid | consumable | equipment | protective_gear
    unit = Column(String(30), nullable=False, default="packet")       # packet | bag | box | vial | tablet | unit
    current_stock = Column(Integer, nullable=False, default=0)
    min_threshold = Column(Integer, nullable=False, default=20)
    batch_number = Column(String(60), nullable=True)
    expiry_date = Column(Date, nullable=True)
    storage_location = Column(String(100), nullable=True)
    is_critical_shortage = Column(Boolean, nullable=False, default=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("hospital_id", "item_name", "batch_number", name="uq_hosp_item_batch"),
        Index("ix_hosp_inv_lookup", "hospital_id", "category"),
    )


class HospitalStockTransaction(Base):
    __tablename__ = "hospital_stock_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id = Column(UUID(as_uuid=True), ForeignKey("hospital_inventory_items.id", ondelete="CASCADE"), nullable=False, index=True)
    transaction_type = Column(String(30), nullable=False)  # received | distributed | consumed | damaged | expired | adjustment
    quantity = Column(Integer, nullable=False)            # positive for received, negative or unsigned with type
    previous_stock = Column(Integer, nullable=False)
    new_stock = Column(Integer, nullable=False)
    batch_number = Column(String(60), nullable=True)
    notes = Column(Text, nullable=True)
    performed_by_email = Column(String(120), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


# ══════════════════════════════════════════════════════════════════════════
# 2. NGO Operations: Campaigns, Inventory, Distribution
# ══════════════════════════════════════════════════════════════════════════

class ReliefCampaign(Base):
    __tablename__ = "relief_campaigns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_name = Column(String(150), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    target_districts = Column(String(300), nullable=False, index=True)  # e.g. "Feni, Sylhet"
    target_upazilas = Column(String(500), nullable=True)
    target_population = Column(Integer, nullable=False, default=1000)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    team_lead_name = Column(String(120), nullable=True)
    team_lead_contact = Column(String(50), nullable=True)
    status = Column(String(30), nullable=False, default="active")  # draft | active | paused | completed | archived
    created_by_email = Column(String(120), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class NgoInventoryItem(Base):
    __tablename__ = "ngo_inventory_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_name = Column(String(150), nullable=False, index=True)
    item_name = Column(String(150), nullable=False, index=True)
    category = Column(String(60), nullable=False, default="dry_food")  # dry_food | clean_water | water_purification | medical_kit | hygiene_kit | shelter_blanket
    unit = Column(String(30), nullable=False, default="packet")       # packet | kg | carton | kit | piece | bottle
    current_stock = Column(Integer, nullable=False, default=0)
    min_threshold = Column(Integer, nullable=False, default=50)
    warehouse_location = Column(String(150), nullable=True)
    batch_number = Column(String(60), nullable=True)
    expiry_date = Column(Date, nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("organization_name", "item_name", "batch_number", name="uq_ngo_item_batch"),
    )


class NgoStockTransaction(Base):
    __tablename__ = "ngo_stock_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_name = Column(String(150), nullable=False, index=True)
    item_id = Column(UUID(as_uuid=True), ForeignKey("ngo_inventory_items.id", ondelete="CASCADE"), nullable=False, index=True)
    transaction_type = Column(String(30), nullable=False)  # received | dispatched | damaged | expired | adjustment
    quantity = Column(Integer, nullable=False)
    previous_stock = Column(Integer, nullable=False)
    new_stock = Column(Integer, nullable=False)
    recipient_location = Column(String(150), nullable=True)
    notes = Column(Text, nullable=True)
    performed_by_email = Column(String(120), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class ReliefDistributionTask(Base):
    __tablename__ = "relief_distribution_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("relief_campaigns.id", ondelete="CASCADE"), nullable=True, index=True)
    organization_name = Column(String(150), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    district = Column(String(120), nullable=False, index=True)
    upazila = Column(String(120), nullable=True)
    union_or_village = Column(String(150), nullable=True)
    planned_supplies = Column(JSON, nullable=True)   # [{"item": "Water Purification Tabs", "qty": 500, "unit": "tablet"}]
    actual_distributed = Column(JSON, nullable=True) # [{"item": "Water Purification Tabs", "qty": 480, "unit": "tablet"}]
    beneficiary_households = Column(Integer, nullable=False, default=0)
    people_reached = Column(Integer, nullable=False, default=0)
    status = Column(String(30), nullable=False, default="planned")  # planned | dispatched | in_transit | completed | incomplete
    assigned_team = Column(String(120), nullable=True)
    notes = Column(Text, nullable=True)
    verified_by_email = Column(String(120), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)


# ══════════════════════════════════════════════════════════════════════════
# 3. Health Worker Field Tasks & Visit Logs
# ══════════════════════════════════════════════════════════════════════════

class FieldTask(Base):
    __tablename__ = "field_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    task_type = Column(String(60), nullable=False, default="outbreak_investigation")  # outbreak_investigation | ors_distribution | water_testing | emergency_triage | vulnerable_check
    district = Column(String(120), nullable=False, index=True)
    upazila = Column(String(120), nullable=True, index=True)
    priority = Column(String(20), nullable=False, default="medium")  # low | medium | high | critical
    status = Column(String(30), nullable=False, default="assigned")  # assigned | accepted | in_progress | completed | cancelled
    assigned_to_email = Column(String(120), nullable=False, index=True)
    assigned_by_email = Column(String(120), nullable=True)
    deadline = Column(DateTime, nullable=True)
    completion_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class FieldVisitLog(Base):
    __tablename__ = "field_visit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    health_worker_email = Column(String(120), nullable=False, index=True)
    district = Column(String(120), nullable=False, index=True)
    upazila = Column(String(120), nullable=True)
    location_name = Column(String(150), nullable=False)
    households_visited = Column(Integer, nullable=False, default=0)
    suspected_cases_count = Column(Integer, nullable=False, default=0)
    suspected_diseases = Column(String(200), nullable=True)  # e.g. "Acute Watery Diarrhoea, Cholera"
    ors_packets_distributed = Column(Integer, nullable=False, default=0)
    water_purification_tablets_distributed = Column(Integer, nullable=False, default=0)
    referrals_count = Column(Integer, nullable=False, default=0)
    urgent_shortage_reported = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


# ══════════════════════════════════════════════════════════════════════════
# 4. Government Requisitions, Allocations & Official Alerts
# ══════════════════════════════════════════════════════════════════════════

class ResourceRequest(Base):
    __tablename__ = "resource_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    requester_email = Column(String(120), nullable=False, index=True)
    requester_role = Column(String(30), nullable=False)  # health_worker | hospital | ngo
    organization_name = Column(String(150), nullable=False)
    district = Column(String(120), nullable=False, index=True)
    upazila = Column(String(120), nullable=True)
    request_type = Column(String(40), nullable=False)    # medicine | iv_fluid | medical_personnel | clean_water | relief_supplies | emergency_evacuation
    requested_items = Column(JSON, nullable=False)       # [{"item": "IV Saline Bags", "quantity": 1000, "unit": "bag"}]
    urgency = Column(String(30), nullable=False, default="urgent")  # normal | urgent | critical_emergency
    justification = Column(Text, nullable=False)
    status = Column(String(30), nullable=False, default="pending")  # pending | under_review | approved | partially_fulfilled | rejected
    allocated_items = Column(JSON, nullable=True)
    reviewer_email = Column(String(120), nullable=True)
    review_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    reviewed_at = Column(DateTime, nullable=True)


class ResourceAllocation(Base):
    __tablename__ = "resource_allocations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id = Column(UUID(as_uuid=True), ForeignKey("resource_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    allocated_by_email = Column(String(120), nullable=False)
    source_depot_or_facility = Column(String(150), nullable=False)
    destination_facility = Column(String(150), nullable=False)
    allocated_items = Column(JSON, nullable=False)
    dispatch_status = Column(String(30), nullable=False, default="pending_dispatch")  # pending_dispatch | dispatched | in_transit | received
    tracking_number = Column(String(60), nullable=True)
    dispatched_at = Column(DateTime, nullable=True)
    received_at = Column(DateTime, nullable=True)
    receipt_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class OfficialAlert(Base):
    __tablename__ = "official_alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title_bn = Column(String(200), nullable=False)
    title_en = Column(String(200), nullable=False)
    message_bn = Column(Text, nullable=False)
    message_en = Column(Text, nullable=False)
    severity = Column(String(30), nullable=False, default="warning")  # advisory | warning | critical | evacuation
    target_districts = Column(String(300), nullable=False, index=True)  # e.g. "Feni, Sylhet, Sunamganj" or "ALL"
    status = Column(String(30), nullable=False, default="draft")       # draft | approved | published | cancelled
    approved_by_email = Column(String(120), nullable=True)
    published_by_email = Column(String(120), nullable=True)
    published_at = Column(DateTime, nullable=True, index=True)
    expires_at = Column(DateTime, nullable=True)
    channel = Column(String(30), nullable=False, default="in_app")     # in_app | sms | both
    sent_sms_count = Column(Integer, nullable=False, default=0)
    created_by_email = Column(String(120), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ══════════════════════════════════════════════════════════════════════════
# 5. Shared Audit Event Trail
# ══════════════════════════════════════════════════════════════════════════

class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_email = Column(String(120), nullable=False, index=True)
    user_role = Column(String(30), nullable=False)
    action = Column(String(60), nullable=False, index=True)  # create | update | delete | approve | allocate | publish | status_change
    resource_type = Column(String(60), nullable=False, index=True)  # hospital_inventory | relief_campaign | field_task | resource_request | official_alert | user_role
    resource_id = Column(String(100), nullable=True)
    before_state = Column(JSON, nullable=True)
    after_state = Column(JSON, nullable=True)
    details = Column(Text, nullable=True)
    ip_address = Column(String(60), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


# ══════════════════════════════════════════════════════════════════════════
# 6. Background Automation Job Execution Registry
# ══════════════════════════════════════════════════════════════════════════

class AutomationJob(Base):
    __tablename__ = "automation_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(String(250), nullable=True)
    interval_seconds = Column(Integer, nullable=False, default=3600)
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True)
    status = Column(String(30), nullable=False, default="idle")  # idle | running | success | failed
    last_error = Column(Text, nullable=True)
    last_duration_seconds = Column(Float, nullable=True)
    total_runs = Column(Integer, nullable=False, default=0)
    success_runs = Column(Integer, nullable=False, default=0)
    failure_runs = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class AutomationExecution(Base):
    __tablename__ = "automation_executions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(String(120), unique=True, nullable=False, index=True)
    event_id = Column(String(120), unique=True, nullable=False, index=True)
    job_name = Column(String(100), nullable=False, index=True)
    engine = Column(String(30), nullable=False)  # n8n | native | unknown
    status = Column(String(30), nullable=False)  # pending | running | success | failed | timeout | unknown
    result = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    completed_at = Column(DateTime, nullable=True)

