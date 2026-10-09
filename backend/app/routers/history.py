"""
/history/weekly/{district} -- District weekly case + environmental history

GET  /history/weekly/{district}
    Returns the 8 most recent weeks of real data for a district.
    A district must have all 8 rows before it can be used by the LSTM;
    incomplete history returns 404 rather than fabricated observations.
     Open to all authenticated users (same as /predict/* endpoints).

POST /history/weekly/{district}
     Upserts a batch of weekly observations for a district.
     Restricted to operational roles (health_worker, hospital, ngo,
     government, admin) -- the same set that can see the full assessment.
     Useful for seeding real data during onboarding or via a cron job.

The table is created automatically at startup (Base.metadata.create_all
in main.py) so no manual migration is needed for a fresh deploy.
"""
from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import func

from app.database import get_db
from app.history_models import WeeklyHistory
from app.schemas import WeeklyHistoryResponse, WeeklyHistoryItem, WeeklyHistorySeedItem
from app.auth_deps import require_any_authenticated_user, require_roles
from app.auth_models import UserRole, User
from app.auth_deps import get_current_user
from app.prediction_models import PredictionHistory
from app.schemas import PredictionHistoryItem
from app.services.weather_service import normalize_district_for_lookup

router = APIRouter(
    prefix="/history",
    tags=["District Weekly History"],
    dependencies=[Depends(require_any_authenticated_user)],
)

_NEEDED = 8  # LSTM lookback window


@router.get("/predictions", response_model=List[PredictionHistoryItem])
def get_prediction_history(
    model_name: str | None = Query(None),
    district: str | None = Query(None),
    risk_level: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(PredictionHistory).filter(PredictionHistory.user_id == user.id)
    if model_name:
        query = query.filter(PredictionHistory.model_name == model_name)
    if district:
        query = query.filter(PredictionHistory.district == district)
    if risk_level:
        query = query.filter(PredictionHistory.risk_level == risk_level)
    rows = query.order_by(PredictionHistory.created_at.desc()).limit(200).all()
    return [PredictionHistoryItem(
        id=str(row.id), model_name=row.model_name, district=row.district,
        risk_level=row.risk_level, probability=row.probability,
        input_data=row.input_data, output_data=row.output_data,
        created_at=row.created_at.isoformat(),
    ) for row in rows]


@router.get("/weekly/{district}", response_model=WeeklyHistoryResponse)
def get_weekly_history(
    district: str,
    db: Session = Depends(get_db),
):
    """
    Return the 8 most-recent weekly observations for a district, oldest first.
    If the DB has fewer than 8, return 404. The forecast model must never
    receive generated values presented as historical observations.

    District-name aliases (Cumilla/Comilla, Bogura/Bogra, Jashore/Jessore,
    Chattogram/Chittagong) are normalised before lookup so a user picking
    the modern spelling from the dashboard still finds seeded history.
    """
    canonical = normalize_district_for_lookup(district)
    rows = (
        db.query(WeeklyHistory)
        .filter(func.lower(WeeklyHistory.district) == canonical)
        .order_by(WeeklyHistory.week_ending.desc())
        .limit(_NEEDED)
        .all()
    )

    # Rows are newest-first; reverse to oldest-first for the LSTM
    rows = list(reversed(rows))

    if len(rows) < _NEEDED:
        raise HTTPException(
            status_code=404,
            detail=f"Only {len(rows)} real weekly observations are available for '{district}'; 8 are required.",
        )

    items: List[WeeklyHistoryItem] = [
        WeeklyHistoryItem(
            week_ending=row.week_ending.isoformat(),
            weekly_cases=row.weekly_cases,
            rainfall_mm=row.rainfall_mm,
            temperature_c=row.temperature_c,
            flood_depth_cm=row.flood_depth_cm,
            sanitation_score=row.sanitation_score,
        )
        for row in rows
    ]

    return WeeklyHistoryResponse(district=district, weeks=items, source="database")


@router.post(
    "/weekly/{district}",
    response_model=WeeklyHistoryResponse,
    dependencies=[Depends(require_roles(
        UserRole.health_worker, UserRole.hospital,
        UserRole.ngo, UserRole.government, UserRole.admin,
    ))],
    status_code=status.HTTP_200_OK,
    summary="Upsert weekly history rows for a district (operational roles only)",
)
def upsert_weekly_history(
    district: str,
    payload: List[WeeklyHistorySeedItem],
    db: Session = Depends(get_db),
):
    """
    Upsert one or more weekly observations for a district.
    On conflict (same district + week_ending) the existing row is updated.
    Returns the full 8-week history after the upsert.
    """
    if not payload:
        raise HTTPException(status_code=422, detail="payload must contain at least one item")

    for item in payload:
        try:
            week_date = date.fromisoformat(item.week_ending)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=f"week_ending '{item.week_ending}' is not a valid ISO date (YYYY-MM-DD)",
            )

        stmt = (
            pg_insert(WeeklyHistory)
            .values(
                district=district,
                week_ending=week_date,
                weekly_cases=item.weekly_cases,
                rainfall_mm=item.rainfall_mm,
                temperature_c=item.temperature_c,
                flood_depth_cm=item.flood_depth_cm,
                sanitation_score=item.sanitation_score,
            )
            .on_conflict_do_update(
                constraint="uq_district_week",
                set_=dict(
                    weekly_cases=item.weekly_cases,
                    rainfall_mm=item.rainfall_mm,
                    temperature_c=item.temperature_c,
                    flood_depth_cm=item.flood_depth_cm,
                    sanitation_score=item.sanitation_score,
                ),
            )
        )
        db.execute(stmt)

    db.commit()
    # Re-use the GET handler to return the current state
    return get_weekly_history(district, db)
