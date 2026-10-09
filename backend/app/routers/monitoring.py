"""Prediction monitoring and a lightweight probability drift signal."""
from collections import Counter
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth_deps import require_roles
from app.auth_models import UserRole
from app.database import get_db
from app.prediction_models import PredictionHistory

router = APIRouter(prefix="/monitoring", tags=["Model Monitoring"])
OPERATIONAL_ROLES = (UserRole.health_worker, UserRole.hospital, UserRole.ngo, UserRole.government, UserRole.admin)


def _psi(old: list[float], new: list[float]) -> float | None:
    if len(old) < 5 or len(new) < 5:
        return None
    bins = [0.0, 0.2, 0.4, 0.6, 0.8, 1.00001]
    def distribution(values):
        counts = [0] * 5
        for value in values:
            index = next((i for i in range(5) if bins[i] <= value < bins[i + 1]), 4)
            counts[index] += 1
        total = len(values)
        return [(count + 0.5) / (total + 2.5) for count in counts]
    old_dist, new_dist = distribution(old), distribution(new)
    return round(sum((new_dist[i] - old_dist[i]) * __import__("math").log(new_dist[i] / old_dist[i]) for i in range(5)), 4)


@router.get("/summary", dependencies=[Depends(require_roles(*OPERATIONAL_ROLES))])
def monitoring_summary(db: Session = Depends(get_db)):
    rows = db.query(PredictionHistory).order_by(PredictionHistory.created_at.asc()).limit(1000).all()
    probabilities = [float(row.probability) for row in rows if row.probability is not None and 0 <= row.probability <= 1]
    midpoint = len(probabilities) // 2
    by_model = Counter(row.model_name for row in rows)
    return {
        "prediction_count": len(rows),
        "models": dict(by_model),
        "average_probability": round(sum(probabilities) / len(probabilities), 4) if probabilities else None,
        "probability_psi": _psi(probabilities[:midpoint], probabilities[midpoint:]) if midpoint else None,
        "drift_status": "insufficient_data" if len(probabilities) < 10 else "monitor",
        "note": "PSI is a screening signal, not a model-quality verdict; investigate data and labels before retraining.",
    }
