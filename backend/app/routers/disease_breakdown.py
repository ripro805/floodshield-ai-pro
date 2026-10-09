"""
/predict/disease-breakdown -- Model 2B (Per-Disease Case Prediction)

Uses 6 individual XGBoost regressors (one per disease) downloaded from
Hugging Face to predict expected case counts for:
    Cholera, Diarrhea, Typhoid, Dengue, Hepatitis A, Skin Disease.

Accepts the same input features as /predict/disease (Model 2), since both
models were trained on the same underlying dataset — just with different
target columns.

The feature row is built identically to disease.py's _build_feature_row(),
reusing it directly to avoid drift between the two endpoints.
"""
import asyncio
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

from app.models_loader import models
from app.schemas import DiseaseBreakdownRequest, DiseaseBreakdownResponse
from app.auth_deps import require_any_authenticated_user
from app.routers.disease import _build_feature_row

router = APIRouter(
    prefix="/predict",
    tags=["Disease Breakdown (Model 2B)"],
)


def _predict_all_diseases(input_df: pd.DataFrame) -> dict[str, float]:
    """Run each per-disease regressor and return {disease: predicted_cases}."""
    results: dict[str, float] = {}
    for disease_col, regressor in models.disease_breakdown_models.items():
        # XGBoost .predict() uses the model's own feature order; we reindex
        # to match disease_breakdown_features exactly.
        df = input_df.reindex(columns=models.disease_breakdown_features, fill_value=0)
        pred = float(regressor.predict(df)[0])
        # Clamp negative predictions to 0 — case counts can't be negative
        results[disease_col] = round(max(pred, 0.0), 2)
    return results


def _clean_disease_name(col_name: str) -> str:
    """Convert 'cholera_cases' → 'Cholera', 'skin_disease_cases' → 'Skin Disease'."""
    return col_name.replace("_cases", "").replace("_", " ").title()


@router.post("/disease-breakdown", response_model=DiseaseBreakdownResponse)
async def predict_disease_breakdown(payload: DiseaseBreakdownRequest):
    # Guard: Model 2B not loaded
    if models.disease_breakdown_models is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Disease breakdown models are not loaded. "
                "Check that the Hugging Face artifacts are accessible."
            ),
        )

    # Build the feature row using the same logic as /predict/disease
    input_df = await _build_feature_row(payload)

    # Run all 6 regressors in a thread pool (CPU-bound XGBoost inference)
    raw_results = await asyncio.to_thread(_predict_all_diseases, input_df)

    # Build a human-friendly dict with cleaned disease names
    breakdown = {_clean_disease_name(k): v for k, v in raw_results.items()}
    total = round(sum(breakdown.values()), 2)
    dominant = max(breakdown, key=breakdown.get)  # type: ignore[arg-type]

    return DiseaseBreakdownResponse(
        disease_breakdown=breakdown,
        dominant_disease=dominant,
        total_predicted_cases=total,
    )
