"""
/predict/forecast -- Model 3 (Time Series Forecasting, LSTM)

Mirrors `forecast_district()` from Model3_TimeSeries_LSTM.ipynb.

Important design note: the notebook's scalers were fit per-district on
a *stored* weekly history dataframe that lives only in the training
notebook, not in this backend. Rather than silently re-deriving that
history (which this API has no access to), this endpoint requires the
caller to supply the last 8 weeks of observations directly. In the
full product, those 8 weeks would come from the predictions_history
table in the database once real weekly data is being logged -- for now,
the frontend/dashboard is responsible for supplying them.
"""
import numpy as np
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.models_loader import models
from app.schemas import ForecastRequest, ForecastResponse
from app.auth_deps import require_any_authenticated_user
from app.auth_deps import get_current_user
from app.auth_models import User
from app.database import get_db
from app.services.prediction_history import record_prediction

router = APIRouter(
    prefix="/predict",
    tags=["Time Series Forecasting (Model 3)"],
    dependencies=[Depends(require_any_authenticated_user)],
)


@router.post("/forecast", response_model=ForecastResponse)
def forecast(payload: ForecastRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if models.timeseries_model is None:
        raise HTTPException(
            status_code=503,
            detail="LSTM forecast model is unavailable (tensorflow not installed on this server).",
        )
    if payload.district not in models.timeseries_scalers:
        raise HTTPException(
            status_code=404,
            detail=f"No trained scaler for district '{payload.district}'. "
                   f"This district may not have had enough historical weeks during training.",
        )

    scaler = models.timeseries_scalers[payload.district]
    feature_cols = models.timeseries_feature_cols  # e.g. ['weekly_cases','rainfall_mm','temperature_c','flood_depth_cm','sanitation_score']

    window = np.array([
        [getattr(week, col) for col in feature_cols]
        for week in payload.recent_weeks
    ])

    scaled_window = scaler.transform(window)
    scaled_window = scaled_window.reshape(1, models.timeseries_lookback, len(feature_cols))

    pred_7, pred_14 = models.timeseries_model.predict(scaled_window, verbose=0)

    def inverse_cases(scaled_val: float) -> float:
        dummy = np.zeros((1, len(feature_cols)))
        dummy[0, 0] = scaled_val  # weekly_cases is column 0
        return float(scaler.inverse_transform(dummy)[0, 0])

    result = ForecastResponse(
        district=payload.district,
        forecast_next_7_days_cases=round(inverse_cases(pred_7[0][0]), 1),
        forecast_next_14_days_cases=round(inverse_cases(pred_14[0][0]), 1),
    )
    record_prediction(db, user, "forecast", payload, result, payload.district)
    return result
