"""
/recommend -- Model 6 (Recommendation AI)
/predict/full-assessment -- Model 5 + Model 6 chained together

Reads district hospital stock from the `district_hospital_aggregates` table
(seeded in app.services.seed_reference from data/hospital_resources_csv.xls).
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.auth_deps import require_roles
from app.auth_models import UserRole
from app.database import get_db
from app.reference_models import DistrictHospitalAggregate
from app.routers.risk import compute_risk_score
from app.schemas import (
    RecommendationRequest, RecommendationResponse,
    FullAssessmentRequest, FullAssessmentResponse,
)

router = APIRouter(tags=["Recommendation AI (Model 6)"])

OPERATIONAL_ROLES = (
    UserRole.health_worker, UserRole.hospital, UserRole.ngo,
    UserRole.government, UserRole.admin,
)


DISTRICT_ALIASES = {
    "chittagong": "Chattogram",
    "bogra": "Bogura",
    "comilla": "Cumilla",
    "barisal": "Barishal",
    "jessore": "Jashore",
    "dacca": "Dhaka",
    "coxs bazar": "Cox's Bazar",
    "coxsbazar": "Cox's Bazar",
    "netrakona": "Netrokona",
}


def _recommend_for_district(
    db: Session, district: str, risk_level: str
) -> RecommendationResponse:
    norm_district = DISTRICT_ALIASES.get(district.strip().lower(), district).strip().lower()
    row = (
        db.query(DistrictHospitalAggregate)
        .filter(DistrictHospitalAggregate.district.ilike(norm_district))
        .first()
    )
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"No hospital data found for district '{district}'",
        )

    # Resource thresholds mirrored from the original Model 6 pickle.  Kept
    # here (instead of a separate table) because they are static policy
    # values, not reference data.
    thresholds = {"ors": 1000, "iv": 500, "antibiotics": 800}
    recommendations: list[str] = []

    if risk_level == "Critical":
        recommendations += [
            "Deploy Emergency Medical Team",
            "Prepare Emergency Shelter",
            "Distribute Emergency Kits (household level)",
        ]
        recommendations.append("URGENT: ORS restock needed" if row.ors_stock < thresholds["ors"] else "ORS stock adequate")
        recommendations.append("URGENT: IV Saline restock needed" if row.iv_saline_stock < thresholds["iv"] else "IV Saline stock adequate")
        recommendations.append("URGENT: Antibiotics restock needed" if row.antibiotics_stock < thresholds["antibiotics"] else "Antibiotics stock adequate")

    elif risk_level == "High":
        recommendations.append("Increase ORS supply" if row.ors_stock < thresholds["ors"] else "ORS stock adequate")
        recommendations.append("Increase IV Saline supply" if row.iv_saline_stock < thresholds["iv"] else "IV Saline stock adequate")
        recommendations.append("Alert local health workers for increased monitoring")

    elif risk_level == "Medium":
        recommendations.append("Monitor ORS stock" if row.ors_stock < thresholds["ors"] else "No immediate action needed")
        recommendations.append("Routine health advisory to community")

    else:  # Low
        recommendations.append("Routine monitoring, no special action needed")

    return RecommendationResponse(
        district=row.district,
        risk_level=risk_level,
        hospital_beds_available=int(row.beds),
        occupancy_percent=round(float(row.occupancy_percent), 1),
        recommendations=recommendations,
        ors_stock=int(row.ors_stock),
        iv_saline_stock=int(row.iv_saline_stock),
        antibiotics_stock=int(row.antibiotics_stock),
    )


@router.post("/recommend", response_model=RecommendationResponse,
             dependencies=[Depends(require_roles(*OPERATIONAL_ROLES))])
def recommend(payload: RecommendationRequest, db: Session = Depends(get_db)):
    return _recommend_for_district(db, payload.district, payload.risk_level)


@router.post("/predict/full-assessment", response_model=FullAssessmentResponse,
             dependencies=[Depends(require_roles(*OPERATIONAL_ROLES))])
async def full_assessment(
    payload: FullAssessmentRequest, db: Session = Depends(get_db)
):
    """One call: Model 2 -> Model 5 -> Model 6, chained."""
    risk = await compute_risk_score(payload)
    reco = _recommend_for_district(db, payload.district, risk.final_risk_level)
    return FullAssessmentResponse(
        district=payload.district,
        risk_assessment=risk,
        recommendation=reco,
    )