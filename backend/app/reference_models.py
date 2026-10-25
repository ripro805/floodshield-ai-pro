"""
Persistent reference-data tables.

Everything here is read-mostly data that ships with the project
(climate / hospital / community reports / medical knowledge / locations
/ satellite exports).  Storing it in the DB rather than shipping it as
xlsx/csv/pkl/geojson files in the repo means:

1. Local dev, Docker, Railway/Render, and any future deploy host all
   see identical data (no "did you remember to copy data/ to the
   container?" bug).
2. Reads go through the same connection pool as user-facing data.
3. We can update reference rows in place (admin tooling) without
   redeploying model artifacts.

Tables:
- locations             : canonical (district, upazila) pairs
- districts             : canonical 64-district table (FK target for
                          hospitals.district_id; stores bbox + centroid)
- district_env          : latest observed per-district environmental readings
                          (one row per district; supersedes water_risk_dataset
                          / climate_dataset lookups)
- hospitals             : one row per hospital facility
- district_hospital_agg : one row per district -- denormalised aggregates the
                          Model 6 / risk-all-districts endpoints consume
- knowledge_articles    : medical grounding corpus (superset of the embedded
                          MEDICAL_KNOWLEDGE_BASE string)
- community_reports     : 10k Bengali community-report rows
- satellite_extents     : per-district Sentinel-1 GeoJSON payloads + labels
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Float, Integer, Date, DateTime, JSON, Text,
    UniqueConstraint, Index, ForeignKey,
)
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector

from app.database import Base


# ──────────────────────────────────────────────────────────────────────
# Locations
# ──────────────────────────────────────────────────────────────────────
class Location(Base):
    __tablename__ = "locations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    district = Column(String(120), nullable=False, index=True)
    upazila = Column(String(120), nullable=True, index=True)
    kind = Column(String(20), nullable=False, default="upazila")  # district | upazila
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("district", "upazila", "kind", name="uq_location_district_upazila_kind"),
        Index("ix_locations_district_lower", "district"),
    )


# ──────────────────────────────────────────────────────────────────────
# Canonical Bangladesh districts (the 64 from the BB government gazette).
# FK target for `hospitals.district_id`.  Stores the bbox + centroid
# that the seeder and /hospitals/nearby both use to keep regenerated
# hospital coordinates inside the correct district and to validate that
# a /nearby query point falls inside Bangladesh.
# ──────────────────────────────────────────────────────────────────────
class District(Base):
    __tablename__ = "districts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Canonical English name, e.g. "Barishal" (NOT the legacy "Barisal"
    # spelling; seed scripts normalize legacy spellings before insert).
    name = Column(String(120), nullable=False, unique=True, index=True)
    # Bangla name from the canonical EN_TO_BN map.  Optional so a future
    # district with no Bangla translation still inserts cleanly.
    name_bn = Column(String(120), nullable=True)
    # Centroid (used to deterministically regenerate hospital coords and
    # to validate /hospitals/nearby query points fall inside Bangladesh).
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    # Loose bounding box (min_lat, max_lat, min_lng, max_lng) the seeder
    # uses to keep regenerated hospital coordinates inside the district.
    bbox_min_lat = Column(Float, nullable=True)
    bbox_max_lat = Column(Float, nullable=True)
    bbox_min_lng = Column(Float, nullable=True)
    bbox_max_lng = Column(Float, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ──────────────────────────────────────────────────────────────────────
# Per-district latest environmental observation
# ──────────────────────────────────────────────────────────────────────
class DistrictEnv(Base):
    __tablename__ = "district_env"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    district = Column(String(120), nullable=False, unique=True, index=True)
    observed_on = Column(Date, nullable=False)
    season = Column(String(20), nullable=True)
    rainfall_mm = Column(Float, nullable=True)
    temperature_c = Column(Float, nullable=True)
    humidity_percent = Column(Float, nullable=True)
    river_level_m = Column(Float, nullable=True)
    flood_depth_cm = Column(Float, nullable=True)
    water_quality_index = Column(Float, nullable=True)
    population_density = Column(Float, nullable=True)
    sanitation_score = Column(Float, nullable=True)
    elevation_m = Column(Float, nullable=True)
    contamination_risk = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ──────────────────────────────────────────────────────────────────────
# Hospitals (raw rows) and district aggregates (the columns the
# existing /recommend and /risk/all-districts endpoints already consume)
# ──────────────────────────────────────────────────────────────────────
class Hospital(Base):
    __tablename__ = "hospitals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    # `district` (string) is the legacy column /recommend + seed_reference
    # still use.  `district_id` is the new FK the directory feature uses
    # for joins + uniqueness.  Both are populated; the seed keeps them
    # in lockstep.
    district = Column(String(120), nullable=False, index=True)
    district_id = Column(
        UUID(as_uuid=True),
        ForeignKey("districts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    hospital_type = Column(String(60), nullable=True)
    upazila = Column(String(120), nullable=True)
    address = Column(String(500), nullable=True)
    # Phone is intentionally nullable -- we never fabricate a phone number
    # for seed rows.  The UI hides the field when null and falls back to
    # the national emergency number (999) for emergency actions.
    phone = Column(String(40), nullable=True)
    beds = Column(Integer, nullable=False, default=0)
    beds_occupied = Column(Integer, nullable=True)
    icu_beds_total = Column(Integer, nullable=False, default=0)
    icu_beds_occupied = Column(Integer, nullable=False, default=0)
    isolation_beds_total = Column(Integer, nullable=False, default=0)
    isolation_beds_occupied = Column(Integer, nullable=False, default=0)
    operating_status = Column(String(40), nullable=False, default="normal")  # normal | high_surge | critical_divert | service_interrupted
    emergency_contact = Column(String(60), nullable=True)
    doctors = Column(Integer, nullable=False, default=0)
    nurses = Column(Integer, nullable=False, default=0)
    ors_stock = Column(Integer, nullable=False, default=0)
    iv_saline_stock = Column(Integer, nullable=False, default=0)
    antibiotics_stock = Column(Integer, nullable=False, default=0)
    occupancy_percent = Column(Float, nullable=False, default=0.0)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    # Provenance: where did this row come from?  Lets the UI badge
    # synthetic seed values so a future real data import is clearly
    # distinguishable.
    data_source = Column(String(20), nullable=False, default="seed")
    # Sub-sources -- "seed" with synthetic coords vs. an operator-edited
    # row vs. an external registry import.  All three are tracked so the
    # seed script is never the only path that can update coordinates or
    # addresses.
    coordinates_source = Column(String(20), nullable=True)
    address_source = Column(String(20), nullable=True)
    last_updated = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # --- Audit trail (denormalized "last editor" snapshot for fast UI) ---
    last_edited_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    last_edited_at = Column(DateTime, nullable=True, index=True)

    __table_args__ = (
        Index("ix_hospitals_district_lower", "district"),
        Index("ix_hospitals_lat_lng", "latitude", "longitude"),
        UniqueConstraint("name", "district_id", name="uq_hospitals_name_district_id"),
    )


class DistrictHospitalAggregate(Base):
    __tablename__ = "district_hospital_aggregates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    district = Column(String(120), nullable=False, unique=True, index=True)
    beds = Column(Integer, nullable=False, default=0)
    doctors = Column(Integer, nullable=False, default=0)
    nurses = Column(Integer, nullable=False, default=0)
    ors_stock = Column(Integer, nullable=False, default=0)
    iv_saline_stock = Column(Integer, nullable=False, default=0)
    antibiotics_stock = Column(Integer, nullable=False, default=0)
    occupancy_percent = Column(Float, nullable=False, default=0.0)
    hospital_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ──────────────────────────────────────────────────────────────────────
# Medical knowledge corpus
# ──────────────────────────────────────────────────────────────────────
class KnowledgeArticle(Base):
    __tablename__ = "knowledge_articles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    disease_name = Column(String(80), nullable=False, unique=True, index=True)
    symptoms = Column(Text, nullable=False)
    causes = Column(Text, nullable=True)
    prevention_tips = Column(Text, nullable=True)
    home_care_guidance = Column(Text, nullable=True)
    when_to_see_doctor = Column(Text, nullable=True)
    emergency_contact_info = Column(Text, nullable=True)
    reference = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ──────────────────────────────────────────────────────────────────────
# Community reports (Bengali text + label + severity)
# ──────────────────────────────────────────────────────────────────────
class CommunityReport(Base):
    __tablename__ = "community_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    text = Column(Text, nullable=False)
    label = Column(String(60), nullable=False, index=True)
    severity = Column(String(20), nullable=False, index=True)
    district = Column(String(120), nullable=True, index=True)
    upazila = Column(String(120), nullable=True)
    reporter_email = Column(String(120), nullable=True, index=True)
    reporter_phone = Column(String(50), nullable=True)
    status = Column(String(30), nullable=False, default="unverified")  # unverified | verified | rejected | withdrawn
    image_url = Column(String(500), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ──────────────────────────────────────────────────────────────────────
# Satellite flood-extent registry + GeoJSON payloads
# ──────────────────────────────────────────────────────────────────────
class SatelliteExtent(Base):
    """One row per (district, event) Sentinel-1 flood-extent export.

    `geojson` is stored as a JSON blob so the payload is colocated with the
    registry and travels with the DB.  We still tolerate the legacy
    `data/geo_exports/*.geojson` files on disk if a row is missing, so an
    existing deployment keeps working through the migration.
    """
    __tablename__ = "satellite_extents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    district = Column(String(120), nullable=False, index=True)
    event_label = Column(String(200), nullable=False)
    filename = Column(String(200), nullable=True)
    acquisition_window_start = Column(Date, nullable=True)
    acquisition_window_end = Column(Date, nullable=True)
    geojson = Column(JSON, nullable=False)
    source = Column(String(120), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("district", "event_label", name="uq_satellite_district_event"),
    )


# ──────────────────────────────────────────────────────────────────────
# RAG corpus: WHO / DGHS / flood-safety documents → pgvector chunks
# ──────────────────────────────────────────────────────────────────────
#
# Each `RagDocument` is a single source (e.g. "WHO Cholera Guideline 2023"),
# and each `RagChunk` is one piece of that source (one paragraph or a
# ~300-token window).  Chunks carry a 384-dim embedding from the
# all-MiniLM-L6-v2 model -- query-side we run the same model on the user's
# question and ask pgvector for the cosine-nearest chunks.
#
# The table is intentionally small (we keep only the med/flood grounding
# texts that the chatbot actually needs); a few hundred rows fits in a
# tiny pgvector index and returns sub-millisecond nearest-neighbour
# matches.
EMBEDDING_DIM = 384  # all-MiniLM-L6-v2


class RagDocument(Base):
    """One source document in the RAG corpus (e.g. WHO Cholera Guideline).

    `category` controls which kinds of queries the document is eligible for:
      - 'medical'    : disease/symptom/treatment questions
      - 'safety'     : flood safety, WASH, evacuation, first aid
      - 'district'   : district-specific overview, per-district risk factors
      - 'metadata'   : assistant meta-knowledge (about the platform itself).
                       Excluded from medical queries so the chatbot never
                       answers a user question with "this is what our
                       knowledge base contains".
    """
    __tablename__ = "rag_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(String(120), nullable=False)        # 'WHO', 'DGHS', 'Dataset', ...
    title = Column(String(400), nullable=False)
    slug = Column(String(200), nullable=False, unique=True, index=True)
    language = Column(String(8), nullable=False, default="en")  # 'en' or 'bn'
    category = Column(String(20), nullable=False, default="medical", index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class RagChunk(Base):
    """A text chunk (typically a paragraph) with its embedding vector."""
    __tablename__ = "rag_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(
        UUID(as_uuid=True),
        # FK is declared at the table-arg level because the document table
        # name is fully resolved at metadata-merge time and we want to keep
        # the inline declaration small.
        # (No raw FK constraint to avoid circular import at import time.)
        nullable=False,
        index=True,
    )
    chunk_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    embedding = Column(Vector(EMBEDDING_DIM), nullable=False)
    token_estimate = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_rag_doc_chunk"),
        # HNSW index is created in `ensure_rag_indexes()` because SQLAlchemy
        # doesn't auto-create pgvector indexes from declarative metadata.
    )


# ──────────────────────────────────────────────────────────────────────
# Hospital update audit log
# ──────────────────────────────────────────────────────────────────────
class HospitalUpdate(Base):
    """One row per PATCH on /hospitals/{id}.

    Captures *which* fields changed and *who* made the change so admins
    can answer "why did Feni district hospital's ORS stock jump 200
    units on Tuesday?"  Mirrors the `prediction_history` table style
    (input/output JSON) but for a simpler per-field diff.
    """
    __tablename__ = "hospital_updates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id = Column(
        UUID(as_uuid=True),
        ForeignKey("hospitals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    editor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Field name -> new value (only changed fields are recorded)
    changes = Column(JSON, nullable=False)
    # Snapshot of the new district rollup after the PATCH
    district_aggregate = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


# ──────────────────────────────────────────────────────────────────────
# Hospital issue reports (citizen or ops, "phone is wrong", "facility
# is closed", etc.) -- per-hospital inbox for admins.
# ──────────────────────────────────────────────────────────────────────
class HospitalIssueReport(Base):
    """One row per "report an issue" submission on a hospital's
    detail modal.  Distinct from `CommunityReport` (which is the
    free-text incident stream the chatbot classifies) so admins can
    pull up "all issues reported for Feni District Hospital" in one
    place.

    Statuses:
        open     -- freshly reported, no admin response
        ack      -- admin has seen it (in a future admin UI)
        resolved -- the underlying data was fixed
        dismissed -- out of scope / not actionable
    """
    __tablename__ = "hospital_issue_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id = Column(
        UUID(as_uuid=True),
        ForeignKey("hospitals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reporter_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # One of a small fixed vocabulary so admins can filter the inbox:
    # "phone_wrong" | "address_wrong" | "closed" | "no_doctor" |
    # "no_stock" | "name_wrong" | "other"
    category = Column(String(30), nullable=False, index=True)
    # Free-text description (1-1000 chars).
    description = Column(Text, nullable=False)
    # Reporter's role at submission time (audit only -- we don't FK
    # to roles because they're an Enum, not a table).
    reporter_role = Column(String(30), nullable=True)
    status = Column(String(20), nullable=False, default="open", index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    # Audit columns -- who flipped the status and when.  The {verb}_at /
    # {verb}_by convention keeps the schema flat and makes the
    # per-hospital "issue history" endpoint a single round-trip.
    ack_at = Column(DateTime, nullable=True)
    ack_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    dismissed_at = Column(DateTime, nullable=True)
    dismissed_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

# ─── Idempotent micro-migrations ──────────────────────────────────────
# Base.metadata.create_all() only handles new tables.  When we add a
# column to an existing model we have to ALTER TABLE the live DB
# ourselves.  Postgres does not support `ADD COLUMN IF NOT EXISTS`
# (SQLite does, since 3.35), so we introspect information_schema
# first and only ALTER for columns that are actually missing.
# Safe to call repeatedly.
from sqlalchemy import text as _sa_text, inspect as _sa_inspect
from app.database import engine as _engine  # noqa: E402


def _ensure_issue_audit_columns() -> None:
    spec = [
        # (column_name, ddl-for-postgres, ddl-for-sqlite)
        ("ack_at",      "ALTER TABLE hospital_issue_reports ADD COLUMN ack_at TIMESTAMP NULL",
                        "ALTER TABLE hospital_issue_reports ADD COLUMN ack_at DATETIME"),
        ("ack_by",      "ALTER TABLE hospital_issue_reports ADD COLUMN ack_by UUID NULL",
                        "ALTER TABLE hospital_issue_reports ADD COLUMN ack_by CHAR(32)"),
        ("resolved_at", "ALTER TABLE hospital_issue_reports ADD COLUMN resolved_at TIMESTAMP NULL",
                        "ALTER TABLE hospital_issue_reports ADD COLUMN resolved_at DATETIME"),
        ("resolved_by", "ALTER TABLE hospital_issue_reports ADD COLUMN resolved_by UUID NULL",
                        "ALTER TABLE hospital_issue_reports ADD COLUMN resolved_by CHAR(32)"),
        ("dismissed_at","ALTER TABLE hospital_issue_reports ADD COLUMN dismissed_at TIMESTAMP NULL",
                        "ALTER TABLE hospital_issue_reports ADD COLUMN dismissed_at DATETIME"),
        ("dismissed_by","ALTER TABLE hospital_issue_reports ADD COLUMN dismissed_by UUID NULL",
                        "ALTER TABLE hospital_issue_reports ADD COLUMN dismissed_by CHAR(32)"),
    ]
    try:
        insp = _sa_inspect(_engine)
        # If the table doesn't exist yet, Base.metadata.create_all()
        # elsewhere will create it with the full schema.  Skip.
        if not insp.has_table("hospital_issue_reports"):
            return
        existing = {c["name"] for c in insp.get_columns("hospital_issue_reports")}
        is_sqlite = _engine.dialect.name == "sqlite"
        with _engine.begin() as conn:
            for col, ddl_pg, ddl_sqlite in spec:
                if col in existing:
                    continue
                ddl = ddl_sqlite if is_sqlite else ddl_pg
                conn.execute(_sa_text(ddl))
    except Exception:
        # Don't block import if the DB is unreachable during a
        # static-analysis pass; the runtime path is what matters.
        pass


_ensure_issue_audit_columns()
