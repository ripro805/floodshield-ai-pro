import axios, { AxiosError } from 'axios';
import { getToken, clearToken } from './auth';
import type {
  FloodPredictionRequest, FloodPredictionResponse,
  DiseasePredictionRequest, DiseasePredictionResponse,
  DiseaseBreakdownRequest, DiseaseBreakdownResponse,
  ForecastRequest, ForecastResponse,
  RiskScoreRequest, RiskScoreResponse,
  RecommendationRequest, RecommendationResponse,
  FullAssessmentRequest, FullAssessmentResponse, FullAssessmentV2Response,
  SatelliteDistrictsResponse, FloodExtentResponse,
  SatelliteSegmentRequest, SatelliteSegmentResponse,
  WeeklyHistoryResponse,
    HotspotResponse,
    SmsSubscriptionRequest, SmsSubscriptionResponse,
    PredictionHistoryItem,
    LocationSearchResponse,
  WeatherResponse, UserSignup, UserLogin, Token, UserOut, ForgotPasswordResponse,
  HospitalUpdateHistoryResponse,
  DistrictsSummaryResponse, HospitalListResponse, NearbyHospital, HospitalPublic, HospitalOperational,
} from './types';

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const apiClient = axios.create({ baseURL: BASE_URL });

// ─── Request interceptor: attach Bearer token ─────────────────────────────────
apiClient.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ─── Response interceptor: handle 401 / 403 ──────────────────────────────────
apiClient.interceptors.response.use(
  (res) => res,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      clearToken();
      if (typeof window !== 'undefined') {
        window.location.href = '/login';
      }
    }
    // 403 is handled per-call (show inline message, no redirect)
    return Promise.reject(error);
  }
);

// ─── Auth ─────────────────────────────────────────────────────────────────────
export async function postSignup(body: UserSignup): Promise<Token> {
  const { data } = await apiClient.post<Token>('/auth/signup', body);
  return data;
}

export async function postLogin(body: UserLogin): Promise<Token> {
  const { data } = await apiClient.post<Token>('/auth/login', body);
  return data;
}

export async function getMe(): Promise<UserOut> {
  const { data } = await apiClient.get<UserOut>('/auth/me');
  return data;
}

export async function postForgotPassword(email: string): Promise<ForgotPasswordResponse> {
  const { data } = await apiClient.post<ForgotPasswordResponse>('/auth/forgot-password', { email });
  return data;
}

export async function postResetPassword(token: string, new_password: string): Promise<{ message: string }> {
  const { data } = await apiClient.post<{ message: string }>('/auth/reset-password', {
    token,
    new_password,
  });
  return data;
}

// ─── Weather ─────────────────────────────────────────────────────────────────
export async function getWeather(location: string): Promise<WeatherResponse> {
  const { data } = await apiClient.get<WeatherResponse>('/api/weather', {
    params: { location },
  });
  if (data.river_level_m != null && data.water_quality_index != null) {
    return data;
  }

  try {
    const response = await fetch('/data/district-environment.json', { cache: 'no-store' });
    if (!response.ok) {
      return data;
    }
    const observations = await response.json() as Record<string, Partial<WeatherResponse>>;
    const observation = observations[location.trim().toLowerCase()];
    return observation ? { ...data, ...observation } : data;
  } catch (error) {
    console.warn('District environmental fallback unavailable:', error);
    return data;
  }
}

// ─── Model 1: Flood Prediction ────────────────────────────────────────────────
export async function postFloodPrediction(
  body: FloodPredictionRequest
): Promise<FloodPredictionResponse> {
  const { data } = await apiClient.post<FloodPredictionResponse>('/predict/flood', body, {
    timeout: 60_000,
  });
  return data;
}

// ─── Model 2: Disease Outbreak ────────────────────────────────────────────────
export async function postDiseasePrediction(
  body: DiseasePredictionRequest
): Promise<DiseasePredictionResponse> {
  const { data } = await apiClient.post<DiseasePredictionResponse>('/predict/disease', body, {
    timeout: 60_000,
  });
  return data;
}

// ─── Model 2B: Disease-Wise Breakdown ─────────────────────────────────────────
export async function postDiseaseBreakdown(
  body: DiseaseBreakdownRequest
): Promise<DiseaseBreakdownResponse> {
  const { data } = await apiClient.post<DiseaseBreakdownResponse>('/predict/disease-breakdown', body, {
    timeout: 60_000,
  });
  return data;
}

// ─── Model 3: 7/14-Day Forecast ──────────────────────────────────────────────
export async function postForecast(body: ForecastRequest): Promise<ForecastResponse> {
  const { data } = await apiClient.post<ForecastResponse>('/predict/forecast', body, {
    timeout: 60_000,
  });
  return data;
}

// ─── Model 5: Composite Risk Score ───────────────────────────────────────────
export async function postRiskScore(body: RiskScoreRequest): Promise<RiskScoreResponse> {
  const { data } = await apiClient.post<RiskScoreResponse>('/predict/risk', body, {
    timeout: 60_000,
  });
  return data;
}

export async function getDiseaseHotspots(): Promise<HotspotResponse> {
  const { data } = await apiClient.get<HotspotResponse>('/predict/hotspots');
  return data;
}

export async function getSmsSubscription(): Promise<SmsSubscriptionResponse | null> {
  const { data } = await apiClient.get<SmsSubscriptionResponse | null>('/alerts/sms/subscription');
  return data;
}

export async function getPredictionHistory(params: {
  model_name?: string; district?: string; risk_level?: string;
} = {}): Promise<PredictionHistoryItem[]> {
  const { data } = await apiClient.get<PredictionHistoryItem[]>('/history/predictions', { params });
  return data;
}

export async function searchLocations(query: string): Promise<LocationSearchResponse> {
  const { data } = await apiClient.get<LocationSearchResponse>('/api/locations/search', { params: { q: query } });
  return data;
}

export async function subscribeSms(body: SmsSubscriptionRequest): Promise<SmsSubscriptionResponse> {
  const { data } = await apiClient.post<SmsSubscriptionResponse>('/alerts/sms/subscribe', body);
  return data;
}

export async function unsubscribeSms(): Promise<{ status: string }> {
  const { data } = await apiClient.delete<{ status: string }>('/alerts/sms/unsubscribe');
  return data;
}

// ─── Model 6: Recommendation AI ──────────────────────────────────────────────
export async function postRecommendation(
  body: RecommendationRequest
): Promise<RecommendationResponse> {
  const { data } = await apiClient.post<RecommendationResponse>('/recommend', body);
  return data;
}

// ─── Combined: Full Assessment ────────────────────────────────────────────────
export async function postFullAssessment(
  body: FullAssessmentRequest
): Promise<FullAssessmentResponse> {
  const { data } = await apiClient.post<FullAssessmentResponse>('/predict/full-assessment', body, {
    timeout: 60_000,
  });
  return data;
}



// ─── Per-Section Full Assessment (V2) ───────────────────────────────────────────
//
// One server-side call to /assessment/{district} that returns the entire
// assessment with per-section status.  The dashboard auto-runs this on
// page open.  Bounded by 90s (5 model calls in parallel) and 1 retry.
export async function getFullAssessmentV2(
  district: string,
  river_level?: number | null,
): Promise<FullAssessmentV2Response> {
  const params = river_level != null ? { river_level } : {};
  const { data } = await apiClient.get<FullAssessmentV2Response>(
    `/assessment/${encodeURIComponent(district)}`,
    { params, timeout: 90_000 },
  );
  return data;
}


// ─── Model 4: Satellite ──────────────────────────────────────────────────────
export async function getSatelliteDistricts(): Promise<SatelliteDistrictsResponse> {
  const { data } = await apiClient.get<SatelliteDistrictsResponse>('/satellite/flood-extent');
  return data;
}

export async function getSatelliteFloodExtent(
  district: string
): Promise<FloodExtentResponse | null> {
  try {
    const { data } = await apiClient.get<FloodExtentResponse>(
      `/satellite/flood-extent/${encodeURIComponent(district)}`
    );
    return data;
  } catch (error) {
    // 404 is expected for 63 of 64 districts — not an error state in the UI.
    if (axios.isAxiosError(error) && error.response?.status === 404) {
      return null;
    }
    throw error;
  }
}

// ─── Model 4B: SAR Segmentation (U-Net) ──────────────────────────────────────
export async function postSatelliteSegment(
  body: SatelliteSegmentRequest
): Promise<SatelliteSegmentResponse> {
  // The backend expects pixel_values as a bare List[List[List[float]]] body,
  // not wrapped in an object key. FastAPI deserialises this directly.
  const { data } = await apiClient.post<SatelliteSegmentResponse>(
    '/satellite/segment',
    body.pixel_values,
    {
      // U-Net inference on CPU-only Windows TensorFlow takes ~60-180s per
      // 256x256x2 SAR chip. Give it a generous 3 minutes before failing.
      timeout: 180_000,
    }
  );
  return data;
}

export async function ingestAndSegmentDistrict(
  district: string
): Promise<SatelliteSegmentResponse> {
  const { data } = await apiClient.get<{ pixel_values: SatelliteSegmentRequest['pixel_values'] }>(
    '/satellite/ingest',
    { params: { district } }
  );
  if (!data?.pixel_values) {
    throw new Error('Ingest response did not include pixel_values.');
  }
  return postSatelliteSegment({ pixel_values: data.pixel_values });
}

// ─── District Weekly History ───────────────────────────────────────────────
export async function getWeeklyHistory(district: string): Promise<WeeklyHistoryResponse> {
  try {
    const { data } = await apiClient.get<WeeklyHistoryResponse>(
      `/history/weekly/${encodeURIComponent(district)}`
    );
    return data;
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 404) {
      return { district, weeks: [], source: 'unavailable' };
    }
    throw error;
  }
}

// ─── Chatbot ──────────────────────────────────────────────────────────────────
import type {
  ChatMessageRequest, ChatMessageResponse,
  ReportIncidentRequest, ReportIncidentResponse,
} from './types';

export async function postChatMessage(body: ChatMessageRequest): Promise<ChatMessageResponse> {
  const { data } = await apiClient.post<ChatMessageResponse>('/chatbot/message', body);
  return data;
}

export async function postReportIncident(body: ReportIncidentRequest): Promise<ReportIncidentResponse> {
  const { data } = await apiClient.post<ReportIncidentResponse>('/chatbot/report-incident', body);
  return data;
}

export async function getChatHistory(conversationId: string): Promise<{ conversation_id: string; messages: Array<{ role: string; content: string; detected_intent: string | null; created_at: string }> }> {
  const { data } = await apiClient.get(`/chatbot/history/${conversationId}`);
  return data;
}

// ─── Error helpers ────────────────────────────────────────────────────────────
export function getApiErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const status = error.response?.status;
    if (status === 403) return "Your account type can't access this.";
    if (status === 404) return 'No data available for this district yet.';
    if (status === 422) return 'Invalid input — please check the form values.';
    const detail = error.response?.data?.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) return detail.map((d: { msg: string }) => d.msg).join(', ');
    // No HTTP response means the request never reached the server.
    // Most common cause: backend is down or unreachable on this network.
    if (error.code === 'ERR_NETWORK' || error.code === 'ECONNABORTED' || !error.response) {
      if (error.code === 'ECONNABORTED') {
        return 'The prediction is taking longer than expected. Please try again.';
      }
      return "Can't reach the FloodShield API. Is the backend running on port 8000?";
    }
  }
  return 'An unexpected error occurred. Please try again.';
}

// Admin gap-endpoint helpers
import type {
  AdminCreateUserPayload,
  AdminPredictionAuditItem,
  AdminKnowledgeArticle,
  AdminDataStatusResponse,
  AdminChatHistoryItem,
  AdminChatHistoryDetail,
  HospitalRecord,
} from './types';

export async function adminCreateUser(
  payload: AdminCreateUserPayload
): Promise<{ id: string; email: string; full_name: string; role: string; district: string | null; created_at: string | null }> {
  const { data } = await apiClient.post('/admin/users', payload);
  return data;
}

export async function adminListAllPredictions(params: {
  model_name?: string;
  district?: string;
  risk_level?: string;
  user_email?: string;
  limit?: number;
} = {}): Promise<{ count: number; items: AdminPredictionAuditItem[] }> {
  const { data } = await apiClient.get('/admin/predictions/all', { params });
  return data;
}

export async function adminListKnowledge(): Promise<{ count: number; items: AdminKnowledgeArticle[] }> {
  const { data } = await apiClient.get('/admin/knowledge');
  return data;
}

export async function adminCreateKnowledge(payload: {
  disease_name: string;
  symptoms: string;
  causes?: string;
  prevention_tips?: string;
  home_care_guidance?: string;
  when_to_see_doctor?: string;
  emergency_contact_info?: string;
  reference?: string;
}): Promise<AdminKnowledgeArticle> {
  const { data } = await apiClient.post('/admin/knowledge', payload);
  return data;
}

export async function adminUpdateKnowledge(
  id: string,
  patch: Partial<{
    disease_name: string;
    symptoms: string;
    causes: string;
    prevention_tips: string;
    home_care_guidance: string;
    when_to_see_doctor: string;
    emergency_contact_info: string;
    reference: string;
  }>
): Promise<AdminKnowledgeArticle> {
  const { data } = await apiClient.patch(`/admin/knowledge/${id}`, patch);
  return data;
}

export async function adminDeleteKnowledge(id: string): Promise<void> {
  await apiClient.delete(`/admin/knowledge/${id}`);
}

export async function adminDataStatus(): Promise<AdminDataStatusResponse> {
  const { data } = await apiClient.get('/admin/data-status');
  return data;
}

export async function adminListChatHistory(params: {
  user_email?: string;
  limit?: number;
} = {}): Promise<{ count: number; items: AdminChatHistoryItem[] }> {
  const { data } = await apiClient.get('/admin/chat-history', { params });
  return data;
}

export async function adminGetChatConversation(
  conversationId: string
): Promise<AdminChatHistoryDetail> {
  const { data } = await apiClient.get(`/admin/chat-history/${conversationId}`);
  return data;
}

// --- Hospitals (Gap 3) ---
export async function listHospitals(params: { district?: string; limit?: number } = {}): Promise<HospitalRecord[]> {
  // /hospitals returns a paginated wrapper: { items: [...], total, limit, offset, operational_fields_present }.
  // The UI treats `hospitals` as a flat array, so unwrap `.items`. This
  // fixes the `hospitals.reduce is not a function` crash that fires when
  // useMemo runs against the wrapper object.
  const { data } = await apiClient.get<HospitalRecord[] | { items: HospitalRecord[] }>('/hospitals', { params });
  if (Array.isArray(data)) return data;
  if (data && Array.isArray((data as { items?: HospitalRecord[] }).items)) {
    return (data as { items: HospitalRecord[] }).items;
  }
  return [];
}

export async function updateHospitalInventory(
  hospitalId: string,
  patch: Partial<{
    beds: number;
    doctors: number;
    nurses: number;
    ors_stock: number;
    iv_saline_stock: number;
    antibiotics_stock: number;
    occupancy_percent: number;
  }>
): Promise<{
  hospital: HospitalRecord;
  district_aggregate: Record<string, unknown>;
  audit_id: string | null;
  changed_fields: string[];
}> {
  const { data } = await apiClient.patch(`/hospitals/${hospitalId}`, patch);
  return data;
}
// Frontend helpers for the one-time admin bootstrap.

export interface BootstrapStatus {
  enabled: boolean;
  admin_exists: boolean;
  admin_count: number;
  usable: boolean;
}

export async function getBootstrapStatus(): Promise<BootstrapStatus> {
  const { data } = await apiClient.get<BootstrapStatus>('/auth/bootstrap-status');
  return data;
}

export async function promoteMeToAdmin(bootstrapToken: string): Promise<Token> {
  const { data } = await apiClient.post<Token>('/auth/promote-me', {
    bootstrap_token: bootstrapToken,
  });
  return data;
}
// Frontend helper: fetch and cache the EN -> BN district name table.

export interface DistrictBanglaPair {
  en: string;
  bn: string;
}

let _cache: Map<string, string> | null = null;
let _inflight: Promise<Map<string, string>> | null = null;

export async function loadDistrictBanglaMap(): Promise<Map<string, string>> {
  if (_cache) return _cache;
  if (_inflight) return _inflight;
  _inflight = apiClient
    .get<{ count: number; pairs: DistrictBanglaPair[] }>('/api/locations/bangla')
    .then((r) => {
      const m = new Map<string, string>();
      for (const p of r.data.pairs) {
        m.set(p.en.toLowerCase(), p.bn);
        // Also support case-insensitive lookup
        m.set(p.en, p.bn);
      }
      _cache = m;
      return m;
    })
    .finally(() => {
      _inflight = null;
    });
  return _inflight;
}

export function lookupBangla(map: Map<string, string> | null, enName: string): string | null {
  if (!map || !enName) return null;
  return map.get(enName) ?? map.get(enName.toLowerCase()) ?? null;
}
// Gap A: hospital audit log helper.
export async function getHospitalHistory(
  hospitalId: string,
  limit: number = 20
): Promise<HospitalUpdateHistoryResponse> {
  const { data } = await apiClient.get<HospitalUpdateHistoryResponse>(
    `/hospitals/${hospitalId}/history`,
    { params: { limit } }
  );
  return data;
}

// Gap B: self-demote helper.
export async function demoteMeToCitizen(): Promise<Token> {
  const { data } = await apiClient.post<Token>('/auth/demote-me');
  return data;
}


// ─── Admin issue inbox (Phase 8) ──────────────────────────────────────
export type AdminIssueStatus = 'open' | 'ack' | 'resolved' | 'dismissed';
export type AdminIssueCategory =
  | 'phone_wrong'
  | 'address_wrong'
  | 'name_wrong'
  | 'closed'
  | 'no_doctor'
  | 'no_stock'
  | 'coordinates_wrong'
  | 'other';

export interface AdminIssueRow {
  id: string;
  hospital_id: string;
  hospital_name: string;
  district: string | null;
  category: AdminIssueCategory;
  description: string;
  status: AdminIssueStatus;
  reporter_role: string | null;
  reporter_email: string | null;
  created_at: string;
}

export interface AdminIssueListResponse {
  items: AdminIssueRow[];
  total: number;
  limit: number;
  offset: number;
}

export interface AdminInboxStatusBucket {
  status: string;
  count: number;
}

export interface AdminInboxDistrictBucket {
  district: string;
  count: number;
  open: number;
  resolved: number;
  dismissed: number;
}

export interface AdminInboxSummary {
  total: number;
  by_status: AdminInboxStatusBucket[];
  by_district: AdminInboxDistrictBucket[];
  by_category: AdminInboxStatusBucket[];
}

export interface AdminIssueStatusUpdateResponse {
  id: string;
  status: AdminIssueStatus;
  updated_at: string;
}

export interface AdminIssueListOpts {
  district?: string;
  status?: AdminIssueStatus;
  category?: AdminIssueCategory;
  limit?: number;
  offset?: number;
}

export async function adminListHospitalIssues(
  opts: AdminIssueListOpts = {}
): Promise<AdminIssueListResponse> {
  const { data } = await apiClient.get<AdminIssueListResponse>(
    '/admin/hospitals/issues',
    { params: opts }
  );
  return data;
}

export async function adminInboxSummary(): Promise<AdminInboxSummary> {
  const { data } = await apiClient.get<AdminInboxSummary>(
    '/admin/hospitals/issues/summary'
  );
  return data;
}

export async function adminUpdateIssueStatus(
  issueId: string,
  status: Exclude<AdminIssueStatus, 'open'>
): Promise<AdminIssueStatusUpdateResponse> {
  const { data } = await apiClient.patch<AdminIssueStatusUpdateResponse>(
    `/admin/hospitals/issues/${issueId}/status`,
    { status }
  );
  return data;
}


/** POST /admin/hospitals/issues/status -- bulk ack/resolve/dismiss. */
export async function adminBulkUpdateIssueStatus(
  issueIds: string[],
  status: Exclude<AdminIssueStatus, 'open'>
): Promise<{
  requested: number;
  updated: number;
  not_found: string[];
  status: AdminIssueStatus;
  updated_at: string;
}> {
  const { data } = await apiClient.post(
    '/admin/hospitals/issues/status',
    { issue_ids: issueIds, status }
  );
  return data;
}

// ─── District hospital issue rollup (read-only, citizen + ops) ──────────
export interface IssueRollupCategory {
  category: string;
  count: number;
}

export interface DistrictHospitalIssueRollup {
  district: string;
  total: number;
  open: number;
  ack: number;
  resolved: number;
  dismissed: number;
  last_filed_at: string | null;
  top_categories: IssueRollupCategory[];
}

export async function getDistrictHospitalIssueRollup(
  district: string
): Promise<DistrictHospitalIssueRollup> {
  const { data } = await apiClient.get<DistrictHospitalIssueRollup>(
    `/hospitals/districts/${encodeURIComponent(district)}/issue-rollup`
  );
  return data;
}

// ─── Hospital Directory (Phase 2-3) ────────────────────────────────────────

/**
 * GET /hospitals/districts-summary -- one row per district (all 64).
 * Operational roles additionally receive low-stock flags.
 */
export async function getDistrictsSummary(): Promise<DistrictsSummaryResponse> {
  const { data } = await apiClient.get<DistrictsSummaryResponse>('/hospitals/districts-summary');
  return data;
}

/** Narrowing helper: tells whether a list item is the operational shape. */
export function isOperationalHospital(
  h: HospitalPublic | HospitalOperational
): h is HospitalOperational {
  return 'ors_stock' in h;
}

export interface HospitalListParams {
  district?: string;
  type?: string;
  q?: string;
  status?: 'Available' | 'Limited' | 'Full';
  sort?: 'name' | 'occupancy' | 'beds' | 'type';
  limit?: number;
  offset?: number;
}

export async function getHospitals(
  params: HospitalListParams = {}
): Promise<HospitalListResponse> {
  const { data } = await apiClient.get<HospitalListResponse>('/hospitals', { params });
  return data;
}

export async function getHospital(
  id: string
): Promise<HospitalPublic | HospitalOperational> {
  const { data } = await apiClient.get<HospitalPublic | HospitalOperational>(
    `/hospitals/${id}`
  );
  return data;
}

export interface NearbyParams {
  lat: number;
  lng: number;
  radius_km?: number;
  limit?: number;
}

export async function getNearbyHospitals(
  p: NearbyParams
): Promise<NearbyHospital[]> {
  const { data } = await apiClient.get<NearbyHospital[]>('/hospitals/nearby', {
    params: { ...p },
  });
  return data;
}

/** "Get directions in Google Maps" link -- works on desktop + mobile. */
export function googleMapsDirectionsUrl(
  destLat: number,
  destLng: number,
  originLat?: number,
  originLng?: number
): string {
  if (originLat !== undefined && originLng !== undefined) {
    return `https://www.google.com/maps/dir/?api=1&origin=${originLat},${originLng}&destination=${destLat},${destLng}&travelmode=driving`;
  }
  return `https://www.google.com/maps/dir/?api=1&destination=${destLat},${destLng}&travelmode=driving`;
}


// ─── Admin CSV import (Phase 6) ────────────────────────────────────────────
export interface HospitalImportSummary {
  deduped_rows: number;
  districts: number;
  hospitals_affected: number;
  rollups_built: number;
  backfilled: number;
  skipped: string[];
  data_source: string;
}

/**
 * POST /admin/hospitals/import -- admin-only.
 * Pass the raw File from an <input type="file">.  The server runs
 * the same dedupe / weighted-occupancy pipeline the CLI seeder uses
 * and returns a summary the UI can render verbatim.
 */
export async function importHospitalCsv(
  file: File,
  opts: { reset?: boolean } = {}
): Promise<HospitalImportSummary> {
  const form = new FormData();
  form.append('file', file);
  if (opts.reset) form.append('reset', 'true');
  const { data } = await apiClient.post<HospitalImportSummary>(
    '/admin/hospitals/import',
    form,
    {
      // Critical -- axios will set the right multipart boundary if we
      // DON'T pre-set Content-Type.
      headers: { 'Content-Type': 'multipart/form-data' },
    }
  );
  return data;
}

/** GET /admin/hospitals/import/template -- returns a small example CSV. */
export async function getHospitalImportTemplate(): Promise<Blob> {
  const { data } = await apiClient.get<Blob>(
    '/admin/hospitals/import/template',
    { responseType: 'blob' }
  );
  return data;
}


// ─── PATCH /hospitals/{id} (Phase 7) ────────────────────────────────────────
export interface HospitalPatchPayload {
  // Inventory (any ops role)
  beds?: number;
  doctors?: number;
  nurses?: number;
  ors_stock?: number;
  iv_saline_stock?: number;
  antibiotics_stock?: number;
  occupancy_percent?: number;
  // Ops metadata
  phone?: string | null;
  address?: string | null;
  upazila?: string | null;
  beds_occupied?: number | null;
  // Admin-only
  name?: string;
  hospital_type?: string | null;
  latitude?: number | null;
  longitude?: number | null;
}

/**
 * PATCH /hospitals/{id} -- update a single hospital's record.
 * Server enforces role-scoped field writes:
 *   - inventory + phone/address/upazila/beds_occupied: any ops role
 *   - name / hospital_type / lat / lng: admin only
 * Returns the updated row (same shape as the GET /hospitals/{id} response).
 */
export async function patchHospital(
  id: string,
  body: HospitalPatchPayload
): Promise<HospitalOperational> {
  const { data } = await apiClient.patch<HospitalOperational>(
    `/hospitals/${id}`,
    body
  );
  return data;
}


// ─── Hospital issue reports (Phase 7) ────────────────────────────────────────
export type HospitalIssueCategory =
  | 'phone_wrong'
  | 'address_wrong'
  | 'name_wrong'
  | 'closed'
  | 'no_doctor'
  | 'no_stock'
  | 'coordinates_wrong'
  | 'other';

export interface HospitalIssue {
  id: string;
  hospital_id: string;
  category: HospitalIssueCategory;
  description: string;
  status: 'open' | 'ack' | 'resolved' | 'dismissed';
  reporter_role: string | null;
  created_at: string;
}

export interface HospitalIssueCreatePayload {
  category: HospitalIssueCategory;
  description: string;
}

/** POST /hospitals/{id}/issues -- any auth'd user. */
export async function createHospitalIssue(
  hospitalId: string,
  body: HospitalIssueCreatePayload
): Promise<HospitalIssue> {
  const { data } = await apiClient.post<HospitalIssue>(
    `/hospitals/${hospitalId}/issues`,
    body
  );
  return data;
}

/** GET /hospitals/{id}/issues?status=open -- newest first. */
export async function listHospitalIssues(
  hospitalId: string,
  opts: { status?: 'open' | 'ack' | 'resolved' | 'dismissed' } = {}
): Promise<HospitalIssue[]> {
  const { data } = await apiClient.get<HospitalIssue[]>(
    `/hospitals/${hospitalId}/issues`,
    { params: opts }
  );
  return data;
}

/** Human-friendly label for an issue category. */
export const HOSPITAL_ISSUE_CATEGORIES: { value: HospitalIssueCategory; label: string }[] = [
  { value: 'phone_wrong',       label: 'Phone number is wrong' },
  { value: 'address_wrong',     label: 'Address is wrong' },
  { value: 'name_wrong',        label: 'Name is wrong' },
  { value: 'coordinates_wrong', label: 'Pin is in the wrong place' },
  { value: 'closed',            label: 'Facility is closed' },
  { value: 'no_doctor',         label: 'No doctor available' },
  { value: 'no_stock',          label: 'Stock shortage' },
  { value: 'other',             label: 'Other' },
];

// ─── Hospital issue history (per-hospital timeline) ────────────────
export type HospitalIssueHistoryEventKind =
  | 'reported'
  | 'ack'
  | 'resolved'
  | 'dismissed';

export interface HospitalIssueHistoryEvent {
  issue_id: string;
  kind: HospitalIssueHistoryEventKind;
  at: string;
  actor_role: string | null;
  actor_email: string | null;
  category: string;
  description: string;
  status: string;
}

export interface HospitalIssueHistory {
  hospital_id: string;
  hospital_name: string;
  district: string | null;
  total: number;
  events: HospitalIssueHistoryEvent[];
}

export async function getHospitalIssueHistory(
  hospitalId: string,
  limit: number = 200
): Promise<HospitalIssueHistory> {
  const { data } = await apiClient.get<HospitalIssueHistory>(
    `/hospitals/${hospitalId}/issue-history`,
    { params: { limit } }
  );
  return data;
}

// ══════════════════════════════════════════════════════════════════════════
// OPERATIONAL MANAGEMENT LAYER (Phase 1 - 7)
// ══════════════════════════════════════════════════════════════════════════

// ─── 1. Hospital Operations ──────────────────────────────────────────────
export interface HospitalInventoryItem {
  id: string;
  hospital_id: string;
  item_name: string;
  category: string;
  unit: string;
  current_stock: number;
  min_threshold: number;
  batch_number?: string | null;
  expiry_date?: string | null;
  storage_location?: string | null;
  is_critical_shortage: boolean;
  updated_at?: string | null;
}

export interface HospitalStockTransaction {
  id: string;
  item_id: string;
  transaction_type: string;
  quantity: number;
  previous_stock: number;
  new_stock: number;
  batch_number?: string | null;
  notes?: string | null;
  performed_by_email: string;
  created_at: string;
}

export async function getHospitalInventory(
  hospitalId: string,
  category?: string,
  search?: string
): Promise<HospitalInventoryItem[]> {
  const { data } = await apiClient.get<HospitalInventoryItem[]>(
    `/hospitals/${hospitalId}/inventory`,
    { params: { category, search } }
  );
  return data;
}

export async function createHospitalInventoryItem(
  hospitalId: string,
  payload: Partial<HospitalInventoryItem>
): Promise<{ message: string; item_id: string }> {
  const { data } = await apiClient.post<{ message: string; item_id: string }>(
    `/hospitals/${hospitalId}/inventory`,
    payload
  );
  return data;
}

export async function postHospitalStockTransaction(
  hospitalId: string,
  itemId: string,
  payload: { transaction_type: string; quantity: number; notes?: string; batch_number?: string }
): Promise<{ message: string; new_stock: number }> {
  const { data } = await apiClient.post<{ message: string; new_stock: number }>(
    `/hospitals/${hospitalId}/inventory/${itemId}/transaction`,
    payload
  );
  return data;
}

export async function getHospitalInventoryTransactions(
  hospitalId: string,
  limit: number = 50
): Promise<HospitalStockTransaction[]> {
  const { data } = await apiClient.get<HospitalStockTransaction[]>(
    `/hospitals/${hospitalId}/inventory/transactions`,
    { params: { limit } }
  );
  return data;
}

export async function patchHospitalProfile(
  hospitalId: string,
  payload: {
    total_beds?: number;
    beds_occupied?: number;
    icu_beds_total?: number;
    icu_beds_occupied?: number;
    operating_status?: string;
    emergency_contact?: string;
  }
): Promise<{ message: string; available_general_beds: number; available_icu_beds: number }> {
  const { data } = await apiClient.patch<{ message: string; available_general_beds: number; available_icu_beds: number }>(
    `/hospitals/${hospitalId}/profile`,
    payload
  );
  return data;
}

export async function getHospitalForecastPrep(hospitalId: string): Promise<any> {
  const { data } = await apiClient.get<any>(`/hospitals/${hospitalId}/forecast-prep`);
  return data;
}

// ─── 2. NGO Operations ───────────────────────────────────────────────────
export interface ReliefCampaign {
  id: string;
  organization_name: string;
  title: string;
  description?: string | null;
  target_districts: string;
  target_upazilas?: string | null;
  target_population: number;
  start_date: string;
  end_date?: string | null;
  team_lead_name?: string | null;
  team_lead_contact?: string | null;
  status: 'draft' | 'active' | 'paused' | 'completed' | 'archived';
  created_by_email: string;
  created_at?: string;
}

export interface NgoInventoryItem {
  id: string;
  organization_name: string;
  item_name: string;
  category: string;
  unit: string;
  current_stock: number;
  min_threshold: number;
  warehouse_location?: string | null;
  batch_number?: string | null;
  expiry_date?: string | null;
  updated_at?: string | null;
}

export interface ReliefDistributionTask {
  id: string;
  campaign_id?: string | null;
  organization_name: string;
  title: string;
  district: string;
  upazila?: string | null;
  union_or_village?: string | null;
  planned_supplies?: any[];
  actual_distributed?: any[];
  beneficiary_households: number;
  people_reached: number;
  status: 'planned' | 'dispatched' | 'in_transit' | 'completed' | 'incomplete';
  assigned_team?: string | null;
  notes?: string | null;
  created_at?: string;
  completed_at?: string | null;
}

export async function listNgoCampaigns(statusFilter?: string): Promise<ReliefCampaign[]> {
  const { data } = await apiClient.get<ReliefCampaign[]>('/ngo/campaigns', {
    params: { status: statusFilter }
  });
  return data;
}

export async function createNgoCampaign(payload: Partial<ReliefCampaign>): Promise<{ message: string; campaign_id: string }> {
  const { data } = await apiClient.post<{ message: string; campaign_id: string }>('/ngo/campaigns', payload);
  return data;
}

export async function patchNgoCampaignStatus(campaignId: string, status: string): Promise<{ message: string }> {
  const { data } = await apiClient.patch<{ message: string }>(`/ngo/campaigns/${campaignId}/status`, { status });
  return data;
}

export async function listNgoInventory(category?: string): Promise<NgoInventoryItem[]> {
  const { data } = await apiClient.get<NgoInventoryItem[]>('/ngo/inventory', { params: { category } });
  return data;
}

export async function createNgoInventoryItem(payload: Partial<NgoInventoryItem>): Promise<{ message: string; item_id: string }> {
  const { data } = await apiClient.post<{ message: string; item_id: string }>('/ngo/inventory', payload);
  return data;
}

export async function postNgoStockTransaction(
  itemId: string,
  payload: { transaction_type: string; quantity: number; recipient_location?: string; notes?: string }
): Promise<{ message: string; new_stock: number }> {
  const { data } = await apiClient.post<{ message: string; new_stock: number }>(
    `/ngo/inventory/${itemId}/transaction`,
    payload
  );
  return data;
}

export async function listNgoDistributionTasks(district?: string, statusFilter?: string): Promise<ReliefDistributionTask[]> {
  const { data } = await apiClient.get<ReliefDistributionTask[]>('/ngo/distribution-tasks', {
    params: { district, status: statusFilter }
  });
  return data;
}

export async function createNgoDistributionTask(payload: Partial<ReliefDistributionTask>): Promise<{ message: string; task_id: string }> {
  const { data } = await apiClient.post<{ message: string; task_id: string }>('/ngo/distribution-tasks', payload);
  return data;
}

export async function patchNgoDistributionTask(taskId: string, payload: Partial<ReliefDistributionTask>): Promise<{ message: string }> {
  const { data } = await apiClient.patch<{ message: string }>(`/ngo/distribution-tasks/${taskId}`, payload);
  return data;
}

export async function getNgoAiAllocation(district: string): Promise<any> {
  const { data } = await apiClient.get<any>(`/ngo/ai-allocation/${district}`);
  return data;
}

// ─── 3. Field & Citizen Operations ───────────────────────────────────────
export interface FieldTask {
  id: string;
  title: string;
  description?: string | null;
  task_type: string;
  district: string;
  upazila?: string | null;
  priority: string;
  status: string;
  assigned_to_email: string;
  assigned_by_email?: string | null;
  deadline?: string | null;
  completion_notes?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface FieldVisitLog {
  id: string;
  health_worker_email: string;
  district: string;
  upazila?: string | null;
  location_name: string;
  households_visited: number;
  suspected_cases_count: number;
  suspected_diseases?: string | null;
  ors_packets_distributed: number;
  water_purification_tablets_distributed: number;
  referrals_count: number;
  urgent_shortage_reported?: string | null;
  notes?: string | null;
  created_at?: string;
}

export interface CitizenReportItem {
  id: string;
  text: string;
  label: string;
  severity: string;
  district?: string | null;
  upazila?: string | null;
  reporter_email?: string | null;
  status: string;
  image_url?: string | null;
  created_at?: string;
}

export async function listFieldTasks(district?: string, statusFilter?: string): Promise<FieldTask[]> {
  const { data } = await apiClient.get<FieldTask[]>('/field/tasks', {
    params: { district, status: statusFilter }
  });
  return data;
}

export async function createFieldTask(payload: Partial<FieldTask>): Promise<{ message: string; task_id: string }> {
  const { data } = await apiClient.post<{ message: string; task_id: string }>('/field/tasks', payload);
  return data;
}

export async function updateFieldTaskStatus(taskId: string, status: string, completion_notes?: string): Promise<{ message: string }> {
  const { data } = await apiClient.patch<{ message: string }>(`/field/tasks/${taskId}`, {
    status,
    completion_notes,
  });
  return data;
}

export async function listFieldVisitLogs(district?: string): Promise<FieldVisitLog[]> {
  const { data } = await apiClient.get<FieldVisitLog[]>('/field/visit-logs', { params: { district } });
  return data;
}

export async function createFieldVisitLog(payload: Partial<FieldVisitLog>): Promise<{ message: string; log_id: string }> {
  const { data } = await apiClient.post<{ message: string; log_id: string }>('/field/visit-logs', payload);
  return data;
}

export async function submitCitizenReport(payload: Partial<CitizenReportItem>): Promise<{ message: string; report_id: string; status: string }> {
  const { data } = await apiClient.post<{ message: string; report_id: string; status: string }>(
    '/citizen/reports',
    payload
  );
  return data;
}

export async function listCitizenMyReports(email?: string): Promise<CitizenReportItem[]> {
  const { data } = await apiClient.get<CitizenReportItem[]>('/citizen/my-reports', { params: { email } });
  return data;
}

export async function withdrawCitizenReport(reportId: string): Promise<{ message: string }> {
  const { data } = await apiClient.patch<{ message: string }>(`/citizen/reports/${reportId}/withdraw`);
  return data;
}

export async function getPublicAlerts(district?: string): Promise<any[]> {
  const { data } = await apiClient.get<any[]>('/citizen/public-alerts', { params: { district } });
  return data;
}

export async function getPublicHospitals(district?: string): Promise<any[]> {
  const { data } = await apiClient.get<any[]>('/citizen/public-hospitals', { params: { district } });
  return data;
}

// ─── 4. Government Emergency Coordination ────────────────────────────────
export interface CommandOverviewData {
  status: string;
  timestamp: string;
  hospital_capacity: {
    total_facilities: number;
    total_general_beds: number;
    available_general_beds: number;
    total_icu_beds: number;
    available_icu_beds: number;
    critical_stock_shortages: number;
  };
  ngo_operations: {
    active_campaigns: number;
    active_relief_tasks: number;
  };
  coordination: {
    pending_resource_requests: number;
    active_official_alerts: number;
    unverified_citizen_reports: number;
    field_investigations_logged: number;
  };
}

export interface ResourceRequestItem {
  id: string;
  requester_email: string;
  requester_role: string;
  organization_name: string;
  district: string;
  upazila?: string | null;
  request_type: string;
  requested_items: any[];
  urgency: string;
  justification: string;
  status: string;
  allocated_items?: any[] | null;
  reviewer_email?: string | null;
  review_notes?: string | null;
  created_at?: string;
  reviewed_at?: string | null;
}

export interface OfficialAlertItem {
  id: string;
  title_bn: string;
  title_en: string;
  message_bn: string;
  message_en: string;
  severity: string;
  target_districts: string;
  status: string;
  channel: string;
  sent_sms_count: number;
  published_at?: string | null;
  created_at?: string;
}

export async function getGovernmentCommandOverview(): Promise<CommandOverviewData> {
  const { data } = await apiClient.get<CommandOverviewData>('/government/command-overview');
  return data;
}

export async function listResourceRequests(district?: string, statusFilter?: string, urgency?: string): Promise<ResourceRequestItem[]> {
  const { data } = await apiClient.get<ResourceRequestItem[]>('/government/resource-requests', {
    params: { district, status: statusFilter, urgency }
  });
  return data;
}

export async function submitResourceRequest(payload: Partial<ResourceRequestItem>): Promise<{ message: string; request_id: string }> {
  const { data } = await apiClient.post<{ message: string; request_id: string }>(
    '/government/resource-requests',
    payload
  );
  return data;
}

export async function reviewResourceRequest(
  requestId: string,
  payload: { status: string; review_notes?: string; allocated_items?: any[] }
): Promise<{ message: string }> {
  const { data } = await apiClient.patch<{ message: string }>(
    `/government/resource-requests/${requestId}/review`,
    payload
  );
  return data;
}

export async function createResourceAllocation(payload: {
  request_id: string;
  source_depot_or_facility: string;
  destination_facility: string;
  allocated_items: any[];
  tracking_number?: string;
}): Promise<{ message: string; allocation_id: string }> {
  const { data } = await apiClient.post<{ message: string; allocation_id: string }>(
    '/government/resource-allocations',
    payload
  );
  return data;
}

export async function listOfficialAlerts(statusFilter?: string): Promise<OfficialAlertItem[]> {
  const { data } = await apiClient.get<OfficialAlertItem[]>('/alerts/official', {
    params: { status: statusFilter }
  });
  return data;
}

export async function draftOfficialAlert(payload: Partial<OfficialAlertItem>): Promise<{ message: string; alert_id: string }> {
  const { data } = await apiClient.post<{ message: string; alert_id: string }>('/alerts/official', payload);
  return data;
}

export async function publishOfficialAlert(alertId: string): Promise<{ message: string }> {
  const { data } = await apiClient.post<{ message: string }>(`/alerts/official/${alertId}/publish`);
  return data;
}

export async function cancelOfficialAlert(alertId: string): Promise<{ message: string }> {
  const { data } = await apiClient.patch<{ message: string }>(`/alerts/official/${alertId}/cancel`);
  return data;
}

export async function getGovernmentIssuesRollup(district?: string): Promise<any> {
  const { data } = await apiClient.get<any>('/government/issues-rollup', { params: { district } });
  return data;
}

// ─── 5. Automation & Admin Monitoring ────────────────────────────────────
export interface AutomationJobItem {
  id: string;
  job_name: string;
  description?: string | null;
  interval_seconds: number;
  status: string;
  last_run_at?: string | null;
  next_run_at?: string | null;
  last_duration_seconds?: number | null;
  last_error?: string | null;
  total_runs: number;
  success_runs: number;
  failure_runs: number;
  is_active: boolean;
  updated_at?: string | null;
}

export interface AuditEventItem {
  id: string;
  user_email: string;
  user_role: string;
  action: string;
  resource_type: string;
  resource_id?: string | null;
  details?: string | null;
  created_at: string;
}

export async function listAdminJobs(): Promise<AutomationJobItem[]> {
  const { data } = await apiClient.get<AutomationJobItem[]>('/admin/jobs');
  return data;
}

export async function triggerAdminJobRun(jobName: string): Promise<{ message: string; details: any }> {
  const { data } = await apiClient.post<{ message: string; details: any }>(`/admin/jobs/${jobName}/run-now`);
  return data;
}

export async function listAdminAuditLogs(resourceType?: string, limit: number = 50): Promise<AuditEventItem[]> {
  const { data } = await apiClient.get<AuditEventItem[]>('/admin/audit-logs', {
    params: { resource_type: resourceType, limit }
  });
  return data;
}

// ─── 6. Reports & Data Exports ───────────────────────────────────────────
export function getReportDownloadUrl(
  reportType: 'daily-risk' | 'hospital-shortages' | 'ngo-distribution' | 'resource-requests'
): string {
  return `${BASE_URL}/reports/${reportType}/csv`;
}
