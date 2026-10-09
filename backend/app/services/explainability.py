"""Small, dependency-free feature-importance explanations for tree models."""
from typing import Any

import pandas as pd


def explain_prediction(model: Any, feature_frame: pd.DataFrame, limit: int = 6) -> list[dict]:
    """Return global model importance plus the value used for this prediction.

    The project models are tree ensembles, so ``feature_importances_`` is a
    stable, auditable explanation available without introducing a second
    unverified explainer runtime. Values are included so the UI can explain
    which observed inputs informed the prediction.
    """
    importances = getattr(model, "feature_importances_", None)
    if importances is None:
        return []

    names = list(feature_frame.columns)
    pairs = sorted(
        zip(names, importances), key=lambda pair: float(pair[1]), reverse=True
    )[:limit]
    values = feature_frame.iloc[0].to_dict()
    return [
        {
            "feature": str(name),
            "importance": round(float(importance), 4),
            "value": round(float(values[name]), 4),
        }
        for name, importance in pairs
    ]
