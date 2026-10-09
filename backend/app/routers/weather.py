from fastapi import APIRouter, Query, HTTPException, Depends
from sqlalchemy.orm import Session
from app.services.weather_service import get_weather_for_location
from app.database import get_db
from app.weather_models import WeatherObservation
from app.schemas import WeatherObservationItem

router = APIRouter(
    prefix="/api/weather",
    tags=["Weather API"],
)

@router.get("")
async def get_weather(location: str = Query(..., description="Location name (e.g. Dhaka)")):
    """
    Fetch live weather data for a given location.
    Data is cached for 30 minutes to reduce API calls.
    """
    if not location:
        raise HTTPException(status_code=400, detail="Location parameter is required")

    weather_data = await get_weather_for_location(location)
    return weather_data


@router.get("/history", response_model=list[WeatherObservationItem])
def get_weather_history(
    location: str = Query(...),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(WeatherObservation)
        .filter(WeatherObservation.location == location)
        .order_by(WeatherObservation.observed_at.desc())
        .limit(limit)
        .all()
    )
    return [WeatherObservationItem(
        location=row.location,
        observed_at=row.observed_at.isoformat(),
        temperature=row.temperature,
        humidity=row.humidity,
        rainfall=row.rainfall,
        river_level_m=row.river_level_m,
        water_quality_index=row.water_quality_index,
        data_source=row.data_source,
    ) for row in rows]
