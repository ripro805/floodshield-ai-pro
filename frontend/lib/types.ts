/**
 * TypeScript types mirroring the FloodShield AI backend Pydantic schemas.
 * Field names must match the backend exactly — do not rename.
 */

// ─── Auth ────────────────────────────────────────────────────────────────────

export type UserRole =
  | 'citizen'
  | 'health_worker'
  | 'hospital'
  | 'ngo'
  | 'government'
  | 'admin';

export type SeasonType = 'Monsoon' | 'Post-Monsoon' | 'Winter' | 'Summer';

export interface UserOut {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  district: string | null;
}

export interface Token {
  access_token: string;
  token_type: 'bearer';
  user: UserOut;
}

export interface UserSignup {
  email: string;
  password: string;
  full_name: string;
  role: UserRole;
  district?: string | null;
}

export interface UserLogin {
  email: string;
  password: string;
}

export interface ForgotPasswordResponse {
  message: string;
  reset_token?: string;
}

// ─── Weather ─────────────────────────────────────────────────────────────────

export interface WeatherResponse {
  location: string;
  temperature: number;
  humidity: number;
  wind_speed: number;
  condition: string;
  rainfall: number;
  data_source: 'live' | 'fallback';
  river_level_m?: number;
  population_density?: number;
  sanitation_score?: number;
  water_quality_index?: number;
  district_conditions_date?: string;
}

// ─── Model 1: Flood Prediction ───────────────────────────────────────────────

export interface FloodPredictionRequest {
  location?: string | null;
  rainfall_mm?: number | null;
  river_level_m: number;
  humidity_percent?: number | null;
  temperature_c?: number | null;
  elevation_m?: number;
  water_quality_index?: number;
  population_density?: number;
  season?: SeasonType;
}

export interface FloodPredictionResponse {
  flood_probability: number;
  flood_risk_level: 'Low' | 'Medium' | 'High';
  likely_severity_if_flood: 'Minor' | 'Moderate' | 'Severe';
  feature_importance: FeatureImportance[];
}

export interface FeatureImportance {
  feature: string;
  importance: number;
  value: number;
}

// ─── Model 2: Disease Outbreak Prediction ────────────────────────────────────

export interface DiseasePredictionRequest {
  location?: string | null;
  rainfall_mm?: number | null;
  temperature_c?: number | null;
  humidity_percent?: number | null;
  river_level_m: number;
  flood_depth_cm: number;
  population_density: number;
  sanitation_score: number;
  water_quality_index: number;
  previous_week_cases: number;
  previous_two_week_cases: number;
  season?: SeasonType;
}

export interface DiseasePredictionResponse {
  predicted_outbreak_risk: 'Medium' | 'High' | 'Critical';
  risk_probability_by_class: {
    Medium?: number;
    High?: number;
    Critical?: number;
  };
  feature_importance: FeatureImportance[];
}

// ─── Model 2B: Disease-Wise Breakdown ────────────────────────────────────────

export type DiseaseBreakdownRequest = DiseasePredictionRequest;

export interface DiseaseBreakdownResponse {
  disease_breakdown: Record<string, number>;  // e.g. {"Cholera": 45.3, "Diarrhea": 30.1, ...}
  dominant_disease: string;
  total_predicted_cases: number;
}

// ─── Model 3: 7/14-Day Forecast ──────────────────────────────────────────────

export interface WeeklyObservation {
  weekly_cases: number;
  rainfall_mm: number;
  temperature_c: number;
  flood_depth_cm: number;
  sanitation_score: number;
}

export interface ForecastRequest {
  district: string;
  recent_weeks: WeeklyObservation[]; // exactly 8, oldest first
}

export interface ForecastResponse {
  district: string;
  forecast_next_7_days_cases: number;
  forecast_next_14_days_cases: number;
}

export interface PredictionHistoryItem {
  id: string;
  model_name: string;
  district: string | null;
  risk_level: string | null;
  probability: number | null;
  input_data: Record<string, unknown>;
  output_data: Record<string, unknown>;
  created_at: string;
}

export interface LocationSearchItem {
  name: string;
  district: string;
  kind: 'district' | 'upazila';
}

export interface LocationSearchResponse {
  query: string;
  results: LocationSearchItem[];
}

// ─── Model 5: Composite Risk Score ───────────────────────────────────────────

// RiskScoreRequest is identical to DiseasePredictionRequest (backend inherits with pass)
export type RiskScoreRequest = DiseasePredictionRequest;

export interface RiskScoreResponse {
  predicted_outbreak_risk: 'Medium' | 'High' | 'Critical';
  flood_severity: 'None' | 'Minor' | 'Moderate' | 'Severe';
  composite_score: number;
  final_risk_level: 'Low' | 'Medium' | 'High' | 'Critical';
}

// ─── Disease Hotspot Detection ──────────────────────────────────────────────

export interface HotspotDistrict {
  district: string;
  cluster_id: number;
  is_noise: boolean;
  signal_score: number;
  flood_depth_cm: number;
  water_quality_index: number;
}

export interface HotspotResponse {
  algorithm: string;
  source: string;
  cluster_count: number;
  districts: HotspotDistrict[];
}

// ─── SMS Alerts ─────────────────────────────────────────────────────────────

export interface SmsSubscriptionRequest {
  phone_number: string;
  district?: string | null;
  risk_threshold: 'Medium' | 'High' | 'Critical';
}

export interface SmsSubscriptionResponse {
  phone_number: string;
  district: string | null;
  risk_threshold: 'Medium' | 'High' | 'Critical';
  is_active: boolean;
}

// ─── Model 6: Recommendation AI ──────────────────────────────────────────────

export interface RecommendationRequest {
  district: string;
  risk_level: 'Low' | 'Medium' | 'High' | 'Critical';
}

export interface RecommendationResponse {
  district: string;
  risk_level: string;
  hospital_beds_available: number;
  occupancy_percent: number;
  recommendations: string[];
}

// ─── Combined: Full Assessment (Model 5 + 6) ─────────────────────────────────

export interface FullAssessmentRequest extends DiseasePredictionRequest {
  district: string;
}

export interface FullAssessmentResponse {
  district: string;
  risk_assessment: RiskScoreResponse;
  recommendation: RecommendationResponse;
}



// ─── Per-Section Full Assessment (V2) ───────────────────────────────────────────
// One server-side call returns every section the Full Assessment page
// needs.  Each section is independent: a missing input or a model
// error in one section does not blank the others.  Status is
// "ok" | "unavailable" | "error" so the UI can render the right
// skeleton/empty/error state for each section.
export interface AssessmentSection {
  status: 'ok' | 'unavailable' | 'error';
  reason?: string | null;
  data_source?: string | null;
  as_of?: string | null;
  data?: Record<string, unknown> | null;
}

export interface SatelliteExtentSectionData {
  district: string;
  event_label: string;
  geojson: unknown;
}

export interface FullAssessmentV2Response {
  district: string;
  is_operational: boolean;
  generated_at: string;
  flood: AssessmentSection;
  water_level: AssessmentSection;
  overall_risk: AssessmentSection;
  disease_outbreak: AssessmentSection;
  disease_breakdown: AssessmentSection;
  forecast: AssessmentSection;
  satellite_extent: AssessmentSection;
  // Absent entirely from the JSON for non-operational users; the server
  // enforces the role rule, the UI just reads what's there.
  recommendation?: AssessmentSection | null;
}


// ─── Model 4: Satellite ──────────────────────────────────────────────────────

export interface SatelliteDistrictsResponse {
  available_districts: string[];
}

export interface FloodExtentResponse {
  district: string;
  event_label: string;
  geojson: GeoJSON.FeatureCollection;
  before_geojson?: GeoJSON.FeatureCollection | null;
  after_geojson?: GeoJSON.FeatureCollection | null;
}

/**
 * POST /satellite/segment
 * Payload: a 256×256×2 nested float array (VV band, VH band), each value 0–1,
 * normalised exactly as Model4B_UNet_Sen1Floods11.ipynb's normalize_sar().
 */
export type SatelliteSegmentPixels = number[][][]; // [256][256][2]

export interface SatelliteSegmentRequest {
  /** 256×256×2 SAR chip as nested lists (VV, VH bands, normalised 0–1). */
  pixel_values: SatelliteSegmentPixels;
}

export interface SatelliteSegmentResponse {
  /** Fraction of pixels classified as flood water by the U-Net (0–1). */
  /** Fraction of pixels classified as flood water by the U-Net (0–1). */
  flood_pixel_ratio: number;
  note: string;
  /** "ok" when the U-Net produced a valid result, "fallback" when the
   *  model head was NaN-corrupted and the result came from the
   *  SAR-band heuristic.  Optional for backward compatibility. */
  model_status?: 'ok' | 'fallback';
  threshold?: number;
  valid_pixel_ratio?: number;
  scene_window?: string;
  data_source?: string;
  mask_overlay?: {
    bounds?: [[number, number], [number, number]];
    threshold?: number;
    flood_pixel_ratio?: number;
  } | null;
}



// ─── District Weekly History ─────────────────────────────────────────────────

export interface WeeklyHistoryItem {
  week_ending: string;        // ISO date string e.g. "2024-08-11"
  weekly_cases: number;
  rainfall_mm: number;
  temperature_c: number;
  flood_depth_cm: number;
  sanitation_score: number;
}

export interface WeeklyHistoryResponse {
  district: string;
  weeks: WeeklyHistoryItem[];
  /** The response contains eight persisted observations suitable for forecasting. */
  source: 'database' | 'unavailable';
}

// ─── UI helpers ──────────────────────────────────────────────────────────────

export type RiskLevel = 'Low' | 'Medium' | 'High' | 'Critical';

export const RISK_COLORS: Record<RiskLevel, string> = {
  Low: '#2DD4BF',
  Medium: '#FBBF24',
  High: '#FB923C',
  Critical: '#F43F5E',
};

export const RISK_GLOW: Record<RiskLevel, string> = {
  Low: '0 0 20px rgba(45,212,191,0.4)',
  Medium: '0 0 20px rgba(251,191,36,0.4)',
  High: '0 0 20px rgba(251,146,60,0.4)',
  Critical: '0 0 24px rgba(244,63,94,0.6)',
};

export const OPERATIONAL_ROLES: UserRole[] = [
  'health_worker',
  'hospital',
  'ngo',
  'government',
  'admin',
];

export const BANGLADESH_DISTRICTS = [
  'Bagerhat', 'Bandarban', 'Barguna', 'Barishal', 'Bhola', 'Bogura',
  'Brahmanbaria', 'Chandpur', 'Chattogram', 'Chuadanga', 'Cox\'s Bazar',
  'Cumilla', 'Dhaka', 'Dinajpur', 'Faridpur', 'Feni', 'Gaibandha',
  'Gazipur', 'Gopalganj', 'Habiganj', 'Jamalpur', 'Jashore', 'Jhalokati',
  'Jhenaidah', 'Joypurhat', 'Khagrachhari', 'Khulna', 'Kishoreganj',
  'Kurigram', 'Kushtia', 'Lakshmipur', 'Lalmonirhat', 'Madaripur',
  'Magura', 'Manikganj', 'Meherpur', 'Moulvibazar', 'Munshiganj',
  'Mymensingh', 'Naogaon', 'Narail', 'Narayanganj', 'Narsingdi',
  'Natore', 'Netrokona', 'Nilphamari', 'Noakhali', 'Pabna', 'Panchagarh',
  'Patuakhali', 'Pirojpur', 'Rajbari', 'Rajshahi', 'Rangamati',
  'Rangpur', 'Satkhira', 'Shariatpur', 'Sherpur', 'Sirajganj',
  'Sunamganj', 'Sylhet', 'Tangail', 'Thakurgaon',
];

// ─── Chatbot ──────────────────────────────────────────────────────────────────

export type ChatIntentType =
  | 'disease_info'
  | 'flood_safety'
  | 'hospital_info'
  | 'emergency'
  | 'incident_report'
  | 'general';

export type ChatLanguage = 'bn' | 'en' | 'banglish' | 'hi' | 'auto';

export type ChatSeverity = 'Low' | 'Medium' | 'High' | 'Critical';

export type ChatActionType = 'navigate' | 'call_endpoint' | 'emergency_call';

export interface ChatSuggestedAction {
  label: string;
  action_type: ChatActionType;
  target: string;
}

/** Whitelisted UI action types the agent can emit.  Frontend validates. */
export type ChatUiActionType =
  | 'navigate'
  | 'select_district'
  | 'run_flood_check'
  | 'run_full_assessment'
  | 'open_satellite_view'
  | 'open_alerts'
  | 'open_reports'
  | 'open_hospital_resources'
  | 'open_hospital_directory'
  | 'open_hospital';

export interface ChatUiAction {
  type: ChatUiActionType;
  params: Record<string, any>;
}

export interface ChatMessageRequest {
  message: string;
  conversation_id: string | null;
  language: ChatLanguage;
}

export interface ChatMessageResponse {
  conversation_id: string;
  reply: string;
  detected_intent: ChatIntentType;
  referenced_disease: string | null;
  used_live_data: boolean;
  suggested_actions: ChatSuggestedAction[];
  /** Server-validated UI actions the agent emitted. */
  ui_actions: ChatUiAction[];
  /** Tool names invoked during this turn (for transparency/debugging). */
  tools_used: string[];
  /** data_source tags seen across tool results. */
  data_sources: string[];
}

export interface ReportIncidentRequest {
  text: string;
  district: string | null;
  latitude: number | null;
  longitude: number | null;
}

export interface ReportIncidentResponse {
  label: string;
  severity: ChatSeverity;
  recommended_action: string;
  alert_created: boolean;
}

// --- Admin: gap endpoints ------------------------------------------------

export interface AdminCreateUserPayload {
  email: string;
  password: string;
  full_name: string;
  role: Exclude<UserRole, 'citizen'>;
  district?: string | null;
}

export interface AdminPredictionAuditItem {
  id: string;
  user_email: string;
  user_role: UserRole;
  model_name: string;
  district: string | null;
  risk_level: string | null;
  probability: number | null;
  created_at: string;
}

export interface AdminKnowledgeArticle {
  id: string;
  disease_name: string;
  symptoms: string;
  causes: string | null;
  prevention_tips: string | null;
  home_care_guidance: string | null;
  when_to_see_doctor: string | null;
  emergency_contact_info: string | null;
  reference: string | null;
  created_at: string | null;
}

export interface AdminDataStatusItem {
  district: string;
  hospitals: number;
  has_aggregate: boolean;
  has_environment: boolean;
  weekly_history_rows: number;
  is_fully_covered: boolean;
}

export interface AdminDataStatusResponse {
  total_districts: number;
  fully_covered: number;
  missing_coverage: number;
  items: AdminDataStatusItem[];
}

export interface AdminChatHistoryItem {
  conversation_id: string;
  user_email: string | null;
  user_role: UserRole | null;
  message_count: number;
  last_active: string | null;
  first_user_message: string | null;
  last_message_preview: string | null;
}

export interface AdminChatHistoryDetail {
  conversation_id: string;
  user_email: string | null;
  user_role: UserRole | null;
  messages: Array<{
    id: string;
    role: 'user' | 'assistant';
    content: string;
    detected_intent: ChatIntentType | null;
    referenced_disease: string | null;
    created_at: string;
  }>;
}

export interface HospitalRecord {
  id: string;
  name: string;
  district: string;
  hospital_type: string | null;
  // The wire shape from the directory router (`GET /hospitals`) uses
  // `beds_total` for the user-facing "Beds" column.  The PATCH inventory
  // endpoint and the historical `_hospital_to_dict` payload use `beds`
  // (the column name on the Hospital row).  We accept either, marked
  // optional, so the consumer can read whichever the server actually
  // sent without a type error.
  beds?: number;
  beds_total?: number;
  total_beds?: number;
  beds_occupied?: number;
  icu_beds_total?: number;
  icu_beds_occupied?: number;
  operating_status?: string;
  doctors?: number;
  nurses?: number;
  ors_stock?: number;
  iv_saline_stock?: number;
  antibiotics_stock?: number;
  occupancy_percent?: number;

  longitude: number | null;
  // --- Audit trail (Gap A) ---
  last_edited_at: string | null;
  last_edited_by_id: string | null;
}

export interface HospitalChange {
  from: number;
  to: number;
}

export interface HospitalUpdateHistoryItem {
  id: string;
  editor: { id: string; email: string; full_name: string; role: string } | null;
  changes: Record<string, HospitalChange>;
  district_aggregate: Record<string, number> | null;
  created_at: string | null;
}

export interface HospitalUpdateHistoryResponse {
  hospital_id: string;
  hospital_name: string;
  last_edited_at: string | null;
  last_edited_by: { id: string; email: string; full_name: string; role: string } | null;
  count: number;
  items: HospitalUpdateHistoryItem[];
}


// ─── Hospital Directory (Phase 2-3) ────────────────────────────────────────

/** Capacity status used by the directory's "Available | Limited | Full" badge. */
export type CapacityStatus = 'Available' | 'Limited' | 'Full' | 'Unknown';

/**
 * Directory fields every authenticated user (citizen included) can see.
 * Mirrors the backend's `HospitalPublic` Pydantic schema.
 */
export interface HospitalPublic {
  id: string;
  name: string;
  hospital_type: string | null;
  district: string;
  upazila: string | null;
  address: string | null;
  latitude: number | null;
  longitude: number | null;
  capacity_status: CapacityStatus;
  /** Only set on the `/hospitals/nearby` endpoint. */
  distance_km: number | null;
  /** "seed" | "manual_update" | "external_import" -- drives the "Sample data" badge. */
  data_source: string;
  coordinates_source: string | null;
  address_source: string | null;
  /** NULL for seed rows (we never fabricate phone numbers). */
  phone: string | null;
}

/**
 * Extra fields visible only to operational roles.  Extends
 * HospitalPublic with beds / stock numbers + low-stock flags.
 */
export interface HospitalOperational extends HospitalPublic {
  beds_total: number;
  beds_occupied: number | null;
  occupancy_percent: number;
  doctors: number;
  nurses: number;
  ors_stock: number;
  iv_saline_stock: number;
  antibiotics_stock: number;
  ors_low: boolean;
  iv_saline_low: boolean;
  antibiotics_low: boolean;
  last_updated: string | null;
}

/** One row per district in the national overview grid. */
export interface DistrictHospitalSummary {
  district: string;
  name_bn: string | null;
  hospital_count: number;
  total_beds: number;
  mean_occupancy_percent: number;
  capacity_status: CapacityStatus;
  // Operational-only fields (null for citizens)
  total_ors?: number | null;
  total_iv_saline?: number | null;
  total_antibiotics?: number | null;
  ors_low?: boolean | null;
  iv_saline_low?: boolean | null;
  antibiotics_low?: boolean | null;
}

export interface DistrictsSummaryResponse {
  items: DistrictHospitalSummary[];
  total_districts: number;
}

export interface HospitalListResponse {
  items: (HospitalPublic | HospitalOperational)[];
  total: number;
  limit: number;
  offset: number;
  /** True iff items are HospitalOperational (operational role). */
  operational_fields_present: boolean;
}

/** One row in the /hospitals/nearby response.  distance_km is always set. */
export interface NearbyHospital extends HospitalPublic {
  distance_km: number;
}
