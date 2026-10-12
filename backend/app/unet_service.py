"""
backend/app/unet_service.py
---------------------------
Model 4B (U-Net) service for Sentinel-1 flood segmentation.

Handles:
1. Thread-safe lazy loading of retrained U-Net model artifacts from Hugging Face
   (flood_segmentation_unet.keras, flood_segmentation_unet_meta.json, unet_preprocessing.py).
2. Dynamic import of preprocess_for_unet from downloaded unet_preprocessing.py.
3. Sentinel-1 SAR chip acquisition from Google Earth Engine (VV + VH in dB, EPSG:32646,
   adaptive scale) for Bangladesh districts with real date windows.
4. Heavy model inference with thread-safe prediction and valid-pixel coverage computation.
"""
import asyncio
import importlib.util
import json
import logging
import os
import threading
from typing import Any, Dict, Optional, Tuple

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Global singleton container and lock
_UNET_LOCK = threading.Lock()
_EE_LOCK = threading.Lock()

_UNET_BUNDLE: Optional[Dict[str, Any]] = None
_EE_INITIALIZED = False


def _get_hf_config() -> Tuple[str, Optional[str], Optional[str]]:
    from app.config import HF_MODEL_REPO_ID, HF_TOKEN
    repo = os.getenv("HF_MODEL_REPO") or os.getenv("HF_MODEL_REPO_ID") or HF_MODEL_REPO_ID or "ripro805/floodshield-ai-models"
    revision = os.getenv("HF_MODEL_REVISION") or None
    token = os.getenv("HF_TOKEN") or HF_TOKEN or None
    return repo, revision, token


def get_unet_bundle() -> Dict[str, Any]:
    """Lazy-load the U-Net model, meta JSON, and preprocessing function once. Thread-safe.

    Raises RuntimeError (mapped to 503 by caller) if download or model loading fails.
    Never falls back to random data, stubs, or old NaN models.
    """
    global _UNET_BUNDLE
    if _UNET_BUNDLE is not None:
        return _UNET_BUNDLE

    with _UNET_LOCK:
        if _UNET_BUNDLE is not None:
            return _UNET_BUNDLE

        repo, revision, token = _get_hf_config()
        from huggingface_hub import hf_hub_download

        try:
            # 1. Download meta JSON
            meta_path = hf_hub_download(
                repo_id=repo,
                filename="flood_segmentation_unet_meta.json",
                revision=revision,
                token=token,
            )
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)

            threshold = float(meta.get("threshold", 0.75))
            img_size = int(meta.get("img_size", 256))

            # 2. Download preprocessing script & load preprocess_for_unet
            prep_path = hf_hub_download(
                repo_id=repo,
                filename="unet_preprocessing.py",
                revision=revision,
                token=token,
            )
            spec = importlib.util.spec_from_file_location("unet_preprocessing", prep_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"Cannot load module spec from {prep_path}")
            prep_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(prep_module)
            preprocess_for_unet = getattr(prep_module, "preprocess_for_unet", None)
            if not callable(preprocess_for_unet):
                raise AttributeError("preprocess_for_unet function missing in unet_preprocessing.py")

            # 3. Download Keras model & load with compile=False
            keras_path = hf_hub_download(
                repo_id=repo,
                filename="flood_segmentation_unet.keras",
                revision=revision,
                token=token,
            )
            from tensorflow.keras.models import load_model
            model = load_model(keras_path, compile=False)

            logger.info(
                "Model 4B (U-Net) loaded from Hugging Face: %s (rev: %s). "
                "Files: [flood_segmentation_unet.keras, flood_segmentation_unet_meta.json, unet_preprocessing.py]. "
                "Threshold: %.4f, Image size: %d",
                repo, revision or "main", threshold, img_size
            )

            _UNET_BUNDLE = {
                "model": model,
                "meta": meta,
                "threshold": threshold,
                "img_size": img_size,
                "preprocess_for_unet": preprocess_for_unet,
                "repo": repo,
            }
            return _UNET_BUNDLE

        except Exception as exc:
            logger.error("Failed to load U-Net model from Hugging Face (%s): %s", repo, exc)
            raise RuntimeError(f"Could not load U-Net model from Hugging Face ({repo}): {exc}") from exc


def init_earth_engine() -> None:
    """Initialize Google Earth Engine once using credentials strictly from environment."""
    global _EE_INITIALIZED
    if _EE_INITIALIZED:
        return

    with _EE_LOCK:
        if _EE_INITIALIZED:
            return

        import ee
        from google.oauth2 import service_account

        try:
            if os.environ.get("GEE_SERVICE_ACCOUNT_JSON"):
                creds_dict = json.loads(os.environ["GEE_SERVICE_ACCOUNT_JSON"])
                credentials = service_account.Credentials.from_service_account_info(
                    creds_dict
                ).with_scopes(["https://www.googleapis.com/auth/earthengine"])
                ee.Initialize(credentials, project=os.environ.get("GEE_PROJECT_ID", "floodshield-505920"))
            else:
                if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
                    default_key = os.path.join(
                        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "ee_service_account.json"
                    )
                    if os.path.exists(default_key):
                        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = default_key
                ee.Initialize(project=os.environ.get("GEE_PROJECT_ID", "floodshield-505920"))

            _EE_INITIALIZED = True
            logger.info("Earth Engine initialized successfully for U-Net SAR chip acquisition.")
        except Exception as exc:
            logger.error("Earth Engine initialization failed: %s", exc)
            raise RuntimeError(f"Earth Engine initialization failed: {exc}") from exc


def fetch_sentinel1_chip(
    district: str,
    date_window: Optional[Tuple[str, str]] = None,
) -> Dict[str, Any]:
    """Fetch a real Sentinel-1 VV+VH (dB) chip through Earth Engine for requested district/date window.

    - Uses EPSG:32646 and adaptive scale [100, 250, 500, 1000].
    - Default window for Feni: August 2024 flood ('2024-08-21' to '2024-08-30').
    - Returns error if no scene exists.
    """
    init_earth_engine()
    import ee
    import geemap
    from app.services.district_centroids import CENTROIDS, _LEGACY_TO_CANONICAL

    d_norm = (district or "").strip()
    canonical_district = _LEGACY_TO_CANONICAL.get(d_norm.casefold(), d_norm)

    if canonical_district.casefold() == "feni":
        aoi = ee.Geometry.Rectangle([91.30, 22.85, 91.55, 23.10])
        bounds = [[22.85, 91.30], [23.10, 91.55]]
        default_start, default_end = "2024-08-21", "2024-08-30"
    else:
        # Resolve centroid
        matched_name = next(
            (k for k in CENTROIDS if k.casefold() == canonical_district.casefold()),
            None
        )
        if matched_name is not None:
            lat, lon = CENTROIDS[matched_name]
            aoi = ee.Geometry.Rectangle([lon - 0.15, lat - 0.15, lon + 0.15, lat + 0.15])
            bounds = [[lat - 0.15, lon - 0.15], [lat + 0.15, lon + 0.15]]
        else:
            # Fallback general box around Dhaka/central Bangladesh
            aoi = ee.Geometry.Rectangle([90.25, 23.65, 90.55, 23.95])
            bounds = [[23.65, 90.25], [23.95, 90.55]]
        default_start, default_end = "2024-08-21", "2024-08-30"

    start_date = date_window[0] if date_window and date_window[0] else default_start
    end_date = date_window[1] if date_window and date_window[1] else default_end

    collection = (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterBounds(aoi)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .select(["VV", "VH"])
    )

    scene_count = collection.size().getInfo()
    if scene_count == 0:
        raise ValueError(
            f"No Sentinel-1 SAR scene found for '{district}' in window {start_date} to {end_date}."
        )

    image = collection.median().clip(aoi)

    arr = None
    chosen_scale = None
    for scale in [100, 250, 500, 1000]:
        try:
            image_rep = image.reproject(crs="EPSG:32646", scale=scale)
            res = geemap.ee_to_numpy(image_rep, region=aoi)
            if res is not None and res.size > 0:
                arr = res
                chosen_scale = scale
                break
        except Exception as exc:
            logger.debug("Scale %d failed for district %s: %s", scale, district, exc)
            continue

    if arr is None or arr.size == 0:
        raise RuntimeError(
            f"Could not extract Sentinel-1 SAR chip from Earth Engine for '{district}'."
        )

    # Valid pixel ratio (finite values in both VV and VH channels)
    valid_mask = np.isfinite(arr[:, :, 0]) & np.isfinite(arr[:, :, 1])
    valid_pixel_ratio = float(np.mean(valid_mask))

    return {
        "raw_chip": arr,
        "valid_mask": valid_mask,
        "valid_pixel_ratio": valid_pixel_ratio,
        "bounds": bounds,
        "scene_window": f"{start_date} to {end_date}",
        "data_source": "Sentinel-1 GRD (IW) via Google Earth Engine",
        "scale": chosen_scale,
    }


async def predict_unet_async(
    chip: np.ndarray,
    valid_mask: Optional[np.ndarray] = None,
    timeout_sec: float = 120.0,
) -> Dict[str, Any]:
    """Run model inference in a threadpool with timeout and compute coverage % over valid pixels."""
    bundle = get_unet_bundle()
    preprocess_fn = bundle["preprocess_for_unet"]
    model = bundle["model"]
    threshold = bundle["threshold"]
    img_size = bundle["img_size"]

    # Preprocess chip (handles NaNs/Infs and resizes to img_size x img_size x 2)
    prep = preprocess_fn(chip, img_size=img_size)

    # Threadpool prediction with timeout
    loop = asyncio.get_running_loop()
    pred = await asyncio.wait_for(
        loop.run_in_executor(None, lambda: model.predict(prep[None, ...], verbose=0)),
        timeout=timeout_sec,
    )

    prob = pred[0, :, :, 0]
    if not np.isfinite(prob).all():
        raise RuntimeError("U-Net model produced non-finite output.")

    mask = prob > threshold

    # Compute coverage over valid pixels if valid_mask available
    if valid_mask is not None and valid_mask.size > 0:
        valid_resized = np.asarray(
            Image.fromarray(valid_mask.astype(np.uint8)).resize((img_size, img_size), Image.NEAREST)
        ) > 0
        if np.any(valid_resized):
            flood_pixel_ratio = float(np.mean(mask[valid_resized]))
        else:
            flood_pixel_ratio = float(np.mean(mask))
    else:
        flood_pixel_ratio = float(np.mean(mask))

    return {
        "flood_pixel_ratio": flood_pixel_ratio,
        "pred_min": float(np.min(prob)),
        "pred_mean": float(np.mean(prob)),
        "pred_max": float(np.max(prob)),
        "threshold": threshold,
        "binary_mask": mask,
    }
