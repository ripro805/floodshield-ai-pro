"""
/predict/flood -- Model 1 (Flood Prediction)

This mirrors the `predict_flood()` function built and validated in
Model1_Flood_Prediction.ipynb: a binary classifier (0 = No Flood,
1 = Flood) trained on leakage-free features (flood_depth_cm was
deliberately excluded -- see the notebook's data-leakage note).

The "likely_severity_if_flood" field is a simple rainfall-based heuristic,
NOT a model prediction -- it exists only to give the frontend something
more descriptive than a bare probability when flood_probability is high.
"""
import asyncio
import pandas as pd
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.models_loader import models
from app.schemas import FloodPredictionRequest, FloodPredictionResponse
from app.auth_deps import require_any_authenticated_user
from app.services.explainability import explain_prediction
from app.services.prediction_history import record_prediction
from app.database import get_db
from app.auth_deps import get_current_user
from app.auth_models import User

router = APIRouter(
    prefix="/predict",
    tags=["Flood Prediction (Model 1)"],
    dependencies=[Depends(require_any_authenticated_user)],
)


def _severity_hint(rainfall_mm: float) -> str:
    if rainfall_mm < 100:
        return "Minor"
    elif rainfall_mm < 300:
        return "Moderate"
    return "Severe"


@router.post("/flood", response_model=FloodPredictionResponse)
async def predict_flood(payload: FloodPredictionRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rainfall = payload.rainfall_mm
    temp = payload.temperature_c
    humidity = payload.humidity_percent

    if (rainfall is None or temp is None or humidity is None) and payload.location:
        from app.services.weather_service import get_weather_for_location
        weather_data = await get_weather_for_location(payload.location)
        if rainfall is None:
            rainfall = weather_data.get("rainfall", 0.0)
        if temp is None:
            temp = weather_data.get("temperature", 25.0)
        if humidity is None:
            humidity = weather_data.get("humidity", 70.0)

    # Fallbacks if still None (e.g., no location provided)
    if rainfall is None: rainfall = 0.0
    if temp is None: temp = 25.0
    if humidity is None: humidity = 70.0

    input_dict = {
        "rainfall_mm": rainfall,
        "river_level_m": payload.river_level_m,
        "humidity_percent": humidity,
        "temperature_c": temp,
        "elevation_m": payload.elevation_m if payload.elevation_m is not None else 20.0,
        "water_quality_index": payload.water_quality_index if payload.water_quality_index is not None else 70.0,
        "population_density": payload.population_density if payload.population_density is not None else 1500.0,
    }

    # one-hot encode season to match the columns the model was trained on
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

    result = FloodPredictionResponse(
        flood_probability=round(flood_probability, 4),
        flood_risk_level=risk_level,
        likely_severity_if_flood=_severity_hint(rainfall),
        feature_importance=await asyncio.to_thread(explain_prediction, models.flood_model, input_df),
    )
    record_prediction(db, user, "flood", payload, result, payload.location, risk_level, flood_probability)
    return result
