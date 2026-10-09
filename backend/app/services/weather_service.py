"""
Live weather service.

`/api/weather` resolves the requested district's coordinates via
OpenWeatherMap, then enriches the response with the latest persisted
district-level environmental conditions from the `district_env` table.

Both the live weather call and the per-district enrichment are cached:
- OpenWeatherMap response: 30-minute TTL (process-local cache)
- district_env snapshot:    5-minute TTL (DB is cheap to re-read but
                             avoid hammering it on every dashboard hit)
"""
from __future__ import annotations

import time
from typing import Any, Dict

import httpx
from fastapi import HTTPException

from app.config import WEATHER_API_KEY
from app.database import SessionLocal
from app.reference_models import DistrictEnv

# Per-process weather cache: { location_lowercase: {"data": ..., "timestamp": ...} }
_weather_cache: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 1800  # 30 minutes

_district_cache: dict[str, tuple[float, dict[str, dict[str, Any]]]] = {}
DISTRICT_CACHE_TTL = 300  # 5 minutes


# Mapping of district names that have changed over time (e.g. government
# official rename, common misspelling).  Both sides are lowercase.
DISTRICT_ALIASES = {
    "cumilla": "comilla",
    "bogura": "bogra",
    "jashore": "jashore",
    "chattogram": "chattogram",
    "comilla": "comilla",
    "bogra": "bogra",
    "jessore": "jashore",
    "chittagong": "chattogram",
}


def normalize_district_for_lookup(location: str) -> str:
    """Return the canonical DB key for a given district name.
    Falls back to the lowercased input if no alias is registered.
    """
    key = location.strip().lower()
    return DISTRICT_ALIASES.get(key, key)


def _latest_district_conditions() -> dict[str, dict[str, Any]]:
    """Latest per-district env reading, read from the `district_env` table.

    Cached for 5 minutes per process; admin re-seeds invalidate naturally
    because the cache key is a fixed dict snapshot.
    """
    now = time.time()
    cached = _district_cache.get("all")
    if cached and now - cached[0] < DISTRICT_CACHE_TTL:
        return cached[1]

    latest: dict[str, dict[str, Any]] = {}
    with SessionLocal() as session:
        for row in session.query(DistrictEnv).all():
            district = (row.district or "").strip().lower()
            if not district:
                continue
            latest[district] = {
                "date": row.observed_on.isoformat() if row.observed_on else None,
                "river_level_m": row.river_level_m,
                "population_density": row.population_density,
                "water_quality_index": row.water_quality_index,
                "sanitation_score": row.sanitation_score,
                "rainfall_mm": row.rainfall_mm,
                "flood_depth_cm": row.flood_depth_cm,
            }
    _district_cache["all"] = (now, latest)
    return latest


def _with_district_conditions(location: str, weather_data: dict) -> dict:
    """Merge the latest per-district conditions from the DB into the
    weather response, transparently following district-name aliases."""
    conditions = _latest_district_conditions().get(normalize_district_for_lookup(location))
    if conditions:
        for k, v in conditions.items():
            if k != "date" and v is not None:
                weather_data[k] = v
        weather_data["district_conditions_date"] = conditions["date"]
    return weather_data


async def get_weather_for_location(location: str) -> dict:
    """
    Fetches live weather data from OpenWeatherMap for the given location.
    Implements a 30-minute in-memory cache.
    Returns a normalized dictionary of weather parameters.
    """
    location_key = location.strip().lower()

    cached = _weather_cache.get(location_key)
    if (
        cached
        and (time.time() - cached["timestamp"] < CACHE_TTL_SECONDS)
        and cached["data"].get("river_level_m") is not None
        and cached["data"].get("water_quality_index") is not None
    ):
        return cached["data"]

    if not WEATHER_API_KEY:
        return _with_district_conditions(location, _get_fallback_weather(location))

    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": f"{location},BD",
        "appid": WEATHER_API_KEY,
        "units": "metric",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            if response.status_code != 200:
                return _with_district_conditions(location, _get_fallback_weather(location))
            data = response.json()
            weather_data = {
                "location": data.get("name", location),
                "temperature": data.get("main", {}).get("temp", 25.0),
                "humidity": data.get("main", {}).get("humidity", 70),
                "wind_speed": data.get("wind", {}).get("speed", 0.0),
                "condition": data.get("weather", [{}])[0].get("main", "Clear"),
                "rainfall": 0.0,
                "data_source": "live",
            }
            if "rain" in data:
                weather_data["rainfall"] = data["rain"].get("1h", data["rain"].get("3h", 0.0))

            weather_data = _with_district_conditions(location, weather_data)
            _weather_cache[location_key] = {"data": weather_data, "timestamp": time.time()}
            return weather_data

    except httpx.RequestError:
        return _with_district_conditions(location, _get_fallback_weather(location))


def _get_fallback_weather(location: str) -> dict:
    """Provides safe, plausible default values if the Weather API is unavailable."""
    return {
        "location": location,
        "temperature": 25.0,
        "humidity": 70,
        "wind_speed": 5.0,
        "condition": "Unknown",
        "rainfall": 0.0,
        "data_source": "fallback",
    }