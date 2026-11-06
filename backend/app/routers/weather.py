import logging
from fastapi import APIRouter, Query, HTTPException, Depends
from sqlalchemy.orm import Session
from app.services.weather_service import get_weather_for_location
from app.database import get_db
from app.weather_models import WeatherObservation
from app.schemas import WeatherObservationItem

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/weather",
    tags=["Weather API"],
)

@router.get("")
async def get_weather(
    location: str = Query(..., description="Location name (e.g. Dhaka)"),
    db: Session = Depends(get_db),
):
    """
    Fetch live weather data for a given location.
    Data is cached for 30 minutes to reduce API calls.
    Persists an observation so history is always available for this district.
    """
    if not location:
        raise HTTPException(status_code=400, detail="Location parameter is required")

    loc_clean = location.strip()
    weather_data = await get_weather_for_location(loc_clean)

    # Lazily record observation if not logged in the last 15 minutes
    try:
        norm_name = weather_data.get("location", loc_clean).capitalize()
        obs = WeatherObservation(
            location=norm_name,
            temperature=float(weather_data.get("temperature", 25.0)),
            humidity=float(weather_data.get("humidity", 70.0)),
            rainfall=float(weather_data.get("rainfall", 0.0)),
            river_level_m=weather_data.get("river_level_m"),
            water_quality_index=weather_data.get("water_quality_index"),
            data_source=str(weather_data.get("data_source", "live")),
        )
        db.add(obs)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.debug("Weather observation persistence skipped: %s", e)

    return weather_data


@router.get("/history", response_model=list[WeatherObservationItem])
async def get_weather_history(
    location: str = Query(...),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    Get recorded weather observations for a district.
    Case-insensitive. If no previous telemetry is recorded yet, fetches
    and seeds a live observation so the response is never empty.
    """
    loc_clean = location.strip()
    rows = (
        db.query(WeatherObservation)
        .filter(WeatherObservation.location.ilike(loc_clean))
        .order_by(WeatherObservation.observed_at.desc())
        .limit(limit)
        .all()
    )

    if not rows:
        try:
            weather_data = await get_weather_for_location(loc_clean)
            norm_name = weather_data.get("location", loc_clean).capitalize()
            new_obs = WeatherObservation(
                location=norm_name,
                temperature=float(weather_data.get("temperature", 25.0)),
                humidity=float(weather_data.get("humidity", 70.0)),
                rainfall=float(weather_data.get("rainfall", 0.0)),
                river_level_m=weather_data.get("river_level_m"),
                water_quality_index=weather_data.get("water_quality_index"),
                data_source=str(weather_data.get("data_source", "live")),
            )
            db.add(new_obs)
            db.commit()
            db.refresh(new_obs)
            rows = [new_obs]
        except Exception as exc:
            db.rollback()
            logger.warning("Auto-recording initial weather observation failed for %s: %s", loc_clean, exc)

    return [
        WeatherObservationItem(
            location=row.location,
            observed_at=row.observed_at.isoformat(),
            temperature=row.temperature,
            humidity=row.humidity,
            rainfall=row.rainfall,
            river_level_m=row.river_level_m,
            water_quality_index=row.water_quality_index,
            data_source=row.data_source,
        )
        for row in rows
    ]
