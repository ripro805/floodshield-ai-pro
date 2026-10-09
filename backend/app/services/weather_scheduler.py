"""Periodic weather collection independent of request traffic."""
import asyncio
import logging

from app.config import WEATHER_REFRESH_DISTRICTS, WEATHER_REFRESH_INTERVAL_SECONDS
from app.services.weather_service import get_weather_for_location
from app.database import SessionLocal
from app.weather_models import WeatherObservation

logger = logging.getLogger(__name__)


async def refresh_weather_once() -> None:
    for district in WEATHER_REFRESH_DISTRICTS:
        try:
            weather = await get_weather_for_location(district)
            db = SessionLocal()
            try:
                db.add(WeatherObservation(
                    location=district,
                    temperature=float(weather.get("temperature", 25.0)),
                    humidity=float(weather.get("humidity", 70.0)),
                    rainfall=float(weather.get("rainfall", 0.0)),
                    river_level_m=weather.get("river_level_m"),
                    water_quality_index=weather.get("water_quality_index"),
                    data_source=str(weather.get("data_source", "fallback")),
                ))
                db.commit()
            finally:
                db.close()
        except Exception:
            logger.exception("Scheduled weather refresh failed for %s", district)


async def weather_refresh_loop() -> None:
    """Run until cancelled by the FastAPI lifespan shutdown."""
    while True:
        await refresh_weather_once()
        await asyncio.sleep(WEATHER_REFRESH_INTERVAL_SECONDS)
