"""
Pydantic models define exactly what each endpoint expects as input and
returns as output. FastAPI uses these to validate requests automatically
(bad input -> a clear 422 error, not a silent crash) and to generate the
interactive /docs page.
"""
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


SeasonType = str  # "Monsoon" | "Post-Monsoon" | "Winter" | "Summer"


# ---------- Model 1: Flood Prediction ----------

class FloodPredictionRequest(BaseModel):
    # Optional because the dashboard typically only knows `location` + `river_level_m`.
    # When omitted, flood.py fills them in from the live weather service (or fallback).
    location: Optional[str] = Field(None, description="District name; used to auto-fill weather when sensor fields are omitted")
    rainfall_mm: Optional[float] = Field(None, ge=0, description="Recent/forecast rainfall in mm; auto-filled from weather if omitted")
    river_level_m: float = Field(..., ge=0, description="Current river water level in meters")
    humidity_percent: Optional[float] = Field(None, ge=0, le=100, description="Auto-filled from weather if omitted")
    temperature_c: Optional[float] = Field(None, description="Auto-filled from weather if omitted")
    elevation_m: Optional[float] = Field(20, ge=0, description="District/upazila elevation in meters")
    water_quality_index: Optional[float] = Field(70, ge=0, le=100)
    population_density: Optional[float] = Field(1500, ge=0)
    season: SeasonType = Field("Monsoon", description="Monsoon | Post-Monsoon | Winter | Summer")

    model_config = ConfigDict(json_schema_extra={
            "example": {
                "rainfall_mm": 180, "river_level_m": 8.5, "humidity_percent": 88,
                "temperature_c": 29, "elevation_m": 5, "water_quality_index": 60,
                "population_density": 1800, "season": "Monsoon"
            }
        })


class FloodPredictionResponse(BaseModel):
    flood_probability: float
    flood_risk_level: str  # Low / Medium / High
    likely_severity_if_flood: str  # Minor / Moderate / Severe (heuristic, see docstring in flood.py)


# ---------- Model 2: Disease Outbreak Prediction ----------

class DiseasePredictionRequest(BaseModel):
    # Optional fields are auto-filled from the live weather service when the
    # dashboard only knows `location` + `river_level_m` + the previous two
    # weeks' case counts. See routers/disease.py:_build_feature_row().
    location: Optional[str] = Field(None, description="District name; used to auto-fill weather when omitted")
    rainfall_mm: Optional[float] = Field(None, ge=0)
    temperature_c: Optional[float] = None
    humidity_percent: Optional[float] = Field(None, ge=0, le=100)
    river_level_m: float = Field(..., ge=0)
    flood_depth_cm: float = Field(..., ge=0, description="Current observed flood depth, not a forecast")
    population_density: Optional[float] = Field(None, ge=0)
    sanitation_score: Optional[float] = Field(None, ge=0, le=1)
    water_quality_index: Optional[float] = Field(None, ge=0, le=100)
    previous_week_cases: float = Field(..., ge=0, description="Actual disease case count, last 7 days")
    previous_two_week_cases: float = Field(..., ge=0, description="Actual disease case count, last 14 days")
    season: SeasonType = "Monsoon"

    model_config = ConfigDict(json_schema_extra={
            "example": {
                "rainfall_mm": 220, "temperature_c": 29, "humidity_percent": 87,
                "river_level_m": 7.5, "flood_depth_cm": 55, "population_density": 2100,
                "sanitation_score": 0.35, "water_quality_index": 50,
                "previous_week_cases": 210, "previous_two_week_cases": 190, "season": "Monsoon"
            }
        })


class DiseasePredictionResponse(BaseModel):
    predicted_outbreak_risk: str  # Medium / High / Critical
    risk_probability_by_class: dict
    feature_importance: list = Field(
        default_factory=list,
        description="Top-6 features driving this prediction (global importance + observed value).",
    )


# ---------- Model 2B: Disease-Wise Breakdown ----------

class DiseaseBreakdownRequest(DiseasePredictionRequest):
    """Same inputs as Model 2 — the breakdown models were trained on the same
    feature set, just with per-disease target columns instead of a single
    risk classification."""
    pass


class DiseaseBreakdownResponse(BaseModel):
    disease_breakdown: dict  # e.g. {"cholera": 45.3, "diarrhea": 30.1, ...}
    dominant_disease: str
    total_predicted_cases: float


# ---------- Model 3: Time Series Forecasting ----------

class WeeklyObservation(BaseModel):
    """One historical week of data, in the same feature order the LSTM was trained on."""
    weekly_cases: float = Field(..., ge=0)
    rainfall_mm: float = Field(..., ge=0)
    temperature_c: float
    flood_depth_cm: float = Field(..., ge=0)
    sanitation_score: float = Field(..., ge=0, le=1)


class ForecastRequest(BaseModel):
    district: str = Field(..., description="Must match a district the scaler was fit on")
    recent_weeks: List[WeeklyObservation] = Field(
        ..., min_length=8, max_length=8,
        description="Exactly 8 most recent consecutive weekly observations, oldest first"
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "district": "Munshiganj",
            "recent_weeks": [
                {"weekly_cases": 120, "rainfall_mm": 90, "temperature_c": 28,
                 "flood_depth_cm": 20, "sanitation_score": 0.5}
            ] * 8
        }
    })


class ForecastResponse(BaseModel):
    district: str
    forecast_next_7_days_cases: float
    forecast_next_14_days_cases: float


# ---------- Model 5: Composite Risk Score ----------

class RiskScoreRequest(DiseasePredictionRequest):
    pass  # identical inputs to Model 2 -- risk score is built on top of it


class RiskScoreResponse(BaseModel):
    predicted_outbreak_risk: str
    flood_severity: str  # None / Minor / Moderate / Severe
    composite_score: float
    final_risk_level: str  # Low / Medium / High / Critical


class DistrictRiskItem(BaseModel):
    district: str
    risk_level: str
    composite_score: float
    flood_severity: str
    outbreak_risk: str


class AllDistrictsRiskResponse(BaseModel):
    districts: List[DistrictRiskItem]


# ---------- Model 6: Recommendation AI ----------

class RecommendationRequest(BaseModel):
    district: str
    risk_level: str = Field(..., description="Low | Medium | High | Critical -- typically Model 5's output")


class RecommendationResponse(BaseModel):
    district: str
    risk_level: str
    hospital_beds_available: int
    occupancy_percent: float
    recommendations: List[str]


# ---------- Combined: Risk + Recommendation in one call ----------

class FullAssessmentRequest(DiseasePredictionRequest):
    district: str


class FullAssessmentResponse(BaseModel):
    district: str
    risk_assessment: RiskScoreResponse
    recommendation: RecommendationResponse


# ---------- Combined Full Assessment (per-section status) ----------
#
# One server-side call that runs the full assessment for a district and
# returns per-section status.  Each section is independent: if one
# input is missing or one model errors, the other sections still run,
# and the frontend shows an honest empty/error state for that one
# section without blanking the rest of the page.  This is the path
# the /dashboard/[district] page uses for its auto-run assessment.
class AssessmentSection(BaseModel):
    """A single section of the per-district full assessment.

    The `status` field is one of:
      - "ok"          -- the section produced a result; `data` is populated.
      - "unavailable" -- the section is genuinely not applicable or has no
                         data for this district (e.g. no weekly history
                         yet); `reason` explains why.  Not an error.
      - "error"       -- the section tried to run but failed; `reason` is
                         the error message so the UI can show a retry
                         button.

    The `data_source` is the human label for where the inputs came
    from (e.g. "live", "fallback", "database"), and `as_of` is the
    observation timestamp for the underlying reading when known.
    """

    status: str = Field(..., description="ok | unavailable | error")
    reason: Optional[str] = None
    data_source: Optional[str] = None
    as_of: Optional[str] = None
    data: Optional[dict] = None


class FullAssessmentV2Response(BaseModel):
    """All sections the Full Assessment page needs, in a single payload.

    Sections included (in render order):
      - flood              (Model 1, available to all auth'd roles)
      - water_level        (river_level_m + water_quality_index, from DB /
                            weather; available to all auth'd roles)
      - overall_risk       (Model 5, available to all auth'd roles)
      - disease_outbreak   (Model 2, available to all auth'd roles)
      - disease_breakdown  (Model 2B, available to all auth'd roles)
      - forecast           (Model 3, available to all auth'd roles; requires
                            8 real weekly observations; "unavailable" with a
                            reason otherwise -- never a fake number)
      - satellite_extent   (GeoJSON of the registered flood extent, available
                            to all auth'd roles; "unavailable" for districts
                            with no registered export)
      - recommendation     (Model 6, operational roles only; the section is
                            present with status="forbidden" for citizens)
    """

    district: str
    is_operational: bool
    generated_at: str
    flood: AssessmentSection
    water_level: AssessmentSection
    overall_risk: AssessmentSection
    disease_outbreak: AssessmentSection
    disease_breakdown: AssessmentSection
    forecast: AssessmentSection
    satellite_extent: AssessmentSection
    recommendation: Optional[AssessmentSection] = None  # omitted for citizens


# ---------- Model 4: Satellite ----------

class FloodExtentResponse(BaseModel):
    district: str
    event_label: str
    geojson: dict


# ---------- Weather ----------

class WeatherObservationItem(BaseModel):
    location: str
    observed_at: str
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    rainfall: Optional[float] = None
    river_level_m: Optional[float] = None
    water_quality_index: Optional[float] = None
    data_source: Optional[str] = None


# ---------- History (weekly + prediction) ----------

class WeeklyHistoryItem(BaseModel):
    week_ending: str
    weekly_cases: float
    rainfall_mm: float
    temperature_c: float
    flood_depth_cm: float
    sanitation_score: float


class WeeklyHistorySeedItem(BaseModel):
    week_ending: str
    weekly_cases: float
    rainfall_mm: float
    temperature_c: float
    flood_depth_cm: float
    sanitation_score: float


class WeeklyHistoryResponse(BaseModel):
    district: str
    weeks: List[WeeklyHistoryItem]
    source: str


class PredictionHistoryItem(BaseModel):
    id: str
    model_name: str
    district: Optional[str] = None
    risk_level: Optional[str] = None
    probability: Optional[float] = None
    input_data: Optional[dict] = None
    output_data: Optional[dict] = None
    created_at: str


# ---------- Hotspots ----------

class HotspotDistrict(BaseModel):
    district: str
    cluster_id: int
    is_noise: bool
    signal_score: float
    flood_depth_cm: float
    water_quality_index: float


class HotspotResponse(BaseModel):
    algorithm: str
    source: str
    cluster_count: int
    districts: List[HotspotDistrict]


# ---------- Locations ----------

class LocationSearchResponse(BaseModel):
    query: str
    results: List[dict]


# ---------- SMS ----------

class SmsAlertRequest(BaseModel):
    district: str
    risk_level: str
    message: Optional[str] = None


class SmsSubscriptionRequest(BaseModel):
    phone_number: str
    district: Optional[str] = None
    risk_threshold: str = "Medium"


class SmsSubscriptionResponse(BaseModel):
    phone_number: str
    district: Optional[str] = None
    risk_threshold: str
    is_active: bool
