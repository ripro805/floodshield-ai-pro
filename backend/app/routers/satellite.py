"""
/satellite/flood-extent -- Model 4A (Google Earth Engine exports) - DB backed
/satellite/segment       -- Model 4B (U-Net inference on a SAR chip)
/satellite/ingest        -- Ingest pipeline used by the dashboard's "Run U-Net"
                            button.

Model 4A's GeoJSON exports are stored in the `satellite_extents` table (one
row per (district, event_label)).  The registry no longer lives in code -- add
a new export by inserting a row, and every deploy instantly sees it.
"""
import asyncio
import hashlib
import os
import json
import logging
from typing import List, Optional, Union, Dict, Any
import numpy as np

from fastapi import APIRouter, HTTPException, Query, Body, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models_loader import models
from app.reference_models import SatelliteExtent
from app.schemas import FloodExtentResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/satellite", tags=["Satellite Flood Detection (Model 4)"])


def _normalize_district(value: str) -> str:
    return (value or "").strip().casefold()


@router.get("/flood-extent", tags=["Satellite Flood Detection (Model 4)"])
def list_available_districts(db: Session = Depends(get_db)):
    """Lets the frontend discover which districts currently have a satellite export."""
    rows = db.query(SatelliteExtent).all()
    return {"available_districts": sorted({row.district for row in rows})}


@router.get("/flood-extent/{district}", response_model=FloodExtentResponse)
def get_flood_extent(district: str, db: Session = Depends(get_db)):
    from app.services.district_centroids import _LEGACY_TO_CANONICAL
    target = _normalize_district(district)
    # Resolve legacy spellings (Barisal -> Barishal) before lookup so
    # the modern and legacy spellings both find the same row.
    target = _LEGACY_TO_CANONICAL.get(target, district).casefold()
    # Also try the legacy spelling of target if applicable.
    legacy_aliases = {k for k, v in _LEGACY_TO_CANONICAL.items() if v.casefold() == target}
    candidates = {target, *legacy_aliases}
    row = next(
        (
            r for r in db.query(SatelliteExtent).all()
            if _normalize_district(r.district) in candidates
        ),
        None,
    )
    if row is None:
        available = sorted({r.district for r in db.query(SatelliteExtent).all()})
        raise HTTPException(
            status_code=404,
            detail=f"No satellite flood-extent export registered for '{district}'. "
                   f"Available: {available}",
        )

    return FloodExtentResponse(
        district=row.district,
        event_label=row.event_label,
        geojson=row.geojson,
    )


def _fetch_sar_chip(district: str, size: int = 256) -> dict:
    """Fetch a real Sentinel-1 SAR chip for a district from Earth Engine."""
    from app.unet_service import fetch_sentinel1_chip, get_unet_bundle
    try:
        fetch_res = fetch_sentinel1_chip(district)
        bundle = get_unet_bundle()
        prep = bundle["preprocess_for_unet"](fetch_res["raw_chip"], img_size=size)
        return {
            "pixel_values": prep.tolist(),
            "source": "earth-engine",
        }
    except Exception as exc:
        logger.error("Failed to fetch real SAR chip from Earth Engine for %s: %s", district, exc)
        raise HTTPException(
            status_code=503,
            detail=f"Failed to fetch Sentinel-1 SAR imagery from Earth Engine for '{district}': {exc}",
        )


@router.get("/ingest")
def ingest_district(district: str = Query(..., min_length=1)):
    """Produce a preprocessed 256x256x2 SAR chip for the requested district from Earth Engine."""
    result = _fetch_sar_chip(district)
    return {
        "district": district.strip(),
        "shape": [256, 256, 2],
        "source": result["source"],
        "pixel_values": result["pixel_values"],
    }


@router.post("/segment")
async def segment_sar_image(
    district: Optional[str] = Query(None, description="District name for real Sentinel-1 acquisition"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    pixel_values: Optional[Union[List[List[List[float]]], Dict[str, Any]]] = Body(None),
):
    """Runs the retrained U-Net (Model 4B) on real Sentinel-1 SAR data or a provided chip."""
    from app.unet_service import get_unet_bundle, fetch_sentinel1_chip, predict_unet_async

    # 1. Ensure U-Net bundle is ready (or 503)
    try:
        await asyncio.to_thread(get_unet_bundle)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Failed to load U-Net model from Hugging Face: {str(e)}")

    # 2. Extract district name if passed in query or body dict
    target_district = district
    if not target_district and isinstance(pixel_values, dict):
        target_district = pixel_values.get("district")
        if not start_date:
            start_date = pixel_values.get("start_date")
        if not end_date:
            end_date = pixel_values.get("end_date")

    # Case A: Real Sentinel-1 acquisition for district
    if target_district:
        date_window = (start_date, end_date) if (start_date and end_date) else None
        try:
            fetch_res = await asyncio.to_thread(fetch_sentinel1_chip, target_district, date_window)
        except ValueError as ve:
            raise HTTPException(status_code=404, detail=str(ve))
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Failed to acquire Sentinel-1 SAR scene: {str(e)}")

        try:
            pred_res = await predict_unet_async(
                chip=fetch_res["raw_chip"],
                valid_mask=fetch_res["valid_mask"],
                timeout_sec=120.0,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"U-Net inference failed: {str(e)}")

        flood_ratio = round(pred_res["flood_pixel_ratio"], 4)
        return {
            "flood_pixel_ratio": flood_ratio,
            "note": "Fraction of valid pixels classified as flood water by the retrained U-Net on real Sentinel-1 SAR imagery.",
            "model_status": "ok",
            "threshold": pred_res["threshold"],
            "valid_pixel_ratio": round(fetch_res["valid_pixel_ratio"], 4),
            "scene_window": fetch_res["scene_window"],
            "data_source": fetch_res["data_source"],
            "mask_overlay": {
                "bounds": fetch_res["bounds"],
                "threshold": pred_res["threshold"],
                "flood_pixel_ratio": flood_ratio,
            },
        }

    # Case B: Provided pixel_values array
    raw_pixels = pixel_values
    if isinstance(pixel_values, dict) and "pixel_values" in pixel_values:
        raw_pixels = pixel_values["pixel_values"]

    if raw_pixels is None:
        raise HTTPException(
            status_code=422,
            detail="Either 'district' parameter or 'pixel_values' array must be provided.",
        )

    try:
        arr = np.array(raw_pixels, dtype="float32")
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid pixel_values array: {e}")

    if arr.ndim != 3 or arr.shape[-1] != 2:
        raise HTTPException(
            status_code=422,
            detail=f"Expected shape (H, W, 2) or (256, 256, 2), got {arr.shape}.",
        )

    try:
        pred_res = await predict_unet_async(chip=arr, timeout_sec=120.0)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"U-Net inference failed: {str(e)}")

    flood_ratio = round(pred_res["flood_pixel_ratio"], 4)
    return {
        "flood_pixel_ratio": flood_ratio,
        "note": "Fraction of pixels classified as flood water by the retrained U-Net.",
        "model_status": "ok",
        "threshold": pred_res["threshold"],
        "valid_pixel_ratio": round(float(np.mean(np.isfinite(arr))), 4),
        "data_source": "Supplied SAR chip",
        "mask_overlay": {
            "threshold": pred_res["threshold"],
            "flood_pixel_ratio": flood_ratio,
        },
    }