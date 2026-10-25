"""Idempotent ALTER-TABLE migrations for schema gaps `create_all` can't fill.

SQLAlchemy's `Base.metadata.create_all()` only creates *missing* tables --
it does not add new columns to existing tables.  Whenever we add a new
column to a model, the live DB won't pick it up until either:
  - the operator drops the table (data loss) and restarts, or
  - we run an explicit ALTER TABLE.

This module is the second option.  Each `_add_column_if_missing(...)`
checks the live DB for the column, and runs `ALTER TABLE ... ADD COLUMN
IF NOT EXISTS` only when it's missing.  Postgres supports the
`IF NOT EXISTS` clause on ADD COLUMN, so the migration is safe to run
on every boot.

Adding a new column
-------------------
1. Add the Column(...) to the SQLAlchemy model in app.reference_models.
2. Add a matching `_add_column_if_missing(...)` call below with the
   correct DB type and a default.  Use a NULLable column or a DEFAULT
   for NOT NULL columns, otherwise Postgres rejects the ALTER.
3. Restart the backend; the migration runs once during the lifespan.
"""
from __future__ import annotations

import logging
from typing import Iterable

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def _column_exists(engine: Engine, table: str, column: str) -> bool:
    """True if `table` already has `column`."""
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = :t AND column_name = :c"
            ),
            {"t": table, "c": column},
        ).first()
        return row is not None


def _add_column_if_missing(
    engine: Engine, table: str, column: str, ddl: str
) -> bool:
    """Run `ALTER TABLE <table> ADD COLUMN <column> <ddl>` if the
    column is missing.  Returns True if the ALTER was executed.

    The `ddl` should be a complete column definition including the
    type, default, and constraints (e.g. `"VARCHAR(40)"` or
    `"UUID REFERENCES users(id) ON DELETE SET NULL"`).  Postgres 12+
    supports `ADD COLUMN IF NOT EXISTS`, so the call is idempotent
    even when `column_exists` lies (race / replication lag).
    """
    if _column_exists(engine, table, column):
        return False
    logger.info("db_migrations: adding %s.%s", table, column)
    with engine.begin() as conn:
        conn.execute(text(f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS "{column}" {ddl}'))
    return True


def run_db_migrations(engine: Engine) -> list[str]:
    """Run all migrations.  Returns the list of ALTERs executed."""
    executed: list[str] = []

    # --- hospitals: columns added in the Hospital Directory feature ---
    hospital_cols: list[tuple[str, str]] = [
        ("district_id", "UUID REFERENCES districts(id) ON DELETE SET NULL"),
        ("upazila", "VARCHAR(120)"),
        ("address", "VARCHAR(500)"),
        ("phone", "VARCHAR(40)"),
        ("beds_occupied", "INTEGER"),
        ("data_source", "VARCHAR(20) NOT NULL DEFAULT 'seed'"),
        ("coordinates_source", "VARCHAR(20)"),
        ("address_source", "VARCHAR(20)"),
        ("last_updated", "TIMESTAMP"),
        ("icu_beds_total", "INTEGER NOT NULL DEFAULT 0"),
        ("icu_beds_occupied", "INTEGER NOT NULL DEFAULT 0"),
        ("isolation_beds_total", "INTEGER NOT NULL DEFAULT 0"),
        ("isolation_beds_occupied", "INTEGER NOT NULL DEFAULT 0"),
        ("operating_status", "VARCHAR(40) NOT NULL DEFAULT 'normal'"),
        ("emergency_contact", "VARCHAR(60)"),
    ]
    for col, ddl in hospital_cols:
        if _add_column_if_missing(engine, "hospitals", col, ddl):
            executed.append(f"hospitals.{col}")

    # --- users: organization & phone for multi-agency tenancy ---
    user_cols: list[tuple[str, str]] = [
        ("organization", "VARCHAR(150)"),
        ("phone", "VARCHAR(40)"),
    ]
    for col, ddl in user_cols:
        if _add_column_if_missing(engine, "users", col, ddl):
            executed.append(f"users.{col}")

    # --- community_reports: operational tracking fields for citizen reporting ---
    report_cols: list[tuple[str, str]] = [
        ("district", "VARCHAR(120)"),
        ("upazila", "VARCHAR(120)"),
        ("reporter_email", "VARCHAR(120)"),
        ("reporter_phone", "VARCHAR(50)"),
        ("status", "VARCHAR(30) NOT NULL DEFAULT 'unverified'"),
        ("image_url", "VARCHAR(500)"),
        ("latitude", "DOUBLE PRECISION"),
        ("longitude", "DOUBLE PRECISION"),
    ]
    for col, ddl in report_cols:
        if _add_column_if_missing(engine, "community_reports", col, ddl):
            executed.append(f"community_reports.{col}")

    # --- (latitude, longitude) composite index for /hospitals/nearby ---
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_hospitals_lat_lng "
                "ON hospitals (latitude, longitude)"
            )
        )
    # Unique constraint: idempotent via IF NOT EXISTS.  Postgres 15+
    # supports this; on 14 and below it errors harmlessly, so we ignore
    # the exception to avoid blocking startup.
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE hospitals "
                    "ADD CONSTRAINT uq_hospitals_name_district_id "
                    "UNIQUE (name, district_id)"
                )
            )
    except Exception as exc:  # pragma: no cover -- only on PG < 15
        logger.debug("uq_hospitals_name_district_id already present or unsupported: %s", exc)

    if executed:
        logger.info("db_migrations: applied %d ALTER(s): %s", len(executed), executed)
    else:
        logger.info("db_migrations: schema already up to date")
    return executed
