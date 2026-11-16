"""
/predict/disease -- Model 2 (Disease Outbreak Prediction)

Mirrors `predict_outbreak()` from Model2_Disease_Prediction.ipynb.
3-class classifier: Medium / High / Critical (the original "Low" class
had only 6 samples in 30,000 rows and was merged into "Medium" during
training -- see the notebook's class-imbalance note).

`future_cases` is intentionally NOT an input here -- that column was
used to build the training label itself, so including it would be
data leakage. Only genuinely-available current/historical values are
accepted (previous_week_cases, previous_two_week_cases, etc.).
"""
import asyncio
import pandas as pd
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.models_loader import models
from app.schemas import DiseasePredictionRequest, DiseasePredictionResponse
from app.auth_deps import require_any_authenticated_user
from app.services.explainability import explain_prediction
from app.services.prediction_history import record_prediction
from app.database import get_db
from app.auth_deps import get_current_user
from app.auth_models import User

router = APIRouter(
    prefix="/predict",
    tags=["Disease Outbreak Prediction (Model 2)"],
    dependencies=[Depends(require_any_authenticated_user)],
)


async def _build_feature_row(payload: DiseasePredictionRequest) -> pd.DataFrame:
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

    pop_density = payload.population_density if payload.population_density is not None else 1200.0
    sanitation = payload.sanitation_score if payload.sanitation_score is not None else 0.5
    water_quality = payload.water_quality_index if payload.water_quality_index is not None else 60.0

    input_dict = {
        "rainfall_mm": rainfall,
        "temperature_c": temp,
        "humidity_percent": humidity,
        "river_level_m": payload.river_level_m,
        "flood_depth_cm": payload.flood_depth_cm,
        "population_density": pop_density,
        "sanitation_score": sanitation,
        "water_quality_index": water_quality,
        "previous_week_cases": payload.previous_week_cases,
        "previous_two_week_cases": payload.previous_two_week_cases,
    }
    season_cols = [c for c in models.outbreak_features if c.startswith("season_")]
    for col in season_cols:
        season_name = col.replace("season_", "")
        input_dict[col] = 1 if season_name == payload.season else 0

    return pd.DataFrame([input_dict])[models.outbreak_features]


@router.post("/disease", response_model=DiseasePredictionResponse)
async def predict_disease(payload: DiseasePredictionRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    input_df = await _build_feature_row(payload)
    # predict_proba is synchronous + CPU-bound (XGBoost/sklearn). Calling it
    # directly on the event loop would freeze every other request for ~30ms
    # each call -- offload to a worker thread so concurrent requests stay
    # responsive. Same fix applied to risk / flood / satellite.
    probs = (await asyncio.to_thread(models.outbreak_model.predict_proba, input_df))[0]
    predicted_class = models.outbreak_label_encoder.classes_[probs.argmax()]
    prob_dict = dict(zip(models.outbreak_label_encoder.classes_, [round(float(p), 4) for p in probs]))

    result = DiseasePredictionResponse(
        predicted_outbreak_risk=predicted_class,
        risk_probability_by_class=prob_dict,
        feature_importance=await asyncio.to_thread(explain_prediction, models.outbreak_model, input_df),
    )
    record_prediction(db, user, "disease", payload, result, payload.location, predicted_class, float(probs.max()))
    return result
