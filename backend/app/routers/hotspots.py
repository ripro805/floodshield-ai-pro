"""
/predict/hotspots -- district-level disease/environment hotspot clustering.

The source is the `district_env` table (seeded from climate_dataset_fixed.xlsx
in app.services.seed_reference).  We standardise the per-district observed
features and cluster them with DBSCAN.  No synthetic case counts are
introduced.
"""
from fastapi import APIRouter, Depends, HTTPException
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler
from sqlalchemy.orm import Session

from app.auth_deps import require_any_authenticated_user
from app.database import get_db
from app.reference_models import DistrictEnv
from app.schemas import HotspotDistrict, HotspotResponse

router = APIRouter(
    prefix="/predict",
    tags=["Disease Hotspot Detection"],
    dependencies=[Depends(require_any_authenticated_user)],
)

_FEATURES = [
    "rainfall_mm", "river_level_m", "flood_depth_cm", "population_density",
    "water_quality_index",
]


@router.get("/hotspots", response_model=HotspotResponse)
def detect_hotspots(db: Session = Depends(get_db)) -> HotspotResponse:
    """Cluster observed district-level environmental disease-risk signals."""
    rows = db.query(DistrictEnv).all()
    if len(rows) < 2:
        raise HTTPException(status_code=503, detail="At least two districts are required for clustering.")

    import pandas as pd
    frame = pd.DataFrame([
        {
            "district": r.district,
            "rainfall_mm": r.rainfall_mm,
            "river_level_m": r.river_level_m,
            "flood_depth_cm": r.flood_depth_cm,
            "population_density": r.population_density,
            "sanitation_score": r.sanitation_score,
            "water_quality_index": r.water_quality_index,
            "contamination_risk_score": 0.0,
        }
        for r in rows
    ])
    for col in _FEATURES:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    # Median-impute remaining NaNs so a single missing feature doesn't drop
    # an entire district from the cluster analysis.
    for col in _FEATURES:
        if frame[col].isna().any():
            frame[col] = frame[col].fillna(frame[col].median())
    if len(frame) < 2:
        raise HTTPException(status_code=503, detail="District env table lacks enough rows for clustering.")

    matrix = StandardScaler().fit_transform(frame[_FEATURES])
    labels = DBSCAN(eps=1.15, min_samples=2).fit_predict(matrix)

    districts = [
        HotspotDistrict(
            district=str(row["district"]),
            cluster_id=int(label),
            is_noise=bool(label == -1),
            signal_score=round(float(row["contamination_risk_score"]), 3),
            flood_depth_cm=round(float(row["flood_depth_cm"]), 2),
            water_quality_index=round(float(row["water_quality_index"]), 2),
        )
        for (_, row), label in zip(frame.iterrows(), labels)
    ]
    cluster_count = len({item.cluster_id for item in districts if not item.is_noise})

    return HotspotResponse(
        algorithm="DBSCAN",
        source="district_env",
        cluster_count=cluster_count,
        districts=districts,
    )