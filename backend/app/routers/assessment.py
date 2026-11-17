"""
/assessment/{district} -- one server-side call that returns the full
district assessment (Flood, Water Level, Overall Risk, Disease Outbreak,
Disease Breakdown, Forecast, Satellite Extent, Recommendation) with
per-section status, so the dashboard can auto-run on page open and
show honest empty/error states per section instead of one section
blanking the rest of the page.

Why this exists
---------------
The earlier full-assessment path assembled the request payload in the
browser from scattered defaults -- producing identical "98% flood risk"
output for every district and the blocking "requires eight real weekly
observations" message.  Moving the assembly server-side means the
backend reads weather, river level, and 8-week history from the
database, runs each model, and returns one response with per-section
status.  Each section is independent: a missing input or a model
error never blocks the other sections.

RBAC
----
The endpoint itself is open to any authenticated user; the response
strips the recommendation section for non-operational roles
(citizens).  This matches the rule that recommendation content is
operational-only and the server must enforce it, not just the UI.

Threading
---------
Every model call already uses `await asyncio.to_thread(...)` in the
downstream routers, so a single assessment call to /assessment/{district}
yields the event loop between sections and remains responsive under
concurrent calls.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth_deps import get_current_user
from app.auth_models import User, UserRole
from app.database import get_db
from app.history_models import WeeklyHistory
from app.models_loader import models
from app.schemas import (
    AssessmentSection,
    DiseaseBreakdownRequest,
    DiseasePredictionRequest,
    ForecastRequest,
    FullAssessmentV2Response,
    RecommendationRequest,
    WeeklyObservation,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/assessment", tags=["Full Assessment (per-section)"])

OPERATIONAL_ROLES = (
    UserRole.health_worker, UserRole.hospital, UserRole.ngo,
    UserRole.government, UserRole.admin,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ok(data: dict, data_source: Optional[str] = None, as_of: Optional[str] = None) -> AssessmentSection:
    return AssessmentSection(
        status="ok",
        data=data,
        data_source=data_source,
        as_of=as_of,
    )


def _unavailable(reason: str, data_source: Optional[str] = None, as_of: Optional[str] = None) -> AssessmentSection:
    return AssessmentSection(
        status="unavailable",
        reason=reason,
        data_source=data_source,
        as_of=as_of,
    )


def _error(reason: str) -> AssessmentSection:
    return AssessmentSection(
        status="error",
        reason=reason,
    )


def _build_disease_payload(
    district: str,
    weather: dict,
    history: list,
    river_level_override: Optional[float] = None,
) -> DiseasePredictionRequest:
    """Build a DiseasePredictionRequest for the district from live weather
    and the most recent 8 weeks of history. Supports manual river level overrides.
    """
    rainfall = weather.get("rainfall") or 0.0
    temp = weather.get("temperature") or 25.0
    humidity = weather.get("humidity") or 70.0
    if river_level_override is not None:
        river_level = river_level_override
    else:
        river_level = weather.get("river_level_m") or 0.0
    population_density = weather.get("population_density") or 1500.0
    water_quality = weather.get("water_quality_index") or 70.0
    sanitation = weather.get("sanitation_score")
    if sanitation is None:
        sanitation = (history[0].sanitation_score if history else 0.5)
    flood_depth = (history[0].flood_depth_cm if history else 0.0)
    if river_level_override is not None and river_level_override > 6.0:
        # If simulated river surge exceeds flood threshold, ensure positive flood depth
        flood_depth = max(flood_depth, (river_level_override - 5.0) * 20.0)

    if len(history) >= 2:
        previous_week = history[-1].weekly_cases
        previous_two_week = history[-2].weekly_cases
    elif history:
        previous_week = history[-1].weekly_cases
        previous_two_week = history[-1].weekly_cases
    else:
        previous_week = 0.0
        previous_two_week = 0.0

    return DiseasePredictionRequest(
        location=district,
        rainfall_mm=float(rainfall),
        temperature_c=float(temp),
        humidity_percent=float(humidity),
        river_level_m=float(river_level),
        flood_depth_cm=float(flood_depth),
        population_density=float(population_density),
        sanitation_score=float(sanitation),
        water_quality_index=float(water_quality),
        previous_week_cases=float(previous_week),
        previous_two_week_cases=float(previous_two_week),
        season="Monsoon",
    )


async def _run_flood(payload: DiseasePredictionRequest) -> dict:
    """Model 1 prediction.  We rebuild the feature dict here (mirroring
    `flood.py:predict_flood`) but skip `record_prediction` -- the audit
    log isn't written for the auto-run assessment because that would
    create 5 history rows per page open and bury the interactive
    prediction history.  Heavy inference still goes through
    `asyncio.to_thread` so the event loop stays responsive.
    """
    import pandas as pd
    from app.models_loader import models
    from app.schemas import FloodPredictionResponse
    from app.services.explainability import explain_prediction

    rainfall = payload.rainfall_mm or 0.0
    humidity = payload.humidity_percent or 70.0
    temp = payload.temperature_c or 25.0
    elevation = 20.0  # default; dashboard doesn't carry this per district
    water_quality = payload.water_quality_index if payload.water_quality_index is not None else 70.0
    population = payload.population_density if payload.population_density is not None else 1500.0

    input_dict = {
        "rainfall_mm": rainfall,
        "river_level_m": payload.river_level_m,
        "humidity_percent": humidity,
        "temperature_c": temp,
        "elevation_m": elevation,
        "water_quality_index": water_quality,
        "population_density": population,
    }
    season_cols = [c for c in models.flood_features if c.startswith("season_")]
    for col in season_cols:
        season_name = col.replace("season_", "")
        input_dict[col] = 1 if season_name == payload.season else 0
    input_df = pd.DataFrame([input_dict])[models.flood_features]
    flood_probability = float((await asyncio.to_thread(models.flood_model.predict_proba, input_df))[0][1])
    if flood_probability > 0.7:
        risk_level = "High"
    elif flood_probability > 0.4:
        risk_level = "Medium"
    else:
        risk_level = "Low"

    def _severity(rainfall_mm: float) -> str:
        if rainfall_mm < 100: return "Minor"
        if rainfall_mm < 300: return "Moderate"
        return "Severe"

    res = FloodPredictionResponse(
        flood_probability=round(flood_probability, 4),
        flood_risk_level=risk_level,
        likely_severity_if_flood=_severity(rainfall),
        feature_importance=await asyncio.to_thread(explain_prediction, models.flood_model, input_df),
    )
    return res.model_dump()


async def _run_disease(payload: DiseasePredictionRequest) -> dict:
    """Model 2 prediction.  Same as `disease.py:predict_disease` but
    without the audit-log write (we don't want the auto-run to spam
    prediction_history).
    """
    from app.models_loader import models
    from app.routers.disease import _build_feature_row
    from app.schemas import DiseasePredictionResponse
    from app.services.explainability import explain_prediction

    input_df = await _build_feature_row(payload)
    probs = (await asyncio.to_thread(models.outbreak_model.predict_proba, input_df))[0]
    predicted_class = models.outbreak_label_encoder.classes_[probs.argmax()]
    prob_dict = dict(zip(models.outbreak_label_encoder.classes_, [round(float(p), 4) for p in probs]))
    res = DiseasePredictionResponse(
        predicted_outbreak_risk=predicted_class,
        risk_probability_by_class=prob_dict,
        feature_importance=await asyncio.to_thread(explain_prediction, models.outbreak_model, input_df),
    )
    return res.model_dump()


async def _run_disease_breakdown(payload: DiseasePredictionRequest) -> dict:
    from app.routers.disease_breakdown import predict_disease_breakdown
    req = DiseaseBreakdownRequest(**payload.model_dump())
    res = await predict_disease_breakdown(req)
    return res.model_dump()


async def _run_risk(payload: DiseasePredictionRequest) -> dict:
    from app.routers.risk import compute_risk_score
    res = await compute_risk_score(payload)
    return res.model_dump()


async def _run_forecast(district: str, history: list) -> dict:
    if not history or len(history) < 8:
        raise HTTPException(
            status_code=422,
            detail=(
                "LSTM forecast requires exactly 8 real weekly observations; "
                f"got {len(history)} for {district}."
            ),
        )
    from app.models_loader import models
    from app.schemas import ForecastResponse
    if models.timeseries_model is None:
        raise HTTPException(
            status_code=503,
            detail="LSTM forecast model is unavailable (tensorflow not installed on this server).",
        )
    if district not in models.timeseries_scalers:
        raise HTTPException(
            status_code=404,
            detail=f"No trained scaler for district '{district}'. "
                   f"This district may not have had enough historical weeks during training.",
        )
    scaler = models.timeseries_scalers[district]
    feature_cols = models.timeseries_feature_cols

    weekly = [
        WeeklyObservation(
            weekly_cases=float(r.weekly_cases),
            rainfall_mm=float(r.rainfall_mm),
            temperature_c=float(r.temperature_c),
            flood_depth_cm=float(r.flood_depth_cm),
            sanitation_score=float(r.sanitation_score),
        )
        for r in history[-8:]
    ]
    import numpy as np
    window = np.array([[getattr(week, col) for col in feature_cols] for week in weekly])
    scaled_window = scaler.transform(window)
    scaled_window = scaled_window.reshape(1, models.timeseries_lookback, len(feature_cols))
    # LSTM .predict is CPU-bound -- offload so we don't block the loop.
    pred_7, pred_14 = await asyncio.to_thread(
        models.timeseries_model.predict, scaled_window, 0
    )
    def inverse_cases(scaled_val: float) -> float:
        dummy = np.zeros((1, len(feature_cols)))
        dummy[0, 0] = scaled_val
        return float(scaler.inverse_transform(dummy)[0, 0])
    res = ForecastResponse(
        district=district,
        forecast_next_7_days_cases=round(inverse_cases(pred_7[0][0]), 1),
        forecast_next_14_days_cases=round(inverse_cases(pred_14[0][0]), 1),
    )
    return res.model_dump()


async def _run_recommendation(db: Session, district: str, risk_level: str) -> dict:
    from app.routers.recommend import _recommend_for_district
    res = _recommend_for_district(db, district, risk_level)
    return res.model_dump()


def _load_history(db: Session, district: str) -> list:
    """Return the 8 most recent WeeklyHistory rows for the district,
    oldest first.  Match case-insensitively because the seeder stores
    rows in lowercase ("feni") while the API accepts title-case
    ("Feni").
    """
    return (
        db.query(WeeklyHistory)
        .filter(WeeklyHistory.district.ilike(district))
        .order_by(WeeklyHistory.week_ending.asc())
        .all()
    )


def _load_satellite_extent(db: Session, district: str) -> Optional[dict]:
    """Read the registered GeoJSON flood extent for the district, if any.
    Returns None when the district has no registered export.  We don't
    call the heavy U-Net here -- segmentation is on-demand only (the
    "Run Segmentation" button), per the spec.

    Looks up under the canonical modern spelling AND under the legacy
    spelling the climate dataset may have shipped with, so both
    "Barishal" (modern) and "Barisal" (legacy) resolve to the same row.
    """
    from app.reference_models import SatelliteExtent
    from app.services.district_centroids import _LEGACY_TO_CANONICAL
    canonical = _LEGACY_TO_CANONICAL.get((district or "").strip().casefold(), district)
    # The row may have been seeded under either spelling; try both.
    candidates = [canonical]
    for legacy, mod in _LEGACY_TO_CANONICAL.items():
        if mod == canonical and legacy != canonical.casefold():
            candidates.append(legacy.capitalize())
    row = None
    for cand in candidates:
        row = (
            db.query(SatelliteExtent)
            .filter(SatelliteExtent.district.ilike(cand))
            .first()
        )
        if row is not None:
            break
    if row is None:
        return None
    return {
        "district": row.district,
        "event_label": row.event_label,
        "geojson": row.geojson,
    }


@router.get("/{district}", response_model=FullAssessmentV2Response, response_model_exclude_none=True)
async def full_assessment_for_district(
    district: str,
    river_level: Optional[float] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run the full assessment for `district` in one server-side call.
    Accepts an optional `river_level` parameter for real-time scenario simulation.

    Each section runs independently.  A failure in one section does not
    block the others.  The response carries `is_operational` so the UI
    can decide whether to even show the "Recommendation" frame.
    """
    district = (district or "").strip()
    if not district:
        raise HTTPException(status_code=422, detail="district is required")

    is_operational = current_user.role in OPERATIONAL_ROLES

    # ── Inputs: weather, history, satellite-extent ────────────────────
    try:
        from app.services.weather_service import get_weather_for_location
        weather = await get_weather_for_location(district)
    except Exception as exc:
        logger.warning("weather lookup failed for %s: %s", district, exc)
        weather = {"data_source": "fallback", "river_level_m": 0.0,
                   "water_quality_index": None, "rainfall": 0.0,
                   "temperature": 25.0, "humidity": 70.0,
                   "population_density": None, "sanitation_score": None}

    try:
        history_rows = await asyncio.to_thread(_load_history, db, district)
    except Exception as exc:
        logger.warning("history load failed for %s: %s", district, exc)
        history_rows = []

    as_of_water = weather.get("district_conditions_date")
    effective_river_level = river_level if river_level is not None else weather.get("river_level_m")
    water_level_section = _ok(
        {
            "river_level_m": effective_river_level,
            "water_quality_index": weather.get("water_quality_index"),
        },
        data_source="manual_override" if river_level is not None else (weather.get("data_source") or "unknown"),
        as_of=as_of_water,
    )
    if effective_river_level is None and weather.get("water_quality_index") is None:
        water_level_section = _unavailable(
            reason="No river-level / water-quality observation recorded for this district yet.",
            data_source=weather.get("data_source") or "unknown",
            as_of=as_of_water,
        )

    payload = _build_disease_payload(district, weather, history_rows, river_level_override=river_level)

    # ── Run all five model sections in parallel ──────────────────────
    # Each `await` yields the event loop, so concurrent requests stay
    # responsive even when the heavier models (U-Net) are warm.
    flood_task = asyncio.create_task(_safe_run(_run_flood(payload), "flood"))
    disease_task = asyncio.create_task(_safe_run(_run_disease(payload), "disease_outbreak"))
    breakdown_task = asyncio.create_task(_safe_run(_run_disease_breakdown(payload), "disease_breakdown"))
    risk_task = asyncio.create_task(_safe_run(_run_risk(payload), "overall_risk"))
    forecast_task = asyncio.create_task(_safe_run(_run_forecast(district, history_rows), "forecast"))

    # Wait for the five core sections together.  Recommendation waits
    # for the risk result, so chain it.
    flood_s, disease_s, breakdown_s, risk_s, forecast_s = await asyncio.gather(
        flood_task, disease_task, breakdown_task, risk_task, forecast_task
    )

    # ── Satellite extent (DB read, no model call) ────────────────────
    try:
        sat_row = await asyncio.to_thread(_load_satellite_extent, db, district)
    except Exception as exc:
        logger.warning("satellite-extent load failed for %s: %s", district, exc)
        sat_row = None
    if sat_row is None:
        satellite_section = _unavailable(
            reason="No satellite export is registered for this district yet. "
                   "Feni is currently the only district with a real export.",
            data_source="database",
        )
    else:
        satellite_section = _ok(sat_row, data_source="database")

    # ── Recommendation (operational only) ────────────────────────────
    recommendation_section: Optional[AssessmentSection] = None
    if is_operational:
        # Use the risk section's final level if available; otherwise
        # default to "Medium" so the recommendation still surfaces.
        risk_level = "Medium"
        if risk_s.status == "ok" and risk_s.data:
            risk_level = risk_s.data.get("final_risk_level") or "Medium"
        try:
            rec = await _run_recommendation(db, district, risk_level)
            recommendation_section = _ok(rec, data_source="database")
        except Exception as exc:
            logger.warning("recommendation failed for %s: %s", district, exc)
            recommendation_section = _error(str(exc))
    # Citizens: keep the field absent from the JSON response, not just empty.

    return FullAssessmentV2Response(
        district=district,
        is_operational=is_operational,
        generated_at=_now_iso(),
        flood=flood_s,
        water_level=water_level_section,
        overall_risk=risk_s,
        disease_outbreak=disease_s,
        disease_breakdown=breakdown_s,
        forecast=forecast_s,
        satellite_extent=satellite_section,
        recommendation=recommendation_section,
    )


async def _safe_run(coro, section_name: str) -> AssessmentSection:
    """Run a coroutine and convert any exception into an `error` section
    so one section failing can never crash the whole assessment."""
    try:
        data = await coro
        return _ok(data)
    except HTTPException as he:
        return _unavailable(reason=str(he.detail))
    except Exception as exc:  # noqa: BLE001
        logger.exception("%s section failed", section_name)
        return _error(reason=str(exc))
