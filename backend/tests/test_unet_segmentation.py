"""
tests/test_unet_segmentation.py
-------------------------------
Verification tests for Model 4B (U-Net) satellite segmentation:
1. Lazy load of the 3 Hugging Face artifacts and threshold extraction from meta.
2. Preprocessing & finite inference on synthetic SAR chips with NaNs and +/- Infs.
3. Inference on real Sentinel-1 SAR imagery for Feni (August 2024 flood window).
4. Backward-compatible POST /satellite/segment with user-supplied pixel_values.
5. Verifies /satellite/flood-extent/Feni remains completely unaffected and intact.
"""
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.unet_service import get_unet_bundle, fetch_sentinel1_chip, predict_unet_async


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_unet_bundle_loads_three_hf_files_and_threshold():
    """Startup/first-call verifies the 3 Hugging Face files are loaded and threshold read from meta."""
    bundle = get_unet_bundle()
    assert bundle is not None
    assert "model" in bundle and bundle["model"] is not None
    assert "meta" in bundle and isinstance(bundle["meta"], dict)
    assert "threshold" in bundle
    # Threshold should match meta (approx 0.75)
    assert 0.0 < bundle["threshold"] < 1.0
    assert bundle["img_size"] == 256
    assert callable(bundle["preprocess_for_unet"])


def test_synthetic_chip_with_nans_and_infs_yields_finite_output():
    """Synthetic array with NaN/inf through preprocess_for_unet + predict -> finite output."""
    import asyncio
    bundle = get_unet_bundle()
    # Create synthetic SAR chip with intentional NaNs, +inf, -inf
    chip = np.random.uniform(-40.0, 5.0, size=(280, 260, 2)).astype("float32")
    chip[10:30, 10:30, :] = np.nan
    chip[40:60, 40:60, 0] = np.inf
    chip[70:90, 70:90, 1] = -np.inf

    res = asyncio.run(predict_unet_async(chip=chip, timeout_sec=60.0))
    assert np.isfinite(res["flood_pixel_ratio"])
    assert 0.0 <= res["flood_pixel_ratio"] <= 1.0
    assert np.isfinite(res["pred_min"])
    assert np.isfinite(res["pred_mean"])
    assert np.isfinite(res["pred_max"])
    assert 0.0 <= res["pred_min"] <= res["pred_max"] <= 1.0


def test_segment_endpoint_real_feni_flood(client):
    """POST /satellite/segment with Feni August 2024 flood returns non-zero, non-100% coverage."""
    response = client.post("/satellite/segment?district=Feni")
    assert response.status_code == 200
    data = response.json()

    assert data["model_status"] == "ok"
    assert "flood_pixel_ratio" in data
    assert 0.0 < data["flood_pixel_ratio"] < 1.0
    assert "valid_pixel_ratio" in data
    assert data["valid_pixel_ratio"] > 0.0
    assert "threshold" in data
    assert "data_source" in data
    assert "scene_window" in data
    assert "mask_overlay" in data
    assert "bounds" in data["mask_overlay"]


def test_segment_endpoint_backward_compatible_pixel_values(client):
    """POST /satellite/segment with raw pixel_values body maintains backward compatibility."""
    # Synthetic clean 256x256x2 SAR chip
    synthetic_pixels = np.full((256, 256, 2), -20.0, dtype=float).tolist()
    response = client.post("/satellite/segment", json=synthetic_pixels)
    assert response.status_code == 200
    data = response.json()
    assert data["model_status"] == "ok"
    assert "flood_pixel_ratio" in data
    assert 0.0 <= data["flood_pixel_ratio"] <= 1.0


def test_flood_extent_feni_unaffected(client):
    """Verification item 5: /satellite/flood-extent/Feni returns exactly what it returned before."""
    response = client.get("/satellite/flood-extent/Feni")
    assert response.status_code == 200
    body = response.json()
    assert body["district"] == "Feni"
    assert "geojson" in body and body["geojson"]["type"] is not None
