import { useMutation, useQuery } from '@tanstack/react-query';
import {
  postFloodPrediction, postDiseasePrediction, postDiseaseBreakdown, postForecast,
  postRiskScore, postRecommendation, postFullAssessment,
  getFullAssessmentV2,
  getSatelliteDistricts, getSatelliteFloodExtent, ingestAndSegmentDistrict,
  getWeeklyHistory, getDiseaseHotspots, getPredictionHistory,
  searchLocations,
  getSmsSubscription, subscribeSms, unsubscribeSms,
  getWeather,
  getDistrictHospitalIssueRollup,
  postChatMessage, postReportIncident, getChatHistory,
} from '@/lib/api';
import type {
  FloodPredictionRequest, DiseasePredictionRequest, DiseaseBreakdownRequest, ForecastRequest,
  RiskScoreRequest, RecommendationRequest, FullAssessmentRequest,
  ChatMessageRequest, ReportIncidentRequest,
  SmsSubscriptionRequest,
} from '@/lib/types';

// ─── Model 1: Flood Prediction ────────────────────────────────────────────────
export function useFloodPrediction() {
  return useMutation({ mutationFn: (body: FloodPredictionRequest) => postFloodPrediction(body) });
}

// ─── Model 2: Disease Outbreak ────────────────────────────────────────────────
export function useDiseasePrediction() {
  return useMutation({ mutationFn: (body: DiseasePredictionRequest) => postDiseasePrediction(body) });
}

// ─── Model 2B: Disease-Wise Breakdown ─────────────────────────────────────────
export function useDiseaseBreakdown() {
  return useMutation({ mutationFn: (body: DiseaseBreakdownRequest) => postDiseaseBreakdown(body) });
}

// ─── Model 3: 7/14-Day Forecast ──────────────────────────────────────────────
export function useForecast() {
  return useMutation({ mutationFn: (body: ForecastRequest) => postForecast(body) });
}

// ─── Model 5: Composite Risk ──────────────────────────────────────────────────
export function useRiskScore() {
  return useMutation({ mutationFn: (body: RiskScoreRequest) => postRiskScore(body) });
}

export function useDiseaseHotspots() {
  return useQuery({
    queryKey: ['diseaseHotspots', 'environmental-v2'],
    queryFn: getDiseaseHotspots,
    staleTime: 0,
    refetchOnMount: 'always',
  });
}

export function useSmsSubscription() {
  return useQuery({ queryKey: ['smsSubscription'], queryFn: getSmsSubscription });
}

export function usePredictionHistory(params: { model_name?: string; district?: string; risk_level?: string } = {}) {
  return useQuery({ queryKey: ['predictionHistory', params], queryFn: () => getPredictionHistory(params), staleTime: 30 * 1000 });
}

export function useLocationSearch(query: string) {
  return useQuery({ queryKey: ['locationSearch', query], queryFn: () => searchLocations(query), enabled: query.trim().length >= 2, staleTime: 5 * 60 * 1000 });
}

export function useSubscribeSms() {
  return useMutation({ mutationFn: (body: SmsSubscriptionRequest) => subscribeSms(body) });
}

export function useUnsubscribeSms() {
  return useMutation({ mutationFn: unsubscribeSms });
}

// ─── Model 6: Recommendation ─────────────────────────────────────────────────
export function useRecommendation() {
  return useMutation({ mutationFn: (body: RecommendationRequest) => postRecommendation(body) });
}

// ─── Combined Full Assessment ─────────────────────────────────────────────────
export function useFullAssessment() {
  return useMutation({ mutationFn: (body: FullAssessmentRequest) => postFullAssessment(body) });
}

// ─── Per-Section Full Assessment (V2) ───────────────────────────────────────────
//
// Auto-runs on the /dashboard/[district] page.  The query key uses only
// the district name (a primitive), so React Query doesn't refetch on
// every render and doesn't mix districts.  `staleTime: 5 min` keeps
// the "back" button from triggering an instant refetch; "Re-run" is a
// manual button in the UI.
export function useFullAssessmentV2(district: string | null) {
  return useQuery({
    queryKey: ['fullAssessmentV2', district],
    queryFn: () => getFullAssessmentV2(district as string),
    enabled: Boolean(district),
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
    refetchOnWindowFocus: false,
    retry: 1,
  });
}


// ─── Satellite districts list ─────────────────────────────────────────────────
export function useSatelliteDistricts() {
  return useQuery({
    queryKey: ['satelliteDistricts'],
    queryFn: getSatelliteDistricts,
    staleTime: 10 * 60 * 1000,
  });
}

// ─── Satellite flood extent for a district ────────────────────────────────────
export function useSatelliteFloodExtent(district: string | null) {
  return useQuery({
    queryKey: ['satelliteFloodExtent', district],
    queryFn: () => getSatelliteFloodExtent(district!),
    enabled: !!district,
    retry: false,   // 404 is a valid empty response, not a retryable failure
    staleTime: 5 * 60 * 1000,
  });
}

// ─── Satellite SAR segmentation (Model 4B U-Net) ─────────────────────────────
export function useSatelliteSegment() {
  return useMutation({
    mutationFn: (district: string) => ingestAndSegmentDistrict(district),
  });
}

// ─── District Weekly History ─────────────────────────────────────────────────
export function useWeeklyHistory(district: string | null) {
  return useQuery({
    queryKey: ['weeklyHistory', district],
    queryFn: () => getWeeklyHistory(district!),
    enabled: !!district,
    staleTime: 10 * 60 * 1000,  // 10 min -- history doesn't change mid-session
    retry: false,               // 404 means no data yet; don't hammer the server
  });
}

// ─── Live weather ─────────────────────────────────────────────────────────────
export function useWeather(location: string | null) {
  return useQuery({
    queryKey: ['weather', location, 'environmental-v2'],
    queryFn: () => getWeather(location!),
    enabled: !!location,
    staleTime: 0,
    refetchOnMount: 'always',
    refetchOnWindowFocus: false,
  });
}

// ─── District hospital issue rollup (read-only, citizen + ops) ──────────────
export function useDistrictHospitalIssueRollup(district: string | null) {
  return useQuery({
    queryKey: ['districtIssueRollup', district],
    queryFn: () => getDistrictHospitalIssueRollup(district!),
    enabled: !!district,
    staleTime: 5 * 60 * 1000,  // 5 min -- counts move slowly
    retry: false,
  });
}

// ─── Chatbot: send message ────────────────────────────────────────────────────
export function useChatMessage() {
  return useMutation({ mutationFn: (body: ChatMessageRequest) => postChatMessage(body) });
}

// ─── Chatbot: report incident ─────────────────────────────────────────────────
export function useReportIncident() {
  return useMutation({ mutationFn: (body: ReportIncidentRequest) => postReportIncident(body) });
}

// ─── Chatbot: get conversation history ────────────────────────────────────────
export function useChatHistory(conversationId: string | null) {
  return useQuery({
    queryKey: ['chatHistory', conversationId],
    queryFn: () => getChatHistory(conversationId!),
    enabled: !!conversationId,
    retry: false,
  });
}
