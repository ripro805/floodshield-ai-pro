'use client';

/**
 * /dashboard/[district] -- the per-district dashboard.
 *
 * Composes the existing Model 1 (flood), Model 2 (disease), Model 3
 * (forecast), Model 5 (risk), weather, and weekly-history cards on
 * top of a District Name header.  Adds:
 *   - A "Nearest hospitals" card backed by the new /hospitals/nearby
 *     endpoint.
 *   - An embedded OpenStreetMap (Leaflet) showing this district's
 *     facilities.
 *   - A "View Directory" CTA that deep-links into the new
 *     /dashboard/resources Directory tab for this district.
 *
 * The path param is a canonical 64-district name; we validate against
 * `BANGLADESH_DISTRICTS` and 404 the page (well, "not found" empty
 * state) on any misspell so the chatbot's `select_district` action
 * (which may emit legacy spellings like "Cumilla" -- normalised by
 * the backend, but not by the URL) gets a useful UI instead of a
 * raw 500.
 */
import { useMemo, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { motion } from 'framer-motion';
import {
  Building2, Loader2, AlertCircle, Map as MapIcon,
  TrendingUp, Activity, Calendar, Droplets, Wind,
  Inbox, CheckCircle2, Clock, XCircle,
} from 'lucide-react';
import GlassCard from '@/components/cards/GlassCard';
import DistrictName from '@/components/common/DistrictName';
import DistrictNearestHospitals from '@/components/hospital/DistrictNearestHospitals';
import DistrictHospitalMap from '@/components/hospital/DistrictHospitalMap';
import AssessmentPanel from '@/components/assessment/AssessmentPanel';
import { useAuth } from '@/lib/auth';



import {
  useWeather, useWeeklyHistory, useDiseaseHotspots,
  useDistrictHospitalIssueRollup,
} from '@/hooks';
import { getApiErrorMessage } from '@/lib/api';
import { BANGLADESH_DISTRICTS } from '@/lib/types';

// Animations shared with the rest of the dashboard pages
const cardVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: (i: number) => ({
    opacity: 1, y: 0,
    transition: { delay: i * 0.06, duration: 0.4 },
  }),
};

interface PageProps {
  params: { district: string };
}

type PullTab = 'overview' | 'history' | 'weather';

export default function DistrictDashboardPage({ params }: PageProps) {
  const searchParams = useSearchParams();
  const riverLevelParam = searchParams.get('river_level');
  const riverLevelOverride = riverLevelParam && !isNaN(parseFloat(riverLevelParam)) ? parseFloat(riverLevelParam) : undefined;

  // URL param -- allow any case and the legacy alias "Cumilla" /
  // "Comilla" / etc.; we don't want to 404 the user just because the
  // chatbot's `select_district` happened to emit a legacy spelling.
  const rawDistrict = (params.district || '').trim();
  const district = useMemo(() => {
    const k = rawDistrict.toLowerCase();
    return (
      BANGLADESH_DISTRICTS.find((d) => d.toLowerCase() === k) ||
      BANGLADESH_DISTRICTS.find(
        (d) => d.toLowerCase().replace(/[^a-z]/g, '') === k.replace(/[^a-z]/g, '')
      ) ||
      rawDistrict
    );
  }, [rawDistrict]);

  // Treat any URL spelling we can't canonicalise as a not-found.
  const isKnown = BANGLADESH_DISTRICTS.includes(district);

  const [tab, setTab] = useState<PullTab>('overview');
  const { user } = useAuth();

  // ─── Pull-on-mount queries ────────────────────────────────────────────
  const weather = useWeather(isKnown ? district : null);
  const issueRollup = useDistrictHospitalIssueRollup(isKnown ? district : null);
  const history = useWeeklyHistory(isKnown ? district : null);
  const hotspots = useDiseaseHotspots();

  if (!isKnown) {
    return (
      <div className="min-h-screen px-4 sm:px-6 py-10 max-w-3xl mx-auto">
        <GlassCard className="p-8 text-center">
          <AlertCircle size={40} className="text-red-400 mx-auto mb-3" />
          <h1 className="text-2xl font-bold text-white mb-2">Unknown district</h1>
          <p className="text-white/60 text-sm">
            &ldquo;{rawDistrict}&rdquo; is not one of the 64 Bangladesh districts we cover.
            Pick a district from the dropdown to continue.
          </p>
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-2 mt-4 px-4 py-2 rounded-xl text-sm font-semibold text-white"
            style={{ background: 'linear-gradient(135deg, #38BDF8, #2DD4BF)' }}
          >
            Open the dashboard
          </Link>
        </GlassCard>
      </div>
    );
  }

  return (
    <div className="min-h-screen px-4 sm:px-6 py-6 max-w-6xl mx-auto">
      {/* ── Header ── */}
      <motion.div
        custom={0} variants={cardVariants} initial="hidden" animate="visible"
        className="mb-6 flex flex-col md:flex-row md:items-end md:justify-between gap-4"
      >
        <div>
          <Link href="/dashboard" className="text-xs text-white/50 hover:text-white mb-2 inline-block">
            ← All districts
          </Link>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center"
                 style={{ background: 'linear-gradient(135deg, #38BDF8, #2DD4BF)' }}>
              <MapIcon size={18} className="text-white" />
            </div>
            <div>
              <DistrictName en={district} size="lg" />
              <p className="text-white/40 text-sm mt-0.5">District dashboard · Bangladesh</p>
            </div>
          </div>
        </div>

        {/* Deep-link to the new Directory tab for this district */}
        <div className="flex flex-wrap gap-2">
          <Link
            href={`/dashboard/resources?tab=directory&district=${encodeURIComponent(district)}`}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold text-white"
            style={{ background: 'linear-gradient(135deg, #38BDF8, #2DD4BF)' }}
          >
            <Building2 size={14} /> View Directory
          </Link>
          <Link
            href="/dashboard/resources?tab=inventory"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold text-white/80 hover:text-white border border-white/10"
            style={{ background: 'rgba(255,255,255,0.04)' }}
          >
            <Activity size={14} /> Hospital inventory
          </Link>
        </div>
      </motion.div>

      {/* ── Quick stats row (always-on, from the cheap endpoints) ── */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-5">
        <QuickStat
          icon={Droplets}
          label="Humidity"
          value={
            weather.data
              ? `${Math.round(weather.data.humidity ?? 0)}%`
              : weather.isLoading ? '…' : '—'
          }
          tone="#7DD3FC"
          index={1}
        />
        <QuickStat
          icon={TrendingUp}
          label="River level"
          value={
            riverLevelOverride !== undefined
              ? `${riverLevelOverride.toFixed(2)} m (Simulation)`
              : weather.data
                ? `${(weather.data.river_level_m ?? 0).toFixed(2)} m`
                : weather.isLoading ? '…' : '—'
          }
          tone="#5EEAD4"
          index={2}
        />
        <QuickStat
          icon={Wind}
          label="Wind"
          value={
            weather.data
              ? `${Math.round(weather.data.wind_speed ?? 0)} km/h`
              : weather.isLoading ? '…' : '—'
          }
          tone="#FCD34D"
          index={3}
        />
        <QuickStat
          icon={Calendar}
          label="Weeks of history"
          value={
            history.data
              ? `${history.data.weeks?.length ?? 0}`
              : history.isLoading ? '…' : history.isError ? '0' : '—'
          }
          tone="#FDA4AF"
          index={4}
        />
      

        <QuickStat
          icon={Inbox}
          label="Hospital issues"
          value={
            issueRollup.isLoading ? '…'
              : issueRollup.data
                ? `${issueRollup.data.open + issueRollup.data.ack} open · ${issueRollup.data.resolved} resolved`
                : '—'
          }
          tone={issueRollup.data && (issueRollup.data.open + issueRollup.data.ack) > 0 ? '#F59E0B' : '#34D399'}
          index={5}
        />
</div>

      {/* ── Full Assessment (auto-runs on mount, supports river level override) ── */}
      <AssessmentPanel district={district} initialRiverLevel={riverLevelOverride} />


      {/* ── Pull-on-mount tab strip ── */}
      <div className="flex items-center gap-2 mb-5 p-1 rounded-xl border"
           style={{ background: 'rgba(255,255,255,0.04)', borderColor: 'rgba(255,255,255,0.08)' }}>
        {(['overview', 'history', 'weather'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex-1 px-3 py-2 rounded-lg text-sm font-semibold transition ${
              tab === t ? 'bg-blue-500/20 text-blue-200' : 'text-white/60 hover:text-white'
            }`}
          >
            {t === 'overview' ? 'Live snapshot' : t === 'history' ? '8-week history' : 'Live weather'}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        {/* Live snapshot card -- hotspots (national) + role-aware tips */}
        {tab === 'overview' && (
          <motion.div
            key="overview" custom={5} variants={cardVariants} initial="hidden" animate="visible"
            className="lg:col-span-2"
          >
            <GlassCard className="p-6 h-full">
              <h2 className="text-lg font-bold text-white mb-3 flex items-center gap-2">
                <Activity size={16} className="text-blue-300" /> Live snapshot — {district}
              </h2>
              {hotspots.isLoading && (
                <div className="flex items-center gap-2 text-white/60 text-sm py-6 justify-center">
                  <Loader2 className="animate-spin" size={14} /> Loading national hotspots…
                </div>
              )}
              {hotspots.isError && (
                <p className="text-amber-300 text-sm flex items-center gap-1">
                  <AlertCircle size={12} /> {getApiErrorMessage(hotspots.error)}
                </p>
              )}
              {hotspots.data && (
                <div className="space-y-2">
                  {hotspots.data.districts
                    ?.filter((d: any) => d.district === district)
                    .slice(0, 3)
                    .map((d: any, i: number) => (
                      <div key={i} className="flex items-center justify-between p-3 rounded-lg" style={{ background: 'rgba(255,255,255,0.04)' }}>
                        <div>
                          <p className="text-white text-sm font-semibold">
                            Cluster {d.cluster_id} {d.is_noise ? '(noise)' : ''}
                          </p>
                          <p className="text-white/40 text-xs">
                            Flood depth {(d.flood_depth_cm ?? 0).toFixed(1)} cm · WQI {(d.water_quality_index ?? 0).toFixed(2)}
                          </p>
                        </div>
                        <div className="text-right">
                          <p className="text-white text-sm font-mono">{(d.signal_score ?? 0).toFixed(2)}</p>
                          <p className="text-white/40 text-[10px]">signal</p>
                        </div>
                      </div>
                    ))}
                  {hotspots.data.districts?.filter((d: any) => d.district === district).length === 0 && (
                    <p className="text-white/50 text-sm">No active hotspots flagged for {district} right now.</p>
                  )}
                </div>
              )}
            </GlassCard>
          </motion.div>
        )}

        {tab === 'history' && (
          <motion.div
            key="history" custom={5} variants={cardVariants} initial="hidden" animate="visible"
            className="lg:col-span-2"
          >
            <GlassCard className="p-6 h-full">
              <h2 className="text-lg font-bold text-white mb-3 flex items-center gap-2">
                <Calendar size={16} className="text-blue-300" /> 8-week history — {district}
              </h2>
              {history.isLoading && (
                <div className="flex items-center gap-2 text-white/60 text-sm py-6 justify-center">
                  <Loader2 className="animate-spin" size={14} /> Loading…
                </div>
              )}
              {history.isError && (
                <p className="text-amber-300 text-sm flex items-center gap-1">
                  <AlertCircle size={12} /> No history rows yet.  The dashboard works without it, but the LSTM forecast will be disabled.
                </p>
              )}
              {history.data && history.data.weeks && (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  {history.data.weeks.map((w: any, i: number) => (
                    <div key={i} className="p-2 rounded-lg" style={{ background: 'rgba(255,255,255,0.04)' }}>
                      <p className="text-white/40 text-[10px] uppercase tracking-wider">
                        {w.week_ending ?? `W${i + 1}`}
                      </p>
                      <p className="text-white text-sm font-semibold">
                        {w.rainfall_mm?.toFixed(1) ?? '—'} mm
                      </p>
                      <p className="text-white/40 text-[10px]">
                        {(w.flood_depth_cm ?? 0).toFixed(0)} cm · {(w.sanitation_score ?? 0).toFixed(2)}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </GlassCard>
          </motion.div>
        )}

        {tab === 'weather' && (
          <motion.div
            key="weather" custom={5} variants={cardVariants} initial="hidden" animate="visible"
            className="lg:col-span-2"
          >
            <GlassCard className="p-6 h-full">
              <h2 className="text-lg font-bold text-white mb-3 flex items-center gap-2">
                <Wind size={16} className="text-blue-300" /> Live weather — {district}
              </h2>
              {weather.isLoading && (
                <div className="flex items-center gap-2 text-white/60 text-sm py-6 justify-center">
                  <Loader2 className="animate-spin" size={14} /> Loading…
                </div>
              )}
              {weather.isError && (
                <p className="text-amber-300 text-sm flex items-center gap-1">
                  <AlertCircle size={12} /> {getApiErrorMessage(weather.error)}
                </p>
              )}
              {weather.data && (
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  {[
                    ['Temperature', `${(weather.data.temperature ?? 0).toFixed(1)}°C`],
                    ['Humidity', `${Math.round(weather.data.humidity ?? 0)}%`],
                    ['Rainfall (1h)', `${(weather.data.rainfall ?? 0).toFixed(1)} mm`],
                    ['Wind', `${Math.round(weather.data.wind_speed ?? 0)} km/h`],
                    ['River level', `${(weather.data.river_level_m ?? 0).toFixed(2)} m`],
                    ['Pressure', `—`],
                  ].map(([k, v]) => (
                    <div key={k as string} className="p-3 rounded-lg" style={{ background: 'rgba(255,255,255,0.04)' }}>
                      <p className="text-white/40 text-[10px] uppercase tracking-wider">{k}</p>
                      <p className="text-white text-sm font-mono mt-0.5">{v}</p>
                    </div>
                  ))}
                </div>
              )}
            </GlassCard>
          </motion.div>
        )}

        {/* Right column: hospital resources side */}
        <div className="space-y-4">
          <motion.div
            custom={6} variants={cardVariants} initial="hidden" animate="visible"
          >
            <DistrictNearestHospitals district={district} />
          </motion.div>

          <motion.div
            custom={7} variants={cardVariants} initial="hidden" animate="visible"
            className="text-[10px] text-white/40 text-center"
          >
            Logged in as <span className="text-white/60">{user?.role ?? 'guest'}</span> ·{' '}
            <Link href="/dashboard" className="hover:text-white underline">change district</Link>
          </motion.div>
        </div>
      </div>

      {/* ── Embedded map (the new B view lives here too) ── */}
      <motion.div
        custom={8} variants={cardVariants} initial="hidden" animate="visible"
        className="mb-6"
      >
        <DistrictHospitalMap district={district} />
      </motion.div>
    </div>
  );
}

function QuickStat({
  icon: Icon, label, value, tone, index,
}: {
  icon: any; label: string; value: string; tone: string; index: number;
}) {
  return (
    <motion.div
      custom={index} variants={cardVariants} initial="hidden" animate="visible"
    >
      <GlassCard className="p-3 flex items-center gap-2">
        <div className="w-9 h-9 rounded-lg flex items-center justify-center"
             style={{ background: 'rgba(255,255,255,0.06)' }}>
          <Icon size={16} style={{ color: tone }} />
        </div>
        <div className="min-w-0">
          <p className="text-[10px] uppercase tracking-wider text-white/40">{label}</p>
          <p className="text-white text-sm font-mono truncate">{value}</p>
        </div>
      </GlassCard>
    </motion.div>
  );
}
