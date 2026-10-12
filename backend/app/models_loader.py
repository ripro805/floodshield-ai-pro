"""
Loads every trained model artifact exactly once, at application startup,
and exposes them through a single `models` object that routers import.

Why this pattern: loading a joblib/.keras file takes real time (and, for
the LSTM/U-Net, real memory). Doing it once at startup -- instead of on
every request -- is what makes the API fast enough to actually use.
"""
import os
import logging
import joblib
try:
    from tensorflow.keras.models import load_model as _tf_load_model
    _TF_AVAILABLE = True
except ModuleNotFoundError:
    _tf_load_model = None  # type: ignore[assignment]
    _TF_AVAILABLE = False
    import warnings
    warnings.warn(
        "tensorflow is not installed — Model 3 (LSTM forecast) and Model 4B (U-Net) "
        "will be unavailable. All other endpoints are fully functional.",
        RuntimeWarning,
        stacklevel=1,
    )

from app.config import MODELS_DIR

logger = logging.getLogger(__name__)


def _load_keras(path: str, **kw):
    """Load a Keras model, raising a clear 503 if TF is missing."""
    if not _TF_AVAILABLE:
        return None
    return _tf_load_model(path, **kw)


def _hf_download(filename: str) -> str | None:
    """Download a file from the project's Hugging Face model repo.

    Returns the local cached path on success, or None if unavailable.
    """
    try:
        from huggingface_hub import hf_hub_download
        from app.config import HF_MODEL_REPO_ID, HF_TOKEN
        token = HF_TOKEN or None
        path = hf_hub_download(
            repo_id=HF_MODEL_REPO_ID,
            filename=filename,
            token=token,
        )
        return path
    except Exception as exc:
        logger.warning("Could not download %s from Hugging Face: %s", filename, exc)
        return None


class ModelRegistry:
    """A simple container so routers can do `from app.models_loader import models`
    and then `models.flood_model.predict(...)` etc., without re-loading anything."""

    def __init__(self):
        self.loaded = False

        # Model 1 -- Flood Prediction (binary: 0 = No Flood, 1 = Flood)
        self.flood_model = None
        self.flood_features = None

        # Model 2 -- Disease Outbreak Prediction (3-class: Medium/High/Critical)
        self.outbreak_model = None
        self.outbreak_label_encoder = None
        self.outbreak_features = None

        # Model 2B -- Disease Breakdown (6 per-disease XGBoost regressors)
        self.disease_breakdown_models = None   # dict[str, XGBRegressor]
        self.disease_breakdown_features = None  # list[str]
        self.disease_breakdown_targets = None   # list[str]

        # Model 3 -- Time Series Forecasting (LSTM, 7-day + 14-day)
        self.timeseries_model = None
        self.timeseries_scalers = None
        self.timeseries_feature_cols = None
        self.timeseries_lookback = None

        # Model 4B -- Satellite Flood Segmentation (U-Net)
        self.unet_model = None

    def _get_path(self, filename: str) -> str:
        local_path = os.path.join(MODELS_DIR, filename)
        if os.path.exists(local_path):
            return local_path
        hf_path = _hf_download(filename)
        if hf_path:
            return hf_path
        raise FileNotFoundError(f"Model file {filename} not found locally or on HuggingFace")

    def load_all(self):
        # Model 1
        try:
            self.flood_model = joblib.load(self._get_path("flood_prediction_model.pkl"))
            self.flood_features = joblib.load(self._get_path("flood_model_features.pkl"))
        except Exception as e:
            logger.error(f"Failed to load Model 1: {e}")

        # Model 2
        try:
            self.outbreak_model = joblib.load(self._get_path("disease_outbreak_model.pkl"))
            self.outbreak_label_encoder = joblib.load(self._get_path("outbreak_risk_label_encoder.pkl"))
            self.outbreak_features = joblib.load(self._get_path("outbreak_model_features.pkl"))
        except Exception as e:
            logger.error(f"Failed to load Model 2: {e}")

        # Model 2B -- Disease Breakdown (downloaded from Hugging Face)
        try:
            self._load_disease_breakdown()
        except Exception as e:
            logger.error(f"Failed to load Model 2B: {e}")

        # Model 3
        try:
            self.timeseries_model = _load_keras(self._get_path("timeseries_lstm_model.keras"), compile=False)
            self.timeseries_scalers = joblib.load(self._get_path("timeseries_scalers.pkl"))
            self.timeseries_feature_cols = joblib.load(self._get_path("timeseries_feature_cols.pkl"))
            self.timeseries_lookback = joblib.load(self._get_path("timeseries_lookback.pkl"))
        except Exception as e:
            logger.error(f"Failed to load Model 3: {e}")

        # Model 6 (hospital-stock aggregates) is now sourced from the
        # `district_hospital_aggregates` DB table; no artifact to load.

        self.loaded = True

    def load_unet(self):
        """Lazily load the heavy U-Net model only when requested."""
        if self.unet_model is not None:
            return
        from app.unet_service import get_unet_bundle
        bundle = get_unet_bundle()
        self.unet_model = bundle["model"]

    # ------------------------------------------------------------------
    def _load_disease_breakdown(self):
        """Load Model 2B artifacts.

        Strategy: try local files first (fastest), fall back to Hugging Face
        download.  If neither is available, log a warning and leave the
        attributes as None — the router will return a clean 503.
        """
        p = lambda name: os.path.join(MODELS_DIR, name)

        files = {
            "models":   "disease_breakdown_models.pkl",
            "features": "disease_breakdown_features.pkl",
            "targets":  "disease_breakdown_target_names.pkl",
        }

        paths: dict[str, str | None] = {}
        for key, filename in files.items():
            local = p(filename)
            if os.path.exists(local):
                paths[key] = local
            else:
                paths[key] = _hf_download(filename)

        if any(v is None for v in paths.values()):
            missing = [k for k, v in paths.items() if v is None]
            logger.warning(
                "Model 2B (disease breakdown) is unavailable — missing: %s. "
                "The /predict/disease-breakdown endpoint will return 503.",
                ", ".join(missing),
            )
            return

        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.disease_breakdown_models  = joblib.load(paths["models"])
            self.disease_breakdown_features = joblib.load(paths["features"])
            self.disease_breakdown_targets  = joblib.load(paths["targets"])

        logger.info(
            "Model 2B loaded: %d disease regressors (%s)",
            len(self.disease_breakdown_models),
            ", ".join(self.disease_breakdown_targets),
        )


# a single shared instance every router imports
models = ModelRegistry()

