'use client';

/**
 * /dashboard/[district] — the auto-running Full Assessment panel.
 *
 * Calls /assessment/{district} once on mount (and on district change)
 * and renders each section in the order the spec requires:
 *
 *   1. Disease Outbreak Risk   (Model 2, overall + class probs)
 *   2. Disease Breakdown       (Model 2B, 6 diseases, dominant first)
 *   3. 7/14-day Forecast       (Model 3, LSTM)
 *   4. Satellite Flood Extent  (Model 4, GeoJSON + U-Net sky-blue mask)
 *      -- "Run Segmentation" stays click-only, never auto-runs
 *
 * Each section is independent: a missing input or a failing model
 * in one section shows an honest skeleton / empty / error state for
 * that section only, never blanking the rest of the page.
 *
 * Hooked queries use primitives in the query key (`['fullAssessmentV2', district]`)
 * so React Query does not refetch on every render and never mixes
 * results between districts.  `staleTime: 5 min` keeps the "back"
 * button from triggering an instant refetch; "Re-run" is the manual
 * button.  When the district changes, React Query cancels the
 * in-flight fetch (and the `district` param changes), so a stale
 * Feni result can never flash under Dhaka.
 */
import { useState, useEffect, useRef, useCallback, useMemo, Component, type ReactNode } from 'react';
import dynamic from 'next/dynamic';
import { motion } from 'framer-motion';
import {
  Loader2, AlertTriangle, AlertCircle, CheckCircle2, Activity, Pill,
  TrendingUp, Droplets, Satellite as SatelliteIcon, RefreshCw,
  Beaker, ShieldAlert, ListOrdered, Map as MapIcon, Cloud,
} from 'lucide-react';
import { useFullAssessmentV2 } from '@/hooks';
import { useMutation } from '@tanstack/react-query';
import { ingestAndSegmentDistrict, getApiErrorMessage, apiClient } from '@/lib/api';
import type {
  FullAssessmentV2Response,
  AssessmentSection,
  SatelliteSegmentResponse,
} from '@/lib/types';
import GlassCard from '@/components/cards/GlassCard';

// Leaflet must not run during SSR.
const AssessmentMap = dynamic(() => import('./AssessmentMap'), { ssr: false });

// ── Per-section error boundary ─────────────────────────────────────────────────
//
// A throw inside one section (e.g. a hot-reload artifact, a bad
// number coming back from the server) must not blank the rest of the
// page.  Each section is wrapped in this so the boundary isolates the
// failure to just that card.
class SectionBoundary extends Component<{ name: string; children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) { return { error }; }
  componentDidCatch(error: Error) {
    // eslint-disable-next-line no-console
    console.error(`[${this.props.name}] crashed:`, error);
  }
  componentDidUpdate(prev: { children: ReactNode }) {
    if (prev.children !== this.props.children && this.state.error) {
      this.setState({ error: null });
    }
  }
  render() {
    if (this.state.error) {
      return (
        <div className="p-4 rounded-xl border border-red-500/20 bg-red-500/5 text-xs text-red-300">
          <AlertTriangle size={12} className="inline mr-1" />
          Section crashed: {this.state.error.message}
        </div>
      );
    }
    return this.props.children;
  }
}

// ── Shared status / skeleton helpers ───────────────────────────────────────────

const TONE = {
  Low: '#34D399', Medium: '#FCD34D', High: '#FB923C', Critical: '#F43F5E',
  None: '#94A3B8', Minor: '#FCD34D', Moderate: '#FB923C', Severe: '#F43F5E',
} as const;

function riskTone(level: string | undefined): string {
  if (!level) return '#94A3B8';
  return (TONE as Record<string, string>)[level] ?? '#94A3B8';
}

function SectionHeader({ icon: Icon, title, status, action }: {
  icon: any; title: string; status: AssessmentSection | null; action?: ReactNode;
}) {
  const tone =
    !status ? 'text-white/40' :
    status.status === 'ok' ? 'text-emerald-300' :
    status.status === 'unavailable' ? 'text-amber-300' :
    'text-red-300';
  return (
    <div className="flex items-center justify-between gap-2 mb-3">
      <h3 className="text-base font-bold text-white flex items-center gap-2">
        <Icon size={15} className="text-blue-300" />
        {title}
      </h3>
      <div className="flex items-center gap-2">
        {status && (
          <span className={`text-[10px] uppercase tracking-wider font-semibold ${tone}`}>
            {status.status === 'ok' ? 'Live' : status.status === 'unavailable' ? 'Unavailable' : 'Error'}
          </span>
        )}
        {action}
      </div>
    </div>
  );
}

function Skeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="space-y-2 animate-pulse" aria-busy="true" aria-live="polite">
      {[...Array(lines)].map((_, i) => (
        <div key={i} className="h-4 rounded bg-white/08" style={{ width: `${80 - i * 12}%` }} />
      ))}
    </div>
  );
}

function SectionState({ status, fallback }: { status: AssessmentSection | null; fallback: string }) {
  if (!status) return <div className="text-xs text-white/40">{fallback}</div>;
  if (status.status === 'unavailable') {
    return (
      <div className="flex items-start gap-2 p-3 rounded-lg text-amber-200 text-xs"
           style={{ background: 'rgba(251, 191, 36, 0.08)', border: '1px solid rgba(251, 191, 36, 0.18)' }}>
        <AlertCircle size={13} className="mt-0.5 shrink-0" />
        <div>
          <p className="font-semibold">Not available right now</p>
          <p className="text-amber-200/80 mt-0.5">{status.reason || 'No data for this section yet.'}</p>
        </div>
      </div>
    );
  }
  if (status.status === 'error') {
    return (
      <div className="flex items-start gap-2 p-3 rounded-lg text-red-300 text-xs"
           style={{ background: 'rgba(244, 63, 94, 0.06)', border: '1px solid rgba(244, 63, 94, 0.20)' }}>
        <AlertTriangle size={13} className="mt-0.5 shrink-0" />
        <div>
          <p className="font-semibold">This section failed</p>
          <p className="text-red-300/80 mt-0.5">{status.reason || 'Unexpected error.'}</p>
        </div>
      </div>
    );
  }
  return null;
}

// ── Section: Disease Outbreak Risk ─────────────────────────────────────────────

function DiseaseOutbreakSection({ section, loading }: { section: AssessmentSection | null; loading: boolean }) {
  if (loading) return <Skeleton lines={4} />;
  if (!section || section.status !== 'ok') return <SectionState status={section} fallback="Loading disease risk…" />;
  const data = (section.data ?? {}) as {
    predicted_outbreak_risk?: string;
    risk_probability_by_class?: Record<string, number>;
  };
  const cls = data.predicted_outbreak_risk ?? '—';
  const probs = data.risk_probability_by_class ?? {};
  const probKeys = Object.keys(probs);
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <span
          className="px-3 py-1 rounded-full text-xs font-bold uppercase border font-mono"
          style={{ color: riskTone(cls), borderColor: riskTone(cls) }}
        >
          {cls}
        </span>
        <span className="text-[10px] text-white/40 uppercase tracking-wider">Predicted outbreak level</span>
      </div>
      {probKeys.length > 0 && (
        <div className="space-y-1.5">
          {probKeys.map((k) => (
            <div key={k} className="flex items-center gap-2 text-[11px]">
              <span className="text-white/55 w-16">{k}</span>
              <div className="flex-1 h-1.5 rounded bg-white/10 overflow-hidden">
                <div className="h-full rounded" style={{ width: `${Math.min((probs[k] ?? 0) * 100, 100)}%`, background: riskTone(k) }} />
              </div>
              <span className="font-mono text-white/65 w-12 text-right">{((probs[k] ?? 0) * 100).toFixed(1)}%</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Section: Disease Breakdown ─────────────────────────────────────────────────

function DiseaseBreakdownSection({ section, loading }: { section: AssessmentSection | null; loading: boolean }) {
  if (loading) return <Skeleton lines={4} />;
  if (!section || section.status !== 'ok') return <SectionState status={section} fallback="Loading disease breakdown…" />;
  const data = (section.data ?? {}) as {
    disease_breakdown?: Record<string, number>;
    dominant_disease?: string;
    total_predicted_cases?: number;
  };
  const bd = data.disease_breakdown ?? {};
  // Sort descending so the dominant disease is on top
  const entries = Object.entries(bd).sort((a, b) => (b[1] ?? 0) - (a[1] ?? 0));
  const dominant = data.dominant_disease || entries[0]?.[0] || '—';
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-xs text-white/65">
        <ListOrdered size={12} className="text-blue-300" />
        Dominant: <span className="text-white font-semibold">{dominant}</span>
        {data.total_predicted_cases != null && (
          <span className="text-white/40">· {data.total_predicted_cases.toFixed(0)} cases / week</span>
        )}
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {entries.map(([name, count]) => (
          <div key={name} className="flex items-center justify-between p-2 rounded-md"
               style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
            <div className="flex items-center gap-2">
              <Pill size={11} className="text-teal-300" />
              <span className="text-[12px] text-white">{name}</span>
              {name === dominant && <span className="text-[9px] uppercase text-emerald-300 font-bold">★</span>}
            </div>
            <span className="font-mono text-white text-sm">{(count ?? 0).toFixed(1)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Section: Forecast ──────────────────────────────────────────────────────────

function ForecastSection({ section, loading }: { section: AssessmentSection | null; loading: boolean }) {
  if (loading) return <Skeleton lines={3} />;
  if (!section || section.status !== 'ok') return <SectionState status={section} fallback="Loading forecast…" />;
  const data = (section.data ?? {}) as {
    district?: string;
    forecast_next_7_days_cases?: number;
    forecast_next_14_days_cases?: number;
  };
  const v7 = data.forecast_next_7_days_cases ?? 0;
  const v14 = data.forecast_next_14_days_cases ?? 0;
  const maxV = Math.max(v7, v14, 1);
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <div className="p-3 rounded-md" style={{ background: 'rgba(56, 189, 248, 0.06)', border: '1px solid rgba(56, 189, 248, 0.18)' }}>
          <p className="text-[10px] uppercase tracking-wider text-white/50">7-day forecast</p>
          <p className="text-white text-xl font-mono mt-1">{v7.toFixed(1)}</p>
          <p className="text-[10px] text-white/40">cases / week</p>
        </div>
        <div className="p-3 rounded-md" style={{ background: 'rgba(45, 212, 191, 0.06)', border: '1px solid rgba(45, 212, 191, 0.18)' }}>
          <p className="text-[10px] uppercase tracking-wider text-white/50">14-day forecast</p>
          <p className="text-white text-xl font-mono mt-1">{v14.toFixed(1)}</p>
          <p className="text-[10px] text-white/40">cases / week</p>
        </div>
      </div>
      {/* Tiny comparison bar */}
      <div className="space-y-1.5 text-[11px]">
        <div className="flex items-center gap-2">
          <span className="text-white/55 w-14">7d</span>
          <div className="flex-1 h-2 rounded bg-white/10 overflow-hidden">
            <div className="h-full rounded" style={{ width: `${(v7 / maxV) * 100}%`, background: '#38BDF8' }} />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-white/55 w-14">14d</span>
          <div className="flex-1 h-2 rounded bg-white/10 overflow-hidden">
            <div className="h-full rounded" style={{ width: `${(v14 / maxV) * 100}%`, background: '#2DD4BF' }} />
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Section: Satellite Flood Extent + U-Net overlay ───────────────────────────

interface SegmentState {
  status: 'idle' | 'loading' | 'ok' | 'error';
  data?: SatelliteSegmentResponse;
  error?: string;
}

function SatelliteFloodSection({
  district, satSection, loading,
}: {
  district: string; satSection: AssessmentSection | null; loading: boolean;
}) {
  const [seg, setSeg] = useState<SegmentState>({ status: 'idle' });
  // Track previous district so a click on "Run" doesn't reuse an old
  // district's result.
  const segDistrictRef = useRef<string | null>(null);

  const runSeg = useCallback(async () => {
    segDistrictRef.current = district;
    setSeg({ status: 'loading' });
    try {
      const { data } = await apiClient.post<SatelliteSegmentResponse>(
        '/satellite/segment',
        null,
        {
          params: { district },
          timeout: 180_000,
        }
      );
      // Guard against late completion from a previous district
      if (segDistrictRef.current !== district) return;
      setSeg({ status: 'ok', data });
    } catch (e) {
      if (segDistrictRef.current !== district) return;
      setSeg({ status: 'error', error: getApiErrorMessage(e) });
    }
  }, [district]);

  // Reset on district change
  useEffect(() => {
    segDistrictRef.current = null;
    setSeg({ status: 'idle' });
  }, [district]);

  const hasGeojson = satSection?.status === 'ok' && Boolean(
    (satSection.data as { geojson?: unknown } | null)?.geojson
  );

  // If the spec section is unavailable and we have no GeoJSON at all,
  // we can still show a small map frame + "no data" hint.
  return (
    <div className="space-y-3">
      {loading && !satSection ? (
        <Skeleton lines={4} />
      ) : satSection && satSection.status !== 'ok' ? (
        <SectionState status={satSection} fallback="Loading satellite extent…" />
      ) : (
        <>
          <div className="rounded-lg overflow-hidden border border-white/10" style={{ height: 260 }}>
            <AssessmentMap
              district={district}
              geojson={(satSection?.data as { geojson?: unknown } | undefined)?.geojson}
              segmentation={seg.status === 'ok' && seg.data ? seg.data : null}
              segmentationLoading={seg.status === 'loading'}
            />
          </div>
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div className="flex items-center gap-3 text-[11px] text-white/55">
              <span className="inline-flex items-center gap-1">
                <span className="inline-block w-3 h-3 rounded" style={{ background: 'rgba(56, 189, 248, 0.55)' }} />
                Water detected by U-Net
              </span>
              {seg.status === 'ok' && seg.data && (
                <span className="text-white/65 font-mono">
                  Coverage: {(seg.data.flood_pixel_ratio * 100).toFixed(1)}%
                  {seg.data.valid_pixel_ratio != null && (
                    <span className="ml-2 text-white/45 text-[10px]" title="Valid SAR pixels">
                      (valid: {(seg.data.valid_pixel_ratio * 100).toFixed(0)}%)
                    </span>
                  )}
                  {seg.data.model_status === 'fallback' && (
                    <span className="ml-2 text-amber-300" title={seg.data.note}>
                      (heuristic)
                    </span>
                  )}
                </span>
              )}
            </div>
            <button
              onClick={runSeg}
              disabled={seg.status === 'loading' || !hasGeojson}
              title={!hasGeojson ? 'No GeoJSON extent available for this district' : 'Run the U-Net over the latest SAR chip'}
              className="px-3 py-1.5 rounded-lg text-xs font-semibold text-white flex items-center gap-1.5 transition disabled:opacity-50"
              style={{ background: 'linear-gradient(135deg, #38BDF8, #2DD4BF)' }}
            >
              {seg.status === 'loading' ? <Loader2 size={12} className="animate-spin" /> : <SatelliteIcon size={12} />}
              {seg.status === 'loading' ? 'Segmenting…' : seg.status === 'ok' ? 'Re-run Segmentation' : seg.status === 'error' ? 'Retry Segmentation' : 'Run Segmentation'}
            </button>
          </div>
          {seg.status === 'error' && (
            <div className="flex items-start justify-between gap-2 p-3 rounded-lg text-red-300 text-xs"
                 style={{ background: 'rgba(244, 63, 94, 0.06)', border: '1px solid rgba(244, 63, 94, 0.20)' }}>
              <div className="flex items-start gap-2">
                <AlertTriangle size={13} className="mt-0.5 shrink-0" />
                <div>
                  <p className="font-semibold">Segmentation failed</p>
                  <p className="text-red-300/80 mt-0.5">{seg.error}</p>
                </div>
              </div>
              <button
                onClick={runSeg}
                className="px-2 py-1 rounded bg-red-500/20 hover:bg-red-500/30 text-red-200 text-xs font-medium transition shrink-0"
              >
                Retry
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ── Section: Water Level (river / water quality) ──────────────────────────────

function WaterLevelSection({ section, loading }: { section: AssessmentSection | null; loading: boolean }) {
  if (loading) return <Skeleton lines={2} />;
  if (!section || section.status !== 'ok') return <SectionState status={section} fallback="Loading water level…" />;
  const data = (section.data ?? {}) as { river_level_m?: number | null; water_quality_index?: number | null };
  const isOverride = section.data_source === 'manual_override';
  return (
    <div className="grid grid-cols-2 gap-3">
      <div className="p-3 rounded-md" style={{ background: 'rgba(56, 189, 248, 0.06)', border: '1px solid rgba(56, 189, 248, 0.18)' }}>
        <div className="flex items-center justify-between text-[10px] uppercase tracking-wider text-white/50">
          <span className="flex items-center gap-1.5"><Droplets size={11} className="text-blue-300" /> River level</span>
          {isOverride && (
            <span className="text-[9px] font-mono font-bold text-amber-300 bg-amber-400/10 px-1.5 py-0.5 rounded border border-amber-400/30">
              Manual Override
            </span>
          )}
        </div>
        <p className="text-white text-xl font-mono mt-1">
          {data.river_level_m != null ? `${data.river_level_m.toFixed(2)} m` : '—'}
        </p>
      </div>
      <div className="p-3 rounded-md" style={{ background: 'rgba(45, 212, 191, 0.06)', border: '1px solid rgba(45, 212, 191, 0.18)' }}>
        <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-white/50">
          <Beaker size={11} className="text-teal-300" /> Water quality
        </div>
        <p className="text-white text-xl font-mono mt-1">
          {data.water_quality_index != null ? `${data.water_quality_index.toFixed(1)} / 100` : '—'}
        </p>
      </div>
    </div>
  );
}

// ── Section: Flood risk (compact) ─────────────────────────────────────────────

function FloodSection({ section, loading }: { section: AssessmentSection | null; loading: boolean }) {
  if (loading) return <Skeleton lines={2} />;
  if (!section || section.status !== 'ok') return <SectionState status={section} fallback="Loading flood risk…" />;
  const data = (section.data ?? {}) as {
    flood_probability?: number;
    flood_risk_level?: string;
    likely_severity_if_flood?: string;
  };
  const lvl = data.flood_risk_level ?? '—';
  const prob = data.flood_probability ?? 0;
  return (
    <div className="flex items-center gap-4">
      <div className="relative w-20 h-20">
        <svg viewBox="0 0 36 36" className="w-20 h-20 -rotate-90">
          <circle cx="18" cy="18" r="15" fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth="3" />
          <circle
            cx="18" cy="18" r="15" fill="none"
            stroke={riskTone(lvl)} strokeWidth="3"
            strokeDasharray={`${Math.min(prob, 1) * 94.2} 94.2`}
            strokeLinecap="round"
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center text-white font-mono text-sm">
          {(prob * 100).toFixed(0)}%
        </div>
      </div>
      <div className="flex-1 space-y-1.5">
        <div className="flex items-center justify-between">
          <span className="text-xs text-white/50">Flood probability</span>
          <span className="font-mono font-bold text-lg" style={{ color: riskTone(lvl) }}>
            {(prob * 100).toFixed(1)}%
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-xs text-white/50">Risk level</span>
          <span
            className="text-xs font-bold uppercase px-2 py-0.5 rounded-full border font-mono"
            style={{ color: riskTone(lvl), borderColor: riskTone(lvl) }}
          >
            {lvl}
          </span>
        </div>
        {data.likely_severity_if_flood && data.likely_severity_if_flood !== 'Minor' && (
          <div className="text-[10px] text-white/40">Severity hint: {data.likely_severity_if_flood}</div>
        )}
      </div>
    </div>
  );
}

// ── Section: Overall risk (composite) ──────────────────────────────────────────

function OverallRiskSection({ section, loading }: { section: AssessmentSection | null; loading: boolean }) {
  if (loading) return <Skeleton lines={3} />;
  if (!section || section.status !== 'ok') return <SectionState status={section} fallback="Loading overall risk…" />;
  const data = (section.data ?? {}) as {
    final_risk_level?: string;
    composite_score?: number;
    flood_severity?: string;
    predicted_outbreak_risk?: string;
  };
  const lvl = data.final_risk_level ?? '—';
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <span
          className="px-3 py-1 rounded-full text-sm font-bold uppercase border font-mono"
          style={{ color: riskTone(lvl), borderColor: riskTone(lvl) }}
        >
          {lvl}
        </span>
        {data.composite_score != null && (
          <span className="text-[10px] uppercase tracking-wider text-white/40">
            Composite score {data.composite_score.toFixed(2)}
          </span>
        )}
      </div>
      <div className="grid grid-cols-2 gap-2 text-[11px]">
        <div className="p-2 rounded-md" style={{ background: 'rgba(255,255,255,0.03)' }}>
          <p className="text-white/40">Flood severity</p>
          <p className="text-white font-semibold" style={{ color: riskTone(data.flood_severity) }}>{data.flood_severity ?? '—'}</p>
        </div>
        <div className="p-2 rounded-md" style={{ background: 'rgba(255,255,255,0.03)' }}>
          <p className="text-white/40">Outbreak risk</p>
          <p className="text-white font-semibold" style={{ color: riskTone(data.predicted_outbreak_risk) }}>{data.predicted_outbreak_risk ?? '—'}</p>
        </div>
      </div>
    </div>
  );
}

// ── Section: Recommendation (operational only) ────────────────────────────────

function RecommendationSection({ section, loading, isOperational }: {
  section: AssessmentSection | null | undefined; loading: boolean; isOperational: boolean;
}) {
  if (!isOperational) {
    return (
      <div className="flex items-start gap-2 p-3 rounded-lg text-white/55 text-xs"
           style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.06)' }}>
        <ShieldAlert size={13} className="mt-0.5 shrink-0" />
        <p>Operational content — sign in as a health worker, hospital, NGO, government, or admin to see recommendations.</p>
      </div>
    );
  }
  if (loading) return <Skeleton lines={3} />;
  if (!section || section.status !== 'ok') return <SectionState status={section ?? null} fallback="Loading recommendation…" />;
  const data = (section.data ?? {}) as {
    hospital_beds_available?: number;
    occupancy_percent?: number;
    recommendations?: string[];
  };
  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 gap-2 text-[11px]">
        <div className="p-2 rounded-md" style={{ background: 'rgba(56,189,248,0.06)' }}>
          <p className="text-white/40">Beds available</p>
          <p className="text-white font-mono font-semibold">{data.hospital_beds_available ?? '—'}</p>
        </div>
        <div className="p-2 rounded-md" style={{ background: 'rgba(56,189,248,0.06)' }}>
          <p className="text-white/40">Occupancy</p>
          <p className="text-white font-mono font-semibold">{data.occupancy_percent != null ? `${data.occupancy_percent.toFixed(1)}%` : '—'}</p>
        </div>
      </div>
      {data.recommendations && data.recommendations.length > 0 ? (
        <ul className="space-y-1.5 text-[12px] text-white/75 list-disc pl-4">
          {data.recommendations.map((r, i) => <li key={i}>{r}</li>)}
        </ul>
      ) : (
        <p className="text-white/50 text-xs">No specific recommendations.</p>
      )}
    </div>
  );
}

// ── Page-level "Last updated" + Re-run ────────────────────────────────────────

function HeaderStrip({
  district, generatedAt, isFetching, onRerun,
}: {
  district: string; generatedAt: string | null; isFetching: boolean; onRerun: () => void;
}) {
  return (
    <div className="flex items-center justify-between gap-3 flex-wrap mb-4">
      <div className="flex items-center gap-2 text-xs text-white/55">
        <CheckCircle2 size={13} className="text-emerald-300" />
        {generatedAt ? (
          <span>Last updated {new Date(generatedAt).toLocaleString()}</span>
        ) : isFetching ? (
          <span>Running assessment…</span>
        ) : (
          <span>No run yet</span>
        )}
      </div>
      <button
        onClick={onRerun}
        disabled={isFetching}
        className="px-3 py-1.5 rounded-lg text-xs font-semibold text-white/80 hover:text-white border border-white/10 flex items-center gap-1.5 transition disabled:opacity-50"
        style={{ background: 'rgba(255,255,255,0.04)' }}
      >
        <RefreshCw size={12} className={isFetching ? 'animate-spin' : ''} />
        Re-run
      </button>
    </div>
  );
}

// ── Main panel ────────────────────────────────────────────────────────────────

interface AssessmentPanelProps {
  district: string;
  initialRiverLevel?: number;
}

export default function AssessmentPanel({ district, initialRiverLevel }: AssessmentPanelProps) {
  const [riverLevel, setRiverLevel] = useState<number>(initialRiverLevel ?? 5.0);
  const [isOverridden, setIsOverridden] = useState<boolean>(initialRiverLevel != null);

  useEffect(() => {
    if (initialRiverLevel != null) {
      setRiverLevel(initialRiverLevel);
      setIsOverridden(true);
    }
  }, [initialRiverLevel]);

  // Single, district-scoped query.  Primitives only in the key.
  const query = useFullAssessmentV2(district, isOverridden ? riverLevel : null);
  const { data, isLoading, isError, isFetching, refetch, error } = query;

  // Defensive: if the user is mid-flip and the response is for a stale
  // district, do not render it.  The `district` prop is the source of
  // truth; data.district is what the server returned.
  const fresh = data && data.district === district ? data : null;
  const visibleLoading = isLoading || (isFetching && !fresh);

  return (
    <div>
      <HeaderStrip
        district={district}
        generatedAt={fresh?.generated_at ?? null}
        isFetching={isFetching}
        onRerun={() => refetch()}
      />

      {/* ── River Surge Simulation Scenario Bar ── */}
      <div className="mb-4 p-3 rounded-xl border border-white/10 bg-white/[0.03] backdrop-blur-md flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-cyan-500/10 border border-cyan-500/20 text-cyan-400">
            <Droplets size={16} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-white">River Surge Scenario</span>
              {isOverridden ? (
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold tracking-wide uppercase bg-amber-500/20 border border-amber-500/40 text-amber-300">
                  Simulated ({riverLevel.toFixed(1)}m)
                </span>
              ) : (
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold tracking-wide uppercase bg-emerald-500/20 border border-emerald-500/40 text-emerald-300">
                  Live Hydro Baseline
                </span>
              )}
            </div>
            <p className="text-[11px] text-white/50">
              {isOverridden
                ? 'All 5 ML models (Flood, Outbreak, Breakdown, Overall Risk, Directives) recalculating for this surge height.'
                : 'Using real-time telemetry from Bangladesh hydrometric stations.'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3 w-full sm:w-auto">
          <div className="flex items-center gap-2 flex-1 sm:w-48">
            <span className="text-[11px] text-white/40">0m</span>
            <input
              type="range"
              min={0}
              max={12}
              step={0.1}
              value={riverLevel}
              onChange={(e) => {
                setRiverLevel(parseFloat(e.target.value));
                setIsOverridden(true);
              }}
              className="w-full accent-cyan-400 cursor-pointer"
            />
            <span className="text-[11px] text-white/40">12m</span>
            <span className="text-xs font-mono font-bold text-cyan-300 min-w-[3rem] text-right">
              {riverLevel.toFixed(1)}m
            </span>
          </div>

          {isOverridden && (
            <button
              onClick={() => {
                setIsOverridden(false);
              }}
              className="px-2.5 py-1 text-[11px] font-medium rounded-lg bg-white/05 hover:bg-white/10 text-white/70 hover:text-white border border-white/10 transition"
              title="Reset to live river level telemetry"
            >
              Reset to live
            </button>
          )}
        </div>
      </div>

      {isError && !fresh && (
        <div className="p-4 rounded-xl border border-red-500/20 bg-red-500/5 text-red-300 text-sm flex items-start gap-2">
          <AlertTriangle size={14} className="mt-0.5 shrink-0" />
          <div>
            <p className="font-semibold">Couldn&apos;t reach the assessment service.</p>
            <p className="text-red-300/80 mt-0.5">{getApiErrorMessage(error)}</p>
            <button
              onClick={() => refetch()}
              className="mt-2 px-3 py-1.5 rounded-lg text-xs font-semibold text-white border border-white/10"
              style={{ background: 'rgba(255,255,255,0.04)' }}
            >
              Try again
            </button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <SectionBoundary name="flood">
          <GlassCard className="p-5">
            <SectionHeader
              icon={Activity}
              title="Flood risk"
              status={fresh?.flood ?? null}
            />
            <FloodSection section={fresh?.flood ?? null} loading={visibleLoading && !fresh} />
          </GlassCard>
        </SectionBoundary>

        <SectionBoundary name="water_level">
          <GlassCard className="p-5">
            <SectionHeader
              icon={Droplets}
              title="Water level"
              status={fresh?.water_level ?? null}
            />
            <WaterLevelSection section={fresh?.water_level ?? null} loading={visibleLoading && !fresh} />
          </GlassCard>
        </SectionBoundary>

        <SectionBoundary name="overall_risk">
          <GlassCard className="p-5">
            <SectionHeader
              icon={ShieldAlert}
              title="Overall risk level"
              status={fresh?.overall_risk ?? null}
            />
            <OverallRiskSection section={fresh?.overall_risk ?? null} loading={visibleLoading && !fresh} />
          </GlassCard>
        </SectionBoundary>

        <SectionBoundary name="disease_outbreak">
          <GlassCard className="p-5">
            <SectionHeader
              icon={Activity}
              title="Disease Outbreak Risk"
              status={fresh?.disease_outbreak ?? null}
            />
            <DiseaseOutbreakSection section={fresh?.disease_outbreak ?? null} loading={visibleLoading && !fresh} />
          </GlassCard>
        </SectionBoundary>

        <SectionBoundary name="disease_breakdown">
          <GlassCard className="p-5">
            <SectionHeader
              icon={Pill}
              title="Disease Breakdown"
              status={fresh?.disease_breakdown ?? null}
            />
            <DiseaseBreakdownSection section={fresh?.disease_breakdown ?? null} loading={visibleLoading && !fresh} />
          </GlassCard>
        </SectionBoundary>

        <SectionBoundary name="forecast">
          <GlassCard className="p-5">
            <SectionHeader
              icon={TrendingUp}
              title="7 / 14-day Forecast"
              status={fresh?.forecast ?? null}
            />
            <ForecastSection section={fresh?.forecast ?? null} loading={visibleLoading && !fresh} />
          </GlassCard>
        </SectionBoundary>

        <div className="md:col-span-2">
          <SectionBoundary name="satellite">
            <GlassCard className="p-5">
              <SectionHeader
                icon={SatelliteIcon}
                title="Satellite Flood Extent"
                status={fresh?.satellite_extent ?? null}
              />
              <SatelliteFloodSection
                district={district}
                satSection={fresh?.satellite_extent ?? null}
                loading={visibleLoading && !fresh}
              />
            </GlassCard>
          </SectionBoundary>
        </div>

        <div className="md:col-span-2">
          <SectionBoundary name="recommendation">
            <GlassCard className="p-5">
              <SectionHeader
                icon={Cloud}
                title="Recommendation"
                status={fresh?.recommendation ?? null}
              />
              <RecommendationSection
                section={fresh?.recommendation}
                loading={visibleLoading && !fresh}
                isOperational={Boolean(fresh?.is_operational)}
              />
            </GlassCard>
          </SectionBoundary>
        </div>
      </div>
    </div>
  );
}
