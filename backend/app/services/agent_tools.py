"""FloodShield AI — agent tools.

The chatbot exposes a small set of *tools* the LLM can call.  Every tool is
a thin wrapper over existing backend logic (predict_flood, get_weather, etc.)
or a direct DB read.  Tools return structured dicts that include a
``data_source`` field (``database`` | ``live_api`` | ``model_prediction`` |
``fallback``) plus an ``as_of`` timestamp where applicable.

Role-based access is enforced server-side inside the executor — never let the
LLM decide who can see what.
"""
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Awaitable, Callable, Dict, List, Optional

import pandas as pd
import structlog
from rapidfuzz import fuzz, process
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth_models import User, UserRole
from app.knowledge_base import MEDICAL_KNOWLEDGE_BASE, get_articles_from_db
from app.models_loader import models
from app.routers.flood import _severity_hint
from app.routers.history import get_weekly_history
from app.routers.recommend import _recommend_for_district, OPERATIONAL_ROLES, DISTRICT_ALIASES
from app.routers.risk import _build_feature_row as _build_risk_feature_row, compute_risk_score, _FLOOD_PRONE_DISTRICTS
from app.routers.satellite import _normalize_district as _normalize_satellite_district
from app.schemas import (
    FloodPredictionRequest,
    DiseaseBreakdownRequest,
    DiseasePredictionRequest,
    ForecastRequest,
    RiskScoreRequest,
    WeatherObservationItem,
)
from app.services.weather_service import (
    get_weather_for_location,
    normalize_district_for_lookup,
)
from app.reference_models import (
    CommunityReport,
    DistrictEnv,
    DistrictHospitalAggregate,
    KnowledgeArticle,
    Location,
    SatelliteExtent,
)
from app.history_models import WeeklyHistory

logger = structlog.get_logger(__name__).bind(module="agent_tools")

# Bangla district names (English -> Bangla alias).  Best-effort; used for
# district-name resolution when the user types in Bangla.
BANGLA_DISTRICT_ALIASES: Dict[str, str] = {
    "feni": "ফেনী",
    "sylhet": "সিলেট",
    "dhaka": "ঢাকা",
    "chattogram": "চট্টগ্রাম",
    "chittagong": "চট্টগ্রাম",
    "cumilla": "কুমিল্লা",
    "comilla": "কুমিল্লা",
    "bogura": "বগুড়া",
    "bogra": "বগুড়া",
    "rajshahi": "রাজশাহী",
    "khulna": "খুলনা",
    "barishal": "বরিশাল",
    "barisal": "বরিশাল",
    "rangpur": "রংপুর",
    "mymensingh": "ময়মনসিংহ",
    "narayanganj": "নারায়ণগঞ্জ",
    "coxs bazar": "কক্সবাজার",
    "coxsbazar": "কক্সবাজার",
}


# ---------------------------------------------------------------------------
# District resolution
# ---------------------------------------------------------------------------

def _bangla_alias_to_english(s: str) -> str:
    """If `s` looks like a Bangla script district name, return its English form.

    Bangla-script names contain Unicode code points 0x0980-0x09FF.  We
    reverse-lookup against the alias map's *values* (which are Bangla).
    """
    has_bangla = any("\u0980" <= ch <= "\u09FF" for ch in s)
    if not has_bangla:
        return ""
    by_bangla = {v: k for k, v in BANGLA_DISTRICT_ALIASES.items()}
    return by_bangla.get(s, "")


async def _list_all_districts(db: Session) -> List[str]:
    """Return the canonical list of district names (64 districts)."""
    rows = await asyncio.to_thread(
        lambda: db.query(Location.district)
        .filter(Location.kind == "district")
        .distinct()
        .all()
    )
    return sorted({r[0] for r in rows if r[0]})


async def resolve_district(db: Session, name: str) -> Dict[str, Any]:
    """Resolve a free-form district name (English, Bangla, misspelled).

    Returns a ``{ok, canonical, candidates[], confidence}`` dict.
    """
    if not name or not name.strip():
        return {"ok": False, "canonical": None, "candidates": [], "error": "Empty input"}

    raw = name.strip()
    raw_lower = raw.lower()
    canonical_set = set(await _list_all_districts(db))

    # 1) exact English match
    if raw in canonical_set:
        return {"ok": True, "canonical": raw, "candidates": [raw], "confidence": 1.0}

    # 2) Bangla script alias -> English
    bn = _bangla_alias_to_english(raw)
    if bn and bn.title() in canonical_set:
        return {"ok": True, "canonical": bn.title(), "candidates": [bn.title()], "confidence": 1.0}

    # 3) DB alias map (chittagong -> chattogram, etc.) — both sides are
    # lowercase.  normalize_district_for_lookup returns the canonical
    # lowercase key.
    norm = normalize_district_for_lookup(raw)
    if norm:
        # Find the actual row in canonical_set (mixed-case) that matches the
        # normalised key.
        for c in canonical_set:
            if c.lower() == norm:
                return {"ok": True, "canonical": c, "candidates": [c], "confidence": 0.95}

    # 4) Fuzzy match against the canonical set.  rapidfuzz returns top-N with
    # scores; accept scores >= 70.
    matches = process.extract(raw, list(canonical_set), scorer=fuzz.WRatio, limit=5)
    scored = [(m, s) for m, s, _ in matches if s >= 70]
    if scored:
        best, score = scored[0]
        candidates = [b for b, _ in scored]
        return {
            "ok": True,
            "canonical": best,
            "candidates": candidates,
            "confidence": round(score / 100, 2),
        }

    # 5) No match — return top 5 candidates so the LLM can offer them as
    # clarifying options.
    fallback = [m for m, _, _ in matches[:5]]
    return {
        "ok": False,
        "canonical": None,
        "candidates": fallback,
        "confidence": 0.0,
        "error": f"No close match for '{raw}'. Pick one of the candidates.",
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _dist_env(db: Session, district: str) -> Optional[DistrictEnv]:
    """Fetch DistrictEnv by canonical name (case-insensitive)."""
    norm = normalize_district_for_lookup(district)
    if not norm:
        return None
    return await asyncio.to_thread(
        lambda: db.query(DistrictEnv)
        .filter(func.lower(DistrictEnv.district) == norm)
        .first()
    )


async def _hospital_agg(db: Session, district: str) -> Optional[DistrictHospitalAggregate]:
    norm = normalize_district_for_lookup(district)
    if not norm:
        return None
    return await asyncio.to_thread(
        lambda: db.query(DistrictHospitalAggregate)
        .filter(func.lower(DistrictHospitalAggregate.district) == norm)
        .first()
    )


async def _weather_with_district_conditions(db: Session, district: str) -> Dict[str, Any]:
    """Live weather + merged per-district fields."""
    try:
        wd = await get_weather_for_location(district)
    except Exception as exc:
        logger.warning("weather fetch failed", district=district, error=str(exc))
        wd = {"location": district, "data_source": "fallback"}
    # Always overlay latest per-district DB conditions
    env = await _dist_env(db, district)
    as_of = _now_iso()
    if env is not None:
        # `get_weather_for_location` may already include these; only set if missing.
        wd.setdefault("river_level_m", env.river_level_m)
        wd.setdefault("water_quality_index", env.water_quality_index)
        wd.setdefault("flood_depth_cm", env.flood_depth_cm)
        wd.setdefault("observed_on", env.observed_on.isoformat() if env.observed_on else None)
        wd["observed_on"] = env.observed_on.isoformat() if env.observed_on else wd.get("observed_on")
        wd["season"] = env.season
        wd["district_observed_on"] = env.observed_on.isoformat() if env.observed_on else None
        wd.setdefault("data_source", "database")
    wd["as_of"] = as_of
    return wd
async def _dashboard_disease_params(
    db: Session, district: str
) -> Optional[Dict[str, Any]]:
    """Build the same feature dict the dashboard's Disease Outbreak Risk
    panel feeds ``/predict/disease-breakdown`` and ``/predict/disease``.

    Source mapping (must match ``frontend/app/dashboard/[district]/page.tsx``):
      - rainfall_mm / temperature_c / humidity_percent / river_level_m /
        population_density / water_quality_index:  live weather API
      - flood_depth_cm / sanitation_score:           latest WeeklyHistory row
      - previous_week_cases:                         latestWeek.weekly_cases
      - previous_two_week_cases:                     prevWeek.weekly_cases
      - season:                                      hard-coded 'Monsoon'

    Returns ``None`` if any required field is missing; callers fall back
    to the env-only code path in that case.
    """
    norm = normalize_district_for_lookup(district)
    try:
        wd = await get_weather_for_location(district)
    except Exception as exc:
        logger.warning("dashboard_params weather failed", district=district, error=str(exc))
        return None
    if not wd or wd.get("data_source") == "fallback":
        return None
    weekly_rows = await asyncio.to_thread(
        lambda: db.query(WeeklyHistory)
        .filter(func.lower(WeeklyHistory.district) == norm)
        .order_by(WeeklyHistory.week_ending.desc())
        .limit(2)
        .all()
    )
    if len(weekly_rows) < 1:
        return None
    latest = weekly_rows[0]
    prev = weekly_rows[1] if len(weekly_rows) >= 2 else latest
    params = {
        "location": district,
        "rainfall_mm": wd.get("rainfall"),
        "temperature_c": wd.get("temperature"),
        "humidity_percent": wd.get("humidity"),
        "river_level_m": wd.get("river_level_m"),
        "flood_depth_cm": float(latest.flood_depth_cm) if latest.flood_depth_cm is not None else None,
        "population_density": wd.get("population_density"),
        "sanitation_score": float(latest.sanitation_score) if latest.sanitation_score is not None else None,
        "water_quality_index": wd.get("water_quality_index"),
        "previous_week_cases": float(latest.weekly_cases or 0),
        "previous_two_week_cases": float(prev.weekly_cases or 0),
        "season": "Monsoon",
    }
    return params


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

async def t_resolve_district(db: Session, user: User, args: Dict[str, Any]) -> Dict[str, Any]:
    name = args.get("name") or args.get("district") or args.get("query") or ""
    return await resolve_district(db, name)


async def t_list_districts(db: Session, user: User, args: Dict[str, Any]) -> Dict[str, Any]:
    all_d = await _list_all_districts(db)
    return {"ok": True, "count": len(all_d), "districts": all_d, "data_source": "database", "as_of": _now_iso()}


async def t_get_weather(db: Session, user: User, args: Dict[str, Any]) -> Dict[str, Any]:
    district = args.get("district")
    if not district:
        return {"error": "Missing 'district'", "code": "missing_input"}
    resolved = await resolve_district(db, district)
    canonical = resolved.get("canonical") if resolved.get("ok") else None
    if not canonical:
        return {
            "error": "Unknown district",
            "code": "unknown_district",
            "candidates": resolved.get("candidates", []),
        }
    wd = await _weather_with_district_conditions(db, canonical)
    return {"ok": True, "district": canonical, **wd, "data_source": wd.get("data_source", "fallback")}


async def t_get_environmental_monitoring(db: Session, user: User, args: Dict[str, Any]) -> Dict[str, Any]:
    district = args.get("district")
    if not district:
        return {"error": "Missing 'district'", "code": "missing_input"}
    resolved = await resolve_district(db, district)
    if not resolved.get("ok"):
        return {
            "ok": False,
            "error": "Unknown district",
            "candidates": resolved.get("candidates", []),
        }
    canon = resolved["canonical"]
    env = await _dist_env(db, canon)
    if env is None:
        return {"ok": False, "error": f"No environmental data for '{canon}'", "code": "no_data"}
    return {
        "ok": True,
        "district": canon,
        "observed_on": env.observed_on.isoformat() if env.observed_on else None,
        "season": env.season,
        "rainfall_mm": env.rainfall_mm,
        "temperature_c": env.temperature_c,
        "humidity_percent": env.humidity_percent,
        "river_level_m": env.river_level_m,
        "flood_depth_cm": env.flood_depth_cm,
        "water_quality_index": env.water_quality_index,
        "population_density": env.population_density,
        "sanitation_score": env.sanitation_score,
        "elevation_m": env.elevation_m,
        "contamination_risk": env.contamination_risk,
        "data_source": "database",
        "as_of": _now_iso(),
    }


async def t_predict_flood(db: Session, user: User, args: Dict[str, Any]) -> Dict[str, Any]:
    district = args.get("district")
    if not district:
        return {"error": "Missing 'district'", "code": "missing_input"}
    resolved = await resolve_district(db, district)
    if not resolved.get("ok"):
        return {"ok": False, "error": "Unknown district", "candidates": resolved.get("candidates", [])}
    canon = resolved["canonical"]

    env = await _dist_env(db, canon)
    if env is None:
        return {"ok": False, "error": f"No river-level data for '{canon}'. Run get_environmental_monitoring first.", "code": "no_env"}

    try:
        payload = FloodPredictionRequest(
            location=canon,
            river_level_m=float(env.river_level_m or 0.0),
            rainfall_mm=float(env.rainfall_mm) if env.rainfall_mm is not None else None,
            temperature_c=float(env.temperature_c) if env.temperature_c is not None else None,
            humidity_percent=float(env.humidity_percent) if env.humidity_percent is not None else None,
            elevation_m=float(env.elevation_m) if env.elevation_m is not None else 20.0,
            water_quality_index=float(env.water_quality_index) if env.water_quality_index is not None else 70.0,
            population_density=float(env.population_density) if env.population_density is not None else 1500.0,
            season=env.season or "Monsoon",
        )
        # Reuse the same code path flood.py uses
        from app.routers.flood import predict_flood
        result = await predict_flood(payload, db, user)
        return {
            "ok": True,
            "district": canon,
            "flood_probability": result.flood_probability,
            "flood_risk_level": result.flood_risk_level,
            "likely_severity_if_flood": result.likely_severity_if_flood,
            "data_source": "model_prediction",
            "as_of": _now_iso(),
        }
    except Exception as exc:
        logger.warning("predict_flood failed", district=canon, error=str(exc))
        return {"ok": False, "error": str(exc), "code": "model_error"}


async def t_get_disease_risk(db: Session, user: User, args: Dict[str, Any]) -> Dict[str, Any]:
    district = args.get("district")
    if not district:
        return {"error": "Missing 'district'", "code": "missing_input"}
    resolved = await resolve_district(db, district)
    if not resolved.get("ok"):
        return {"ok": False, "error": "Unknown district", "candidates": resolved.get("candidates", [])}
    canon = resolved["canonical"]

    env = await _dist_env(db, canon)
    if env is None:
        return {"ok": False, "error": f"No env data for '{canon}'", "code": "no_env"}

    # Use the same per-district WeeklyHistory rows the dashboard's
    # Disease Outbreak Risk panel reads
    # (latestWeek.weekly_cases / prevWeek.weekly_cases).  Falling back
    # to a CommunityReport count would make the chatbot show different
    # numbers than the dashboard for the same district.
    norm = canon.lower()
    # Try to use the same feature dict the dashboard feeds into the model.
    # If live weather is unavailable, fall back to the env-based path below.
    dashboard_params = await _dashboard_disease_params(db, canon)
    weekly_rows = await asyncio.to_thread(
        lambda: db.query(WeeklyHistory)
        .filter(func.lower(WeeklyHistory.district) == norm)
        .order_by(WeeklyHistory.week_ending.desc())
        .limit(2)
        .all()
    )
    if len(weekly_rows) >= 1:
        previous_week_cases = float(weekly_rows[0].weekly_cases or 0)
    else:
        previous_week_cases = 0.0
    if len(weekly_rows) >= 2:
        previous_two_week_cases = float(weekly_rows[1].weekly_cases or 0)
    else:
        previous_two_week_cases = previous_week_cases

    try:
        from app.routers.disease import predict_disease
        if dashboard_params is not None:
            payload = DiseasePredictionRequest(**dashboard_params)
        else:
            payload = DiseasePredictionRequest(
                location=canon,
                rainfall_mm=float(env.rainfall_mm) if env.rainfall_mm is not None else None,
                temperature_c=float(env.temperature_c) if env.temperature_c is not None else None,
                humidity_percent=float(env.humidity_percent) if env.humidity_percent is not None else None,
                river_level_m=float(env.river_level_m or 0.0),
                flood_depth_cm=hb_flood_depth_cm if hb_flood_depth_cm is not None else float(env.flood_depth_cm or 0.0),
                population_density=float(env.population_density) if env.population_density is not None else 1500.0,
                sanitation_score=hb_sanitation_score if hb_sanitation_score is not None else (float(env.sanitation_score) if env.sanitation_score is not None else 0.5),
                water_quality_index=float(env.water_quality_index) if env.water_quality_index is not None else 70.0,
                previous_week_cases=previous_week_cases,
                previous_two_week_cases=previous_two_week_cases,
                # Match the dashboard's Disease Outbreak Risk panel, which
                # hard-codes season='Monsoon'.  Without this, the chat tool's
                # numbers drift away from the panel when env.season is 'Winter'.
                season="Monsoon",
            )
        result = await predict_disease(payload, db, user)
        return {
            "ok": True,
            "district": canon,
            "predicted_outbreak_risk": result.predicted_outbreak_risk,
            "risk_probability_by_class": result.risk_probability_by_class,
            "feature_importance": result.feature_importance,
            "data_source": "model_prediction",
            "as_of": _now_iso(),
        }
    except Exception as exc:
        logger.warning("get_disease_risk failed", district=canon, error=str(exc))
        return {"ok": False, "error": str(exc), "code": "model_error"}


async def t_get_disease_breakdown(db: Session, user: User, args: Dict[str, Any]) -> Dict[str, Any]:
    district = args.get("district")
    if not district:
        return {"error": "Missing 'district'", "code": "missing_input"}
    resolved = await resolve_district(db, district)
    if not resolved.get("ok"):
        return {"ok": False, "error": "Unknown district", "candidates": resolved.get("candidates", [])}
    canon = resolved["canonical"]
    env = await _dist_env(db, canon)
    if env is None:
        return {"ok": False, "error": f"No env data for '{canon}'", "code": "no_env"}

    # Use the same per-district WeeklyHistory rows the dashboard's
    # Disease Outbreak Risk panel reads
    # (latestWeek.weekly_cases / prevWeek.weekly_cases).  Falling back
    # to a CommunityReport count would make the chatbot show different
    # numbers than the dashboard for the same district.
    norm = canon.lower()
    # Try to use the same feature dict the dashboard feeds into the model.
    # If live weather is unavailable, fall back to the env-based path below.
    dashboard_params = await _dashboard_disease_params(db, canon)
    weekly_rows = await asyncio.to_thread(
        lambda: db.query(WeeklyHistory)
        .filter(func.lower(WeeklyHistory.district) == norm)
        .order_by(WeeklyHistory.week_ending.desc())
        .limit(2)
        .all()
    )
    if len(weekly_rows) >= 1:
        previous_week_cases = float(weekly_rows[0].weekly_cases or 0)
    else:
        previous_week_cases = 0.0
    if len(weekly_rows) >= 2:
        previous_two_week_cases = float(weekly_rows[1].weekly_cases or 0)
    else:
        previous_two_week_cases = previous_week_cases

    # The dashboard's Disease Outbreak Risk panel uses the *latest week* of
    # WeeklyHistory for flood_depth_cm / sanitation_score (not the live env
    # snapshot).  Mirror that here so the chat tool's numbers match the
    # panel exactly.
    latest_weekly = weekly_rows[0] if weekly_rows else None
    hb_flood_depth_cm = (
        float(latest_weekly.flood_depth_cm)
        if latest_weekly is not None and latest_weekly.flood_depth_cm is not None
        else None
    )
    hb_sanitation_score = (
        float(latest_weekly.sanitation_score)
        if latest_weekly is not None and latest_weekly.sanitation_score is not None
        else None
    )

    if models.disease_breakdown_models is None:
        return {
            "ok": False,
            "error": "Disease-breakdown model is not loaded on this server",
            "code": "model_unavailable",
        }

    try:
        from app.routers.disease_breakdown import predict_disease_breakdown
        # Prefer the dashboard-equivalent feature dict when live weather is
        # available; otherwise fall back to the env+weekly hybrid.
        if dashboard_params is not None:
            payload = DiseaseBreakdownRequest(**dashboard_params)
        else:
            payload = DiseaseBreakdownRequest(
                location=canon,
                rainfall_mm=float(env.rainfall_mm) if env.rainfall_mm is not None else None,
                temperature_c=float(env.temperature_c) if env.temperature_c is not None else None,
                humidity_percent=float(env.humidity_percent) if env.humidity_percent is not None else None,
                river_level_m=float(env.river_level_m or 0.0),
                flood_depth_cm=hb_flood_depth_cm if hb_flood_depth_cm is not None else float(env.flood_depth_cm or 0.0),
                population_density=float(env.population_density) if env.population_density is not None else 1500.0,
                sanitation_score=hb_sanitation_score if hb_sanitation_score is not None else (float(env.sanitation_score) if env.sanitation_score is not None else 0.5),
                water_quality_index=float(env.water_quality_index) if env.water_quality_index is not None else 70.0,
                previous_week_cases=previous_week_cases,
                previous_two_week_cases=previous_two_week_cases,
                # Match the dashboard's Disease Outbreak Risk panel, which
                # hard-codes season='Monsoon'.  Without this, the chat tool's
                # numbers drift away from the panel when env.season is 'Winter'.
                season="Monsoon",
            )
        result = await predict_disease_breakdown(payload)
        return {
            "ok": True,
            "district": canon,
            "disease_breakdown": result.disease_breakdown,
            "dominant_disease": result.dominant_disease,
            "total_predicted_cases": result.total_predicted_cases,
            "data_source": "model_prediction",
            "as_of": _now_iso(),
        }
    except Exception as exc:
        logger.warning("get_disease_breakdown failed", district=canon, error=str(exc))
        return {"ok": False, "error": str(exc), "code": "model_error"}


async def t_get_forecast(db: Session, user: User, args: Dict[str, Any]) -> Dict[str, Any]:
    district = args.get("district")
    if not district:
        return {"error": "Missing 'district'", "code": "missing_input"}
    resolved = await resolve_district(db, district)
    if not resolved.get("ok"):
        return {"ok": False, "error": "Unknown district", "candidates": resolved.get("candidates", [])}
    canon = resolved["canonical"]

    # Pull the 8 most recent weeks of real history.  If unavailable the
    # endpoint 404s; we surface the same honesty to the LLM.
    try:
        hist = await asyncio.to_thread(get_weekly_history, canon, db)
        weeks = hist.weeks
    except Exception as exc:
        return {"ok": False, "error": str(exc), "code": "history_unavailable"}

    if models.timeseries_model is None:
        return {"ok": False, "error": "LSTM forecast model is unavailable", "code": "model_unavailable"}

    try:
        from app.routers.forecast import forecast
        from app.schemas import WeeklyObservation
        recent_weeks = [
            WeeklyObservation(
                weekly_cases=w.weekly_cases,
                rainfall_mm=w.rainfall_mm,
                temperature_c=w.temperature_c,
                flood_depth_cm=w.flood_depth_cm,
                sanitation_score=w.sanitation_score,
            )
            for w in weeks
        ]
        payload = ForecastRequest(district=canon, recent_weeks=recent_weeks)
        # forecast is a sync def; the LSTM predict is CPU-bound — run in a
        # threadpool so we don't block the event loop.
        result = await asyncio.to_thread(forecast, payload, db, user)
        return {
            "ok": True,
            "district": canon,
            "forecast_next_7_days_cases": result.forecast_next_7_days_cases,
            "forecast_next_14_days_cases": result.forecast_next_14_days_cases,
            "history_weeks_used": len(weeks),
            "data_source": "model_prediction",
            "as_of": _now_iso(),
        }
    except Exception as exc:
        logger.warning("get_forecast failed", district=canon, error=str(exc))
        return {"ok": False, "error": str(exc), "code": "model_error"}


async def t_get_risk_score(db: Session, user: User, args: Dict[str, Any]) -> Dict[str, Any]:
    district = args.get("district")
    if not district:
        return {"error": "Missing 'district'", "code": "missing_input"}
    resolved = await resolve_district(db, district)
    if not resolved.get("ok"):
        return {"ok": False, "error": "Unknown district", "candidates": resolved.get("candidates", [])}
    canon = resolved["canonical"]
    env = await _dist_env(db, canon)
    if env is None:
        return {"ok": False, "error": f"No env data for '{canon}'", "code": "no_env"}

    # Use the same per-district WeeklyHistory rows the dashboard's
    # Disease Outbreak Risk panel reads
    # (latestWeek.weekly_cases / prevWeek.weekly_cases).  Falling back
    # to a CommunityReport count would make the chatbot show different
    # numbers than the dashboard for the same district.
    norm = canon.lower()
    dashboard_params = await _dashboard_disease_params(db, canon)
    weekly_rows = await asyncio.to_thread(
        lambda: db.query(WeeklyHistory)
        .filter(func.lower(WeeklyHistory.district) == norm)
        .order_by(WeeklyHistory.week_ending.desc())
        .limit(2)
        .all()
    )
    if len(weekly_rows) >= 1:
        previous_week_cases = float(weekly_rows[0].weekly_cases or 0)
    else:
        previous_week_cases = 0.0
    if len(weekly_rows) >= 2:
        previous_two_week_cases = float(weekly_rows[1].weekly_cases or 0)
    else:
        previous_two_week_cases = previous_week_cases

    # The dashboard's Disease Outbreak Risk panel uses the *latest week* of
    # WeeklyHistory for flood_depth_cm / sanitation_score (not the live env
    # snapshot).  Mirror that here so the chat tool's numbers match the
    # panel exactly.
    latest_weekly = weekly_rows[0] if weekly_rows else None
    hb_flood_depth_cm = (
        float(latest_weekly.flood_depth_cm)
        if latest_weekly is not None and latest_weekly.flood_depth_cm is not None
        else None
    )
    hb_sanitation_score = (
        float(latest_weekly.sanitation_score)
        if latest_weekly is not None and latest_weekly.sanitation_score is not None
        else None
    )

    try:
        if dashboard_params is not None:
            payload = RiskScoreRequest(**dashboard_params)
        else:
            payload = RiskScoreRequest(
                location=canon,
                rainfall_mm=float(env.rainfall_mm) if env.rainfall_mm is not None else None,
                temperature_c=float(env.temperature_c) if env.temperature_c is not None else None,
                humidity_percent=float(env.humidity_percent) if env.humidity_percent is not None else None,
                river_level_m=float(env.river_level_m or 0.0),
                flood_depth_cm=hb_flood_depth_cm if hb_flood_depth_cm is not None else float(env.flood_depth_cm or 0.0),
                population_density=float(env.population_density) if env.population_density is not None else 1500.0,
                sanitation_score=hb_sanitation_score if hb_sanitation_score is not None else (float(env.sanitation_score) if env.sanitation_score is not None else 0.5),
                water_quality_index=float(env.water_quality_index) if env.water_quality_index is not None else 70.0,
                previous_week_cases=previous_week_cases,
                previous_two_week_cases=previous_two_week_cases,
                # Match the dashboard's Disease Outbreak Risk panel, which
                # hard-codes season='Monsoon'.  Without this, the chat tool's
                # numbers drift away from the panel when env.season is 'Winter'.
                season="Monsoon",
            )
        result = await compute_risk_score(payload)
        return {
            "ok": True,
            "district": canon,
            "predicted_outbreak_risk": result.predicted_outbreak_risk,
            "flood_severity": result.flood_severity,
            "composite_score": result.composite_score,
            "final_risk_level": result.final_risk_level,
            "data_source": "model_prediction",
            "as_of": _now_iso(),
        }
    except Exception as exc:
        logger.warning("get_risk_score failed", district=canon, error=str(exc))
        return {"ok": False, "error": str(exc), "code": "model_error"}


async def t_get_satellite_flood_extent(db: Session, user: User, args: Dict[str, Any]) -> Dict[str, Any]:
    district = args.get("district")
    if not district:
        return {"error": "Missing 'district'", "code": "missing_input"}
    resolved = await resolve_district(db, district)
    if not resolved.get("ok"):
        return {"ok": False, "error": "Unknown district", "candidates": resolved.get("candidates", [])}
    canon = resolved["canonical"]

    target = _normalize_satellite_district(canon)
    rows = await asyncio.to_thread(lambda: db.query(SatelliteExtent).all())
    matched = next(
        (r for r in rows if _normalize_satellite_district(r.district) == target), None
    )
    available = sorted({r.district for r in rows})

    if matched is None:
        return {
            "ok": False,
            "available": available,
            "error": f"No satellite flood-extent export registered for '{canon}'. Currently available: {available}",
            "code": "not_available",
        }

    # Flood area km² approximated from polygon coordinates — count coords and
    # use a simple per-coordinate area estimate.  This is a *rough* derived
    # number so the tool can return something the LLM can quote.
    poly = (matched.geojson or {}).get("features", [{}])[0].get("geometry", {}).get("coordinates", [[]])
    # Coordinates are [[[lon, lat], ...]].  Approximate area: lateral km
    # between consecutive vertices times a longitudinal scaling.  Suitable as
    # an estimate only.
    import math
    approx_km2 = 0.0
    if poly and len(poly[0]) >= 4:
        ring = poly[0]
        for i in range(len(ring) - 1):
            x1, y1 = ring[i][:2]
            x2, y2 = ring[i + 1][:2]
            dx = (x2 - x1) * 111.32 * math.cos(math.radians(y1))  # km
            dy = (y2 - y1) * 110.57                              # km
            approx_km2 += abs(dx) * abs(dy) * 0.5                # approximate polygon contribution
        # Polygon area is roughly sum of triangle areas -> use shoelace once

    # Recompute with shoelace in km space
    shoelace = 0.0
    if poly and len(poly[0]) >= 4:
        ring = poly[0]
        for i in range(len(ring) - 1):
            x1 = ring[i][0] * 111.32 * math.cos(math.radians(ring[i][1]))
            y1 = ring[i][1] * 110.57
            x2 = ring[i + 1][0] * 111.32 * math.cos(math.radians(ring[i + 1][1]))
            y2 = ring[i + 1][1] * 110.57
            shoelace += (x1 * y2) - (x2 * y1)
        approx_km2 = round(abs(shoelace) / 2.0, 2)

    return {
        "ok": True,
        "district": matched.district,
        "event_label": matched.event_label,
        "approx_flood_area_km2": approx_km2,
        "geojson_available": True,
        "data_source": "database",
        "as_of": _now_iso(),
    }


async def t_get_hospital_resources(db: Session, user: User, args: Dict[str, Any]) -> Dict[str, Any]:
    district = args.get("district")
    if not district:
        return {"error": "Missing 'district'", "code": "missing_input"}
    resolved = await resolve_district(db, district)
    if not resolved.get("ok"):
        return {"ok": False, "error": "Unknown district", "candidates": resolved.get("candidates", [])}
    canon = resolved["canonical"]

    if user.role not in OPERATIONAL_ROLES:
        return {
            "ok": False,
            "code": "permission_denied",
            "error": "Hospital stock, ORS, IV saline and antibiotic counts are restricted to operational roles "
                     "(hospital, health-worker, NGO, government, admin).",
        }

    agg = await _hospital_agg(db, canon)
    if agg is None:
        return {"ok": False, "error": f"No hospital aggregate for '{canon}'", "code": "no_data"}
    return {
        "ok": True,
        "district": agg.district,
        "hospital_count": int(agg.hospital_count or 0),
        "beds": int(agg.beds or 0),
        "doctors": int(agg.doctors or 0),
        "nurses": int(agg.nurses or 0),
        "ors_stock": int(agg.ors_stock or 0),
        "iv_saline_stock": int(agg.iv_saline_stock or 0),
        "antibiotics_stock": int(agg.antibiotics_stock or 0),
        "occupancy_percent": float(agg.occupancy_percent or 0),
        "data_source": "database",
        "as_of": _now_iso(),
    }


async def t_get_recommendations(db: Session, user: User, args: Dict[str, Any]) -> Dict[str, Any]:
    district = args.get("district")
    risk_level = args.get("risk_level") or "Medium"
    if not district:
        return {"error": "Missing 'district'", "code": "missing_input"}
    resolved = await resolve_district(db, district)
    if not resolved.get("ok"):
        return {"ok": False, "error": "Unknown district", "candidates": resolved.get("candidates", [])}
    canon = resolved["canonical"]

    if user.role not in OPERATIONAL_ROLES:
        return {
            "ok": False,
            "code": "permission_denied",
            "error": "Operational-recommendation tooling is restricted to operational roles.",
        }

    try:
        reco = await asyncio.to_thread(_recommend_for_district, db, canon, risk_level)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "code": "recommend_unavailable"}
    return {
        "ok": True,
        "district": reco.district,
        "risk_level": reco.risk_level,
        "recommendations": reco.recommendations,
        "hospital_beds_available": reco.hospital_beds_available,
        "occupancy_percent": reco.occupancy_percent,
        "data_source": "model_prediction",
        "as_of": _now_iso(),
    }


async def t_get_top_at_risk_districts(db: Session, user: User, args: Dict[str, Any]) -> Dict[str, Any]:
    n = int(args.get("n", 5))
    n = max(1, min(n, 64))

    def _load() -> List[Dict[str, Any]]:
        rows = db.query(DistrictHospitalAggregate).all()
        items: List[Dict[str, Any]] = []
        for row in rows:
            d_name = row.district
            occ = float(row.occupancy_percent or 0.0)
            ors_low = int(row.ors_stock or 0) < 1000
            iv_low = int(row.iv_saline_stock or 0) < 500
            strained = occ > 80.0 or ors_low or iv_low
            flood_prone = d_name.strip().lower() in _FLOOD_PRONE_DISTRICTS
            if flood_prone and strained:
                risk_level, composite = "Critical", 2.85
            elif flood_prone or occ > 75.0:
                risk_level, composite = "High", 2.10
            elif occ > 50.0:
                risk_level, composite = "Medium", 1.35
            else:
                risk_level, composite = "Low", 0.60
            items.append(
                {
                    "district": d_name,
                    "risk_level": risk_level,
                    "composite_score": composite,
                    "occupancy_percent": occ,
                }
            )
        return items

    items = await asyncio.to_thread(_load)
    items.sort(key=lambda r: r["composite_score"], reverse=True)
    top = items[:n]
    return {
        "ok": True,
        "top_n": top,
        "ranking_basis": "occupancy_percent + flood-prone lookup",
        "data_source": "database",
        "as_of": _now_iso(),
    }


async def t_get_disease_knowledge(db: Session, user: User, args: Dict[str, Any]) -> Dict[str, Any]:
    name = (args.get("disease") or "").strip()
    if not name:
        return {"error": "Missing 'disease'", "code": "missing_input"}

    articles = await asyncio.to_thread(get_articles_from_db, db)
    name_l = name.lower()

    def _norm(s: str) -> str:
        return (s or "").replace("_", " ").lower()

    match: Optional[KnowledgeArticle] = None
    for art in articles:
        if _norm(art.disease_name) == _norm(name):
            match = art
            break
    if match is None:
        # Try fuzzy
        cands = process.extract(name_l, [_norm(a.disease_name) for a in articles], scorer=fuzz.WRatio, limit=3)
        scored = [(c, s) for c, s, _ in cands if s >= 75]
        if scored:
            best, _ = scored[0]
            for art in articles:
                if _norm(art.disease_name) == best:
                    match = art
                    break
            if match is not None:
                candidates_for_llm = [a for n, a in [(c, next(x for x in articles if _norm(x.disease_name) == c)) for c, _ in scored]]
                return {
                    "ok": True,
                    "matched_via": "fuzzy",
                    "disease": match.disease_name,
                    "symptoms": match.symptoms,
                    "causes": match.causes,
                    "prevention": match.prevention_tips,
                    "home_care": match.home_care_guidance,
                    "when_to_see_doctor": match.when_to_see_doctor,
                    "emergency_contact": match.emergency_contact_info or "999",
                    "reference": match.reference,
                    "data_source": "database",
                    "as_of": _now_iso(),
                }
        return {
            "ok": False,
            "error": f"'{name}' is not in my verified knowledge base. I only have grounded guidance for the diseases on my list. "
                     f"Please consult a licensed physician or call 999 for emergencies.",
            "code": "not_in_knowledge_base",
            "available": sorted({a.disease_name for a in articles}),
        }
    return {
        "ok": True,
        "disease": match.disease_name,
        "symptoms": match.symptoms,
        "causes": match.causes,
        "prevention": match.prevention_tips,
        "home_care": match.home_care_guidance,
        "when_to_see_doctor": match.when_to_see_doctor,
        "emergency_contact": match.emergency_contact_info or "999",
        "reference": match.reference,
        "data_source": "database",
        "as_of": _now_iso(),
    }


# ---------------------------------------------------------------------------
# UI actions
# ---------------------------------------------------------------------------

UI_ACTION_ALLOWED_TYPES_OPERATIONAL = {
    "navigate",
    "select_district",
    "run_flood_check",
    "run_full_assessment",
    "open_satellite_view",
    "open_alerts",
    "open_reports",
    "open_hospital_resources",
    "open_hospital_directory",
    "open_hospital",
}

# Citizens can ALSO use open_hospital_directory -- the Directory tab is
# the public directory, not the operational inventory editor.
UI_ACTION_ALLOWED_TYPES_CITIZEN = {
    "navigate",
    "select_district",
    "run_flood_check",
    "open_satellite_view",
    "open_alerts",
    "open_reports",
    "open_hospital_directory",
    "open_hospital",
}


def whitelist_ui_action(action: Dict[str, Any], user_role: UserRole) -> Dict[str, Any]:
    """Server-side whitelist for any UI action the LLM tries to emit.

    Returns the cleaned action or an error dict.
    """
    if not isinstance(action, dict):
        return {"error": "action must be an object", "code": "bad_action"}
    t = action.get("type")
    params = action.get("params", {}) or {}
    allowed = UI_ACTION_ALLOWED_TYPES_OPERATIONAL if user_role in OPERATIONAL_ROLES else UI_ACTION_ALLOWED_TYPES_CITIZEN
    if t not in allowed:
        return {"error": f"action type '{t}' not allowed for role {user_role}", "code": "permission_denied"}

    if t == "navigate":
        route = params.get("route") or ""
        # Allow only known dashboard/admin/auth routes
        allowed_prefixes = ("/dashboard", "/alerts", "/login", "/signup", "/admin")
        if not any(route.startswith(p) for p in allowed_prefixes):
            return {"error": f"route '{route}' not whitelisted", "code": "bad_action"}
        return {"type": "navigate", "params": {"route": route}}
    if t == "select_district":
        d = params.get("district")
        if not d:
            return {"error": "missing district", "code": "bad_action"}
        return {"type": "select_district", "params": {"district": str(d)}}
    if t == "run_flood_check":
        d = params.get("district")
        if not d:
            return {"error": "missing district", "code": "bad_action"}
        return {"type": "run_flood_check", "params": {"district": str(d)}}
    if t == "run_full_assessment":
        if user_role not in OPERATIONAL_ROLES:
            return {"error": "run_full_assessment is for operational roles only", "code": "permission_denied"}
        d = params.get("district")
        if not d:
            return {"error": "missing district", "code": "bad_action"}
        return {"type": "run_full_assessment", "params": {"district": str(d)}}
    if t in ("open_satellite_view", "open_alerts", "open_reports", "open_hospital_resources"):
        if t == "open_hospital_resources" and user_role not in OPERATIONAL_ROLES:
            return {"error": "open_hospital_resources is for operational roles only", "code": "permission_denied"}
        return {"type": t, "params": {}}
    if t == "open_hospital_directory":
        # Public -- works for citizens and operational users.
        # Pass through an optional district so the frontend can deep-link
        # into a specific district view.
        d = params.get("district")
        if d and not isinstance(d, str):
            return {"error": "district must be a string", "code": "bad_action"}
        return {"type": t, "params": {"district": d} if d else {}}
    if t == "open_hospital":
        # Deep-link into a specific hospital's detail modal.  Public
        # for citizens and ops; the frontend opens the directory's
        # HospitalDetailModal and pre-selects the given hospital_id.
        # We require hospital_id so we never open a blank modal.
        hid = params.get("hospital_id")
        if not hid or not isinstance(hid, str):
            return {"error": "open_hospital requires hospital_id", "code": "bad_action"}
        try:
            from uuid import UUID as _UUID
            _UUID(hid)
        except ValueError:
            return {"error": "open_hospital hospital_id must be a UUID", "code": "bad_action"}
        out_params: Dict[str, Any] = {"hospital_id": hid}
        d = params.get("district")
        if isinstance(d, str) and d:
            out_params["district"] = d
        return {"type": "open_hospital", "params": out_params}
    return {"error": f"unknown action type {t}", "code": "bad_action"}


async def t_ui_action(db: Session, user: User, args: Dict[str, Any]) -> Dict[str, Any]:
    action = args.get("action") or {}
    cleaned = whitelist_ui_action(action, user.role)
    if "error" in cleaned:
        return cleaned
    return {"ok": True, "ui_action": cleaned}


async def t_submit_incident_report(db: Session, user: User, args: Dict[str, Any]) -> Dict[str, Any]:
    text = (args.get("text") or "").strip()
    if not text:
        return {"error": "Missing 'text'", "code": "missing_input"}
    district = args.get("district") or user.district or None
    label, severity, recommended_action = _classify_incident_text(text)
    try:
        from app.chat_models import ChatMessage
        from datetime import datetime, timezone
        from app.chat_models import ChatIntentType
        # Persist via chat_messages (the existing incident persistence path
        # the chatbot router uses) so the row shows up in API or admin views.
        msg = ChatMessage(
            user_id=user.id,
            conversation_id="incident_agent",
            role="user",
            content=text,
            detected_intent=ChatIntentType.incident_report,
            used_live_data="false",
        )
        db.add(msg)
        await asyncio.to_thread(db.commit)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "code": "persist_failed"}
    return {
        "ok": True,
        "label": label,
        "severity": severity,
        "recommended_action": recommended_action,
        "district": district,
        "message": "Incident recorded. Thank you for the report.",
        "data_source": "database",
        "as_of": _now_iso(),
    }


def _classify_incident_text(text: str) -> tuple[str, str, str]:
    """Lightweight rule-based classifier mirroring the existing chatbot taxonomy.

    Returns (label, severity, recommended_action).  The LLM can call this
    tool with longer user text; the classifier is best-effort — the existing
    LLM-fallback at /chatbot/report-incident may produce richer labels.
    """
    t = (text or "").lower()
    if any(w in t for w in ["water", "contaminat", "dirty", "pollution", "discolor"]):
        return "water_contamination", "Medium", "Verify source, advise on chlorination."
    if any(w in t for w in ["fever", "diarrhea", "vomit", "illness", "sick", "symptom"]):
        return "disease_symptom", "High", "Encourage the user to seek medical attention."
    if any(w in t for w in ["flood", "water ", "overflow", "submerged", "inundat"]):
        return "flood_impact", "High", "Verify with satellite feed and local reports."
    if any(w in t for w in ["sanitation", "waste", "dirty", "hygiene", "garbage"]):
        return "sanitation_issue", "Medium", "Log the issue against the responsible union parishad."
    if any(w in t for w in ["hospital", "bed", "medicine", "crowded", "resource"]):
        return "hospital_issue", "Medium", "Check hospital capacity / stock levels."
    return "normal", "Low", "Log as a routine update."


# ---------------------------------------------------------------------------
# Anthropic tool-use schemas
# ---------------------------------------------------------------------------


async def t_file_hospital_issue(db: Session, user: User, args: Dict[str, Any]) -> Dict[str, Any]:
    """File a user-reported issue against a hospital.

    Called by the LLM whenever a citizen describes a problem with a
    specific hospital (wrong phone, wrong address, doctor absent, no
    stock, etc.).  The LLM picks a hospital_id and a category from the
    fixed vocabulary; we persist the row in hospital_issue_reports with
    status="open" so it lands in the admin inbox and the per-hospital
    recent-reports panel.

    RBAC: any authenticated user.  We do not dedupe at this layer --
    the admin inbox is a low-volume feed and the human reviewer uses
    the description as the dedupe key.
    """
    from uuid import UUID
    from app.reference_models import Hospital, HospitalIssueReport
    raw_id = (args.get("hospital_id") or "").strip()
    category = (args.get("category") or "").strip()
    description = (args.get("description") or "").strip()
    if not raw_id:
        return {"error": "Missing 'hospital_id'", "code": "missing_input"}
    if not category:
        return {"error": "Missing 'category'", "code": "missing_input"}
    if not description:
        return {"error": "Missing 'description'", "code": "missing_input"}
    try:
        hid = UUID(raw_id)
    except ValueError:
        return {"error": "Invalid hospital_id format", "code": "bad_input"}
    from app.routers.hospitals_issues import ALLOWED_CATEGORIES
    if category not in ALLOWED_CATEGORIES:
        return {
            "error": f"category must be one of: {sorted(ALLOWED_CATEGORIES)}",
            "code": "bad_input",
        }
    h = await asyncio.to_thread(
        db.query(Hospital).filter(Hospital.id == hid).first
    )
    if h is None:
        return {"error": "Hospital not found", "code": "not_found"}
    role_str = user.role.value if hasattr(user.role, "value") else str(user.role)
    row = HospitalIssueReport(
        hospital_id=hid,
        reporter_id=user.id,
        reporter_role=role_str,
        category=category,
        description=description[:2000],
        status="open",
    )
    try:
        db.add(row)
        await asyncio.to_thread(db.commit)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "code": "persist_failed"}
    # Build the post-tool UI action so the chatbot widget can open
    # this hospital's detail modal automatically.  We whitelisted
    # `open_hospital` for both citizens and ops above, so this works
    # for any authenticated user.
    ui_action = {
        "type": "open_hospital",
        "params": {"hospital_id": str(hid), "district": h.district},
    }
    return {
        "ok": True,
        "issue_id": str(row.id),
        "hospital_id": str(hid),
        "hospital_name": h.name,
        "district": h.district,
        "category": category,
        "status": "open",
        "message": "Issue filed. An admin will review it shortly.",
        "ui_action": ui_action,
        "data_source": "database",
        "as_of": _now_iso(),
    }


TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "name": "resolve_district",
        "description": "Resolve a free-form district name (English, Bangla, alias, misspelling) to its canonical 64-district spelling. Always call this first when the user's question names a district and you are not 100% certain of the canonical name.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Free-form district name as the user wrote it."},
            },
            "required": ["name"],
        },
    },
    {
        "name": "list_districts",
        "description": "Return the canonical list of all 64 districts supported by FloodShield.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_weather",
        "description": "Fetch the live weather for a district: temperature, humidity, wind, rainfall. Returns the actual numbers with data_source (live_api | fallback).",
        "input_schema": {
            "type": "object",
            "properties": {"district": {"type": "string"}},
            "required": ["district"],
        },
    },
    {
        "name": "get_environmental_monitoring",
        "description": "Return the latest river level, water quality, rainfall, flood depth and season for a district (database-sourced). This is the 'water level' answer the user wants when they ask 'water level of <district>'.",
        "input_schema": {
            "type": "object",
            "properties": {"district": {"type": "string"}},
            "required": ["district"],
        },
    },
    {
        "name": "predict_flood",
        "description": "Run FloodShield Model 1 (binary flood classifier) for a district using the latest environmental conditions. Returns flood_probability, flood_risk_level and likely_severity_if_flood.",
        "input_schema": {
            "type": "object",
            "properties": {"district": {"type": "string"}},
            "required": ["district"],
        },
    },
    {
        "name": "get_disease_risk",
        "description": "Run FloodShield Model 2 (3-class outbreak classifier) and return predicted_outbreak_risk plus class probabilities for a district.",
        "input_schema": {
            "type": "object",
            "properties": {"district": {"type": "string"}},
            "required": ["district"],
        },
    },
    {
        "name": "get_disease_breakdown",
        "description": "Run FloodShield Model 2B (6 per-disease XGBoost regressors) and return per-disease predicted cases, dominant disease and total predicted cases for a district. This is the answer to 'disease cases in <district>'.",
        "input_schema": {
            "type": "object",
            "properties": {"district": {"type": "string"}},
            "required": ["district"],
        },
    },
    {
        "name": "get_forecast",
        "description": "Run FloodShield Model 3 (LSTM) on the latest 8 weeks of real weekly observations. Returns forecast_next_7_days_cases and forecast_next_14_days_cases. If fewer than 8 real weeks exist for the district, returns an honest 'history_unavailable' error.",
        "input_schema": {
            "type": "object",
            "properties": {"district": {"type": "string"}},
            "required": ["district"],
        },
    },
    {
        "name": "get_risk_score",
        "description": "Run FloodShield Model 5 (composite risk) and return final_risk_level plus composite_score for a district.",
        "input_schema": {
            "type": "object",
            "properties": {"district": {"type": "string"}},
            "required": ["district"],
        },
    },
    {
        "name": "get_satellite_flood_extent",
        "description": "Check whether a satellite-export polygon exists for a district. Returns event_label, approx area in km² when available, or an honest 'not available yet' otherwise.",
        "input_schema": {
            "type": "object",
            "properties": {"district": {"type": "string"}},
            "required": ["district"],
        },
    },
    {
        "name": "get_hospital_resources",
        "description": "Return hospital capacity (beds, occupancy, ORS/IV/antibiotic stock) for a district. OPERATIONAL ROLES ONLY — returns permission_denied for citizens.",
        "input_schema": {
            "type": "object",
            "properties": {"district": {"type": "string"}},
            "required": ["district"],
        },
    },
    {
        "name": "get_recommendations",
        "description": "Return the per-district action list (restock, escalate, deploy EMT, etc.) using FloodShield Model 6. OPERATIONAL ROLES ONLY.",
        "input_schema": {
            "type": "object",
            "properties": {
                "district": {"type": "string"},
                "risk_level": {
                    "type": "string",
                    "enum": ["Low", "Medium", "High", "Critical"],
                    "description": "Risk level input to Model 6 (typically from get_risk_score).",
                },
            },
            "required": ["district"],
        },
    },
    {
        "name": "get_top_at_risk_districts",
        "description": "Return the top N at-risk districts (default 5), same ranking the dashboard map and ranking panel use.",
        "input_schema": {
            "type": "object",
            "properties": {
                "n": {"type": "integer", "minimum": 1, "maximum": 64, "default": 5},
            },
            "required": [],
        },
    },
    {
        "name": "get_disease_knowledge",
        "description": "Return verified medical guidance (symptoms, causes, prevention, home care, when to see doctor, emergency contact) for one disease. ONLY the diseases returned in 'available' are verified — anything else returns an honest 'not in my knowledge base' result.",
        "input_schema": {
            "type": "object",
            "properties": {"disease": {"type:": "string", "type": "string"}},
            "required": ["disease"],
        },
    },
    {
        "name": "submit_incident_report",
        "description": "Classify and persist a citizen's free-text incident report. Server applies the existing 6-class taxonomy (water_contamination, disease_symptom, flood_impact, sanitation_issue, hospital_issue, normal).",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "district": {"type:": "string", "type": "string", "description": "Optional district name; falls back to user's profile district."},
            },
            "required": ["text"],
        },
    },
    {
        "name": "file_hospital_issue",
        "description": "File a user-reported issue against a specific hospital (wrong phone, wrong address, name wrong, closed, no doctor on duty, no stock, coordinates wrong, or other). Pick the hospital_id from a previous get_hospital_resources or hospital lookup. The row lands in the admin issue inbox with status=open; do NOT use this for generic reports (use submit_incident_report instead).",
        "input_schema": {
            "type": "object",
            "properties": {
                "hospital_id": {"type": "string", "description": "UUID of the hospital the report is about."},
                "category": {"type": "string", "enum": ["phone_wrong","address_wrong","name_wrong","closed","no_doctor","no_stock","coordinates_wrong","other"]},
                "description": {"type": "string", "description": "One or two sentences in plain English."},
            },
            "required": ["hospital_id", "category", "description"],
        },
    },
    {
        "name": "ui_action",
        "description": "Emit a UI action for the chatbot widget to execute on the user's screen (navigate, select_district, run_flood_check, open_*, etc). Server whitelists the action by role and route; unrecognised types are rejected.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": sorted(UI_ACTION_ALLOWED_TYPES_OPERATIONAL | UI_ACTION_ALLOWED_TYPES_CITIZEN),
                        },
                        "params": {"type": "object"},
                    },
                    "required": ["type"],
                },
            },
            "required": ["action"],
        },
    },
]


TOOL_DISPATCH: Dict[str, Callable[..., Awaitable[Any]]] = {
    "resolve_district": t_resolve_district,
    "list_districts": t_list_districts,
    "get_weather": t_get_weather,
    "get_environmental_monitoring": t_get_environmental_monitoring,
    "predict_flood": t_predict_flood,
    "get_disease_risk": t_get_disease_risk,
    "get_disease_breakdown": t_get_disease_breakdown,
    "get_forecast": t_get_forecast,
    "get_risk_score": t_get_risk_score,
    "get_satellite_flood_extent": t_get_satellite_flood_extent,
    "get_hospital_resources": t_get_hospital_resources,
    "get_recommendations": t_get_recommendations,
    "get_top_at_risk_districts": t_get_top_at_risk_districts,
    "get_disease_knowledge": t_get_disease_knowledge,
    "submit_incident_report": t_submit_incident_report,
    "file_hospital_issue": t_file_hospital_issue,
    "ui_action": t_ui_action,
}
