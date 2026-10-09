"""
/predict/risk -- Model 5 (Composite District Risk Score)
/predict/risk/all-districts -- composite score for every registered district

Composite = 0.6 * outbreak_score + 0.4 * flood_score, rule-based (not ML)
so the alert is explainable to government/hospital stakeholders.
"""
import asyncio
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import OUTBREAK_WEIGHT, FLOOD_WEIGHT, OUTBREAK_SCORE_MAP, RISK_LEVEL_THRESHOLDS
from app.models_loader import models
from app.routers.disease import _build_feature_row
from app.schemas import RiskScoreRequest, RiskScoreResponse, AllDistrictsRiskResponse, DistrictRiskItem
from app.auth_deps import require_any_authenticated_user, get_current_user
from app.auth_models import User
from app.database import get_db
from app.reference_models import DistrictHospitalAggregate
from app.services.prediction_history import record_prediction

router = APIRouter(
    prefix="/predict",
    tags=["Composite Risk Score (Model 5)"],
    dependencies=[Depends(require_any_authenticated_user)],
)

FLOOD_SEVERITY_LABELS = ["None", "Minor", "Moderate", "Severe"]

# Resource strain thresholds for the /risk/all-districts endpoint.  Mirrors
# the original Model 6 pickle values so the API response is stable.
_RESOURCE_THRESHOLDS = {"ors": 1000, "iv": 500}

# Districts historically hit hardest by monsoon floods in Bangladesh.
_FLOOD_PRONE_DISTRICTS = {
    "feni", "sunamganj", "sylhet", "kurigram", "netrokona",
    "chattogram", "cox's bazar", "sirajganj", "gaibandha", "jamalpur",
}


def flood_severity_score(depth_cm: float) -> int:
    if depth_cm < 10:
        return 0
    elif depth_cm < 40:
        return 1
    elif depth_cm < 80:
        return 2
    return 3


def compute_composite_level(composite: float) -> str:
    for threshold, label in RISK_LEVEL_THRESHOLDS:
        if composite < threshold:
            return label
    return "Critical"


async def compute_risk_score(payload: RiskScoreRequest) -> RiskScoreResponse:
    """Shared logic -- also called directly by the /recommend combined endpoint."""
    input_df = await _build_feature_row(payload)
    probs = (await asyncio.to_thread(models.outbreak_model.predict_proba, input_df))[0]
    outbreak_class = models.outbreak_label_encoder.classes_[probs.argmax()]
    outbreak_score = OUTBREAK_SCORE_MAP.get(outbreak_class, 1)

    flood_score = flood_severity_score(payload.flood_depth_cm)
    composite = OUTBREAK_WEIGHT * outbreak_score + FLOOD_WEIGHT * flood_score

    return RiskScoreResponse(
        predicted_outbreak_risk=outbreak_class,
        flood_severity=FLOOD_SEVERITY_LABELS[flood_score],
        composite_score=round(composite, 2),
        final_risk_level=compute_composite_level(composite),
    )


@router.post("/risk", response_model=RiskScoreResponse)
async def predict_risk(payload: RiskScoreRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    result = await compute_risk_score(payload)
    record_prediction(db, user, "risk", payload, result, payload.location, result.final_risk_level, result.composite_score)
    return result


@router.get("/risk/all-districts", response_model=AllDistrictsRiskResponse)
def get_all_districts_risk(db: Session = Depends(get_db)) -> AllDistrictsRiskResponse:
    """Composite risk score for every district with hospital data in the DB."""
    rows = db.query(DistrictHospitalAggregate).all()
    items: list[DistrictRiskItem] = []
    for row in rows:
        d_name = row.district
        occ = float(row.occupancy_percent or 0.0)
        ors_low = int(row.ors_stock or 0) < _RESOURCE_THRESHOLDS["ors"]
        iv_low = int(row.iv_saline_stock or 0) < _RESOURCE_THRESHOLDS["iv"]
        is_strained = occ > 80.0 or ors_low or iv_low
        is_flood_prone = d_name.strip().lower() in _FLOOD_PRONE_DISTRICTS

        if is_flood_prone and is_strained:
            risk_level, composite, severity, outbreak = "Critical", 2.85, "Severe", "Critical"
        elif is_flood_prone or occ > 75.0:
            risk_level, composite, severity, outbreak = "High", 2.10, "Moderate", "High"
        elif occ > 50.0:
            risk_level, composite, severity, outbreak = "Medium", 1.35, "Minor", "Medium"
        else:
            risk_level, composite, severity, outbreak = "Low", 0.60, "None", "Low"

        items.append(DistrictRiskItem(
            district=d_name,
            risk_level=risk_level,
            composite_score=composite,
            flood_severity=severity,
            outbreak_risk=outbreak,
        ))

    return AllDistrictsRiskResponse(districts=items)