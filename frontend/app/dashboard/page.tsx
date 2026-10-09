'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import dynamic from 'next/dynamic';
import { motion } from 'framer-motion';
import GlassCard from '@/components/cards/GlassCard';
import DistrictName from '@/components/common/DistrictName';
import {
  useDiseaseHotspots, useFloodPrediction, useWeather, useSatelliteDistricts,
  useSmsSubscription, useSubscribeSms, useUnsubscribeSms,
  useLocationSearch,
} from '@/hooks';
import { getApiErrorMessage } from '@/lib/api';
import { BANGLADESH_DISTRICTS, RISK_COLORS } from '@/lib/types';
import { Droplets, Wind, Thermometer, Search, AlertCircle, Loader2, MessageSquare } from 'lucide-react';

const DistrictRiskMap = dynamic(() => import('@/components/map/DistrictRiskMap'), { ssr: false });
const RiskGaugeTube = dynamic(() => import('@/components/three/RiskGaugeTube'), { ssr: false });

const cardVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: (i: number) => ({ opacity: 1, y: 0, transition: { delay: i * 0.08, duration: 0.4 } }),
};

export default function DashboardPage() {
  const router = useRouter();
  const [selectedDistrict, setSelectedDistrict] = useState('Feni');
  const mapRef = useRef<{ flyToDistrict: (name: string) => void; flyToCountry: () => void } | null>(null);
  const [riverLevel, setRiverLevel] = useState(5);
  const [riverLevelOverridden, setRiverLevelOverridden] = useState(false);
  const [phoneNumber, setPhoneNumber] = useState('');
  const [smsThreshold, setSmsThreshold] = useState<'Medium' | 'High' | 'Critical'>('High');
  const [locationQuery, setLocationQuery] = useState('');

  // Keep the URL in sync with the picked district so users can bookmark /
  // share a link straight to a specific district view of the dashboard.
  useEffect(() => {
    const url = new URL(window.location.href);
    if (url.searchParams.get('district') !== selectedDistrict) {
      url.searchParams.set('district', selectedDistrict);
      window.history.replaceState({}, '', url.toString());
    }
  }, [selectedDistrict]);

  // Callback ref for the map. next/dynamic wraps DistrictRiskMap in a
  // LoadableComponent that does NOT forward refs, so we can not use
  // `ref={mapRef}` on the JSX. Instead the map fires `onReady(handle)`
  // once it is mounted; we keep the latest handle in a ref so the
  // existing `mapRef.current?.flyToDistrict(...)` calls in the
  // district-select / location-search handlers still work unchanged.
  const handleMapReady = useCallback(
    (handle: { flyToDistrict: (name: string) => void; flyToCountry: () => void }) => {
      mapRef.current = handle;
    },
    []
  );

  const weatherQuery = useWeather(selectedDistrict);
  // Belt-and-braces: kick an initial flyTo once the dynamic-imported map
  // component has had a moment to register its ref.  The DistrictRiskMap's
  // own [selectedDistrict, geojsonReady] effect covers the common case; this
  // is just here for the very first paint when the ref is still null.
  useEffect(() => {
    const t = setTimeout(() => mapRef.current?.flyToDistrict(selectedDistrict), 400);
    return () => clearTimeout(t);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const floodMutation = useFloodPrediction();
  const satelliteDistrictsQuery = useSatelliteDistricts();
  const hotspotsQuery = useDiseaseHotspots();
  const smsQuery = useSmsSubscription();
  const subscribeSmsMutation = useSubscribeSms();
  const unsubscribeSmsMutation = useUnsubscribeSms();
  const locationSearchQuery = useLocationSearch(locationQuery);

  const handleQuickPredict = () => {
    // Reuse the values already loaded by the live-weather card so the backend
    // doesn't have to re-query OpenWeatherMap on every Check Flood Risk click.
    // Without this the request blocks for ~900 ms waiting on the upstream API.
    floodMutation.mutate({
      location: selectedDistrict,
      river_level_m: riverLevel,
      rainfall_mm: weather?.rainfall,
      temperature_c: weather?.temperature,
      humidity_percent: weather?.humidity,
      water_quality_index: weather?.water_quality_index,
      population_density: weather?.population_density,
      season: 'Monsoon',
    });
  };

  const weather = weatherQuery.data;
  const flood = floodMutation.data;

  // Auto-sync the river-level slider with the latest observed value for the
  // selected district, unless the user has manually dragged the slider since
  // they last picked a district. The slider still wins once the user touches
  // it (riverLevelOverridden flips true onChange).
  useEffect(() => {
    if (riverLevelOverridden) return;
    const observed = weather?.river_level_m;
    if (typeof observed === 'number' && Number.isFinite(observed)) {
      // Slider goes 0–15 m; clamp so an outlier reading can't push it off-range.
      const clamped = Math.min(15, Math.max(0, observed));
      setRiverLevel(Number(clamped.toFixed(2)));
    }
  }, [weather?.river_level_m, weatherQuery.dataUpdatedAt, selectedDistrict, riverLevelOverridden]);

  // Map API risk level string to RiskGaugeTube riskLevel variant
  const floodGaugeLevel = flood
    ? ({ Low: 'low', Medium: 'medium', High: 'high', Critical: 'critical' } as const)[
        flood.flood_risk_level as 'Low' | 'Medium' | 'High' | 'Critical'
      ] ?? 'low'
    : null;

  return (
    <div className="max-w-7xl mx-auto">
      <motion.div initial="hidden" animate="visible" className="space-y-6">
        {/* Header */}
        <motion.div custom={0} variants={cardVariants}>
          <h1 className="text-3xl font-black text-white" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
            District Risk Map
          </h1>
          <p className="text-white/50 mt-1">Click any district for a detailed AI assessment</p>
        </motion.div>

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          {/* Map — spans 2 cols */}
          <motion.div custom={1} variants={cardVariants} className="xl:col-span-2">
            <GlassCard className="overflow-hidden" style={{ height: 520 }}>
              <DistrictRiskMap
                onReady={handleMapReady}
                height="520px"
                selectedDistrict={selectedDistrict}
                onDistrictClick={(d) => {
                  setSelectedDistrict(d);
                  setRiverLevelOverridden(false);
                  router.push(`/dashboard/${encodeURIComponent(d)}`);
                }}
                districtRisks={
                  // Mark every district that has a satellite export; they appear
                  // with a teal 'Low' tint so users know imagery is available.
                  satelliteDistrictsQuery.data?.available_districts.map((d) => ({
                    district: d,
                    riskLevel: 'Low' as const,
                  })) ?? []
                }
				hotspotDistricts={hotspotsQuery.data?.districts ?? []}
              />
            </GlassCard>
          </motion.div>

          {/* Side panel */}
          <div className="flex flex-col gap-4">
            {/* District selector + quick predict */}
            <motion.div custom={2} variants={cardVariants}>
              <GlassCard className="p-5">
                <h2 className="text-sm font-semibold uppercase tracking-widest text-white/60 mb-4 flex items-center gap-2">
                  Quick Flood Check <DistrictName en={selectedDistrict} size="sm" layout="inline" />
                </h2>

                <div className="relative mb-3">
                  <label className="text-xs text-white/50 mb-1 block" htmlFor="location-search">Search district or upazila</label>
                  <div className="relative">
                    <Search size={14} className="absolute left-3 top-3 text-white/35" />
                    <input id="location-search" value={locationQuery} onChange={(event) => setLocationQuery(event.target.value)} placeholder="e.g. Feni Sadar" className="w-full pl-9 pr-3 py-2.5 rounded-xl text-sm text-white border border-white/10 bg-white/5 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400" />
                  </div>
                  {locationSearchQuery.data?.results.length ? <div className="absolute left-0 right-0 top-[4.5rem] z-20 rounded-xl border border-white/10 bg-[#0b1422] shadow-xl overflow-hidden">{locationSearchQuery.data.results.slice(0, 6).map((item) => <button key={`${item.kind}-${item.name}-${item.district}`} onClick={() => {
                    setSelectedDistrict(item.kind === 'district' ? item.name : item.district);
                    setLocationQuery(`${item.name}, ${item.district}`);
                    mapRef.current?.flyToDistrict(item.kind === 'district' ? item.name : item.district);
                  }} className="w-full text-left px-3 py-2 hover:bg-white/10 text-xs text-white/75"><span className="text-white">{item.name}</span><span className="text-white/35 ml-2">{item.kind} · {item.district}</span></button>)}</div> : null}
                </div>

                {/* District select */}
                <div className="mb-3">
                  <label className="text-xs text-white/50 mb-1 block" htmlFor="district-select">District</label>
                  <select
                    id="district-select"
                    value={selectedDistrict}
                    onChange={(e) => {
                      const next = e.target.value;
                      setSelectedDistrict(next);
                      // Allow the new district's live river-level reading to populate the slider again.
                      setRiverLevelOverridden(false);
                      mapRef.current?.flyToDistrict(next);
                    }}
                    className="w-full px-3 py-2.5 rounded-xl text-sm text-white border focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
                    style={{ background: 'rgba(255,255,255,0.05)', borderColor: 'rgba(255,255,255,0.1)' }}
                  >
                    {BANGLADESH_DISTRICTS.map((d) => (
                      <option key={d} value={d} style={{ background: '#060B14' }}>{d}</option>
                    ))}
                  </select>
                </div>

                {/* River level */}
                <div className="mb-4">
                  <label className="text-xs text-white/50 mb-1 flex justify-between" htmlFor="river-level">
                    <span>River Level (m)</span>
                    <span className="font-mono text-blue-400">{riverLevel.toFixed(1)} m</span>
                  </label>
                  <input
                    id="river-level"
                    type="range"
                    min={0}
                    max={15}
                    step={0.1}
                    value={riverLevel}
                    onChange={(e) => {
                      setRiverLevel(Number(e.target.value));
                      setRiverLevelOverridden(true);
                    }}
                    className="w-full accent-blue-400"
                  />
                  <p className="mt-1 text-[10px] text-white/40 flex items-center justify-between">
                    <span className="flex items-center gap-2">
                      <span>
                        {weather?.river_level_m != null
                          ? riverLevelOverridden
                            ? 'Manual override'
                            : 'Auto from latest observation'
                          : 'No observation — fallback default'}
                      </span>
                      {riverLevelOverridden && weather?.river_level_m != null && (
                        <button
                          type="button"
                          onClick={() => setRiverLevelOverridden(false)}
                          className="text-[10px] underline text-blue-300 hover:text-blue-200 transition-colors"
                          title="Re-sync the slider to the latest observed value"
                        >
                          Reset to live
                        </button>
                      )}
                    </span>
                    {weather?.district_conditions_date && (
                      <span>Observed {weather.district_conditions_date}</span>
                    )}
                  </p>
                </div>

                <button
                  onClick={handleQuickPredict}
                  disabled={floodMutation.isPending}
                  className="w-full py-2.5 rounded-xl font-semibold text-sm text-white flex items-center justify-center gap-2 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-300 disabled:opacity-60"
                  style={{ background: 'linear-gradient(135deg, #38BDF8, #2DD4BF)' }}
                >
                  {floodMutation.isPending ? <Loader2 size={15} className="animate-spin" /> : <Droplets size={15} />}
                  {floodMutation.isPending ? 'Predicting…' : 'Check Flood Risk'}
                </button>

                {/* Result */}
                {flood && floodGaugeLevel && (
                  <div className="mt-4 pt-4 border-t border-white/08">
                    <div className="mb-3 text-xs text-white/50 flex items-center gap-1.5">
                      Prediction for <DistrictName en={selectedDistrict} size="sm" layout="inline" />
                    </div>
                    {/* Gauge + text side by side */}
                    <div className="flex items-center gap-4">
                      <RiskGaugeTube
                        value={flood.flood_probability}
                        riskLevel={floodGaugeLevel}
                        size="sm"
                      />
                      <div className="flex-1 space-y-1.5">
                        <div className="flex items-center justify-between">
                          <span className="text-xs text-white/50">Flood probability</span>
                          <span
                            className="font-mono font-bold text-lg"
                            style={{ color: RISK_COLORS[flood.flood_risk_level as keyof typeof RISK_COLORS] }}
                          >
                            {(flood.flood_probability * 100).toFixed(1)}%
                          </span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-xs text-white/50">Risk level</span>
                          <span
                            className="text-xs font-bold uppercase px-2 py-0.5 rounded-full border font-mono"
                            style={{
                              color: RISK_COLORS[flood.flood_risk_level as keyof typeof RISK_COLORS],
                              borderColor: RISK_COLORS[flood.flood_risk_level as keyof typeof RISK_COLORS],
                            }}
                          >
                            {flood.flood_risk_level}
                          </span>
                        </div>
                      </div>
                    </div>
                    <button
                      onClick={() => router.push(`/dashboard/${encodeURIComponent(selectedDistrict)}`)}
                      className="mt-3 w-full py-2 rounded-lg text-xs font-semibold text-blue-400 border border-blue-400/30 hover:bg-blue-400/10 transition"
                    >
                      Full Assessment →
                    </button>
                    {flood.feature_importance?.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-white/08">
                        <p className="text-[10px] uppercase tracking-widest text-white/40 mb-2">Why this result</p>
                        <div className="space-y-1.5">
                          {flood.feature_importance.slice(0, 3).map((item) => (
                            <div key={item.feature} className="flex items-center gap-2 text-[11px]">
                              <span className="text-white/55 flex-1 truncate">{item.feature.replaceAll('_', ' ')}</span>
                              <div className="w-16 h-1.5 rounded bg-white/10 overflow-hidden">
                                <div className="h-full rounded bg-blue-400" style={{ width: `${Math.min(item.importance * 100, 100)}%` }} />
                              </div>
                              <span className="font-mono text-white/45 w-9 text-right">{(item.importance * 100).toFixed(0)}%</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {floodMutation.isError && (
                  <div className="mt-3 flex items-center gap-2 text-red-400 text-xs">
                    <AlertCircle size={13} />
                    {getApiErrorMessage(floodMutation.error)}
                  </div>
                )}
              </GlassCard>
            </motion.div>

            {/* Weather card */}
            <motion.div custom={3} variants={cardVariants}>
              <GlassCard className="p-5">
                <h2 className="text-sm font-semibold uppercase tracking-widest text-white/60 mb-3 flex items-center gap-2">
                  Live Weather — <DistrictName en={selectedDistrict} size="sm" layout="inline" />
                </h2>
                {weatherQuery.isLoading && (
                  <div className="space-y-2 animate-pulse">
                    {[...Array(3)].map((_, i) => <div key={i} className="h-4 rounded bg-white/08 w-3/4" />)}
                  </div>
                )}
                {weather && (
                  <div className="space-y-2.5">
                    {weather.data_source === 'fallback' && (
                      <div className="flex items-center gap-1.5 text-xs text-amber-400 bg-amber-400/10 border border-amber-400/20 rounded-lg px-3 py-2">
                        <AlertCircle size={12} />
                        Estimated — live weather unavailable
                      </div>
                    )}
                    <div className="flex items-center justify-between text-sm">
                      <div className="flex items-center gap-2 text-white/60"><Thermometer size={14} /> Temperature</div>
                      <span className="font-mono text-white">{weather.temperature}°C</span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <div className="flex items-center gap-2 text-white/60"><Droplets size={14} /> Humidity</div>
                      <span className="font-mono text-white">{weather.humidity}%</span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <div className="flex items-center gap-2 text-white/60"><Wind size={14} /> Wind</div>
                      <span className="font-mono text-white">{weather.wind_speed} km/h</span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <div className="flex items-center gap-2 text-white/60"><Droplets size={14} /> Rainfall</div>
                      <span className="font-mono text-white">{weather.rainfall} mm</span>
                    </div>
                    <p className="text-white/30 text-xs capitalize">{weather.condition}</p>
                  </div>
                )}
              </GlassCard>
            </motion.div>

            {/* Dedicated river and water-quality monitoring */}
            <motion.div custom={4} variants={cardVariants}>
              <GlassCard className="p-5">
                <h2 className="text-sm font-semibold uppercase tracking-widest text-white/60 mb-3">
                  Environmental Monitoring
                </h2>
                {weather ? (
                  <div className="grid grid-cols-2 gap-3">
                    <div className="rounded-xl border border-blue-400/15 bg-blue-400/5 p-3">
                      <div className="text-xs text-white/45 mb-1">River level</div>
                      <div className="font-mono text-xl text-blue-300">
                        {weather.river_level_m != null ? `${weather.river_level_m.toFixed(2)} m` : 'Unavailable'}
                      </div>
                    </div>
                    <div className="rounded-xl border border-teal-400/15 bg-teal-400/5 p-3">
                      <div className="text-xs text-white/45 mb-1">Water quality</div>
                      <div className="font-mono text-xl text-teal-300">
                        {weather.water_quality_index != null ? `${weather.water_quality_index.toFixed(1)} / 100` : 'Unavailable'}
                      </div>
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-white/40">Loading district monitoring data…</p>
                )}
                {weather?.district_conditions_date && (
                  <p className="text-[10px] text-white/30 mt-3">Observed conditions: {weather.district_conditions_date}</p>
                )}
              </GlassCard>
            </motion.div>

            {/* SMS alerts */}
            <motion.div custom={5} variants={cardVariants}>
              <GlassCard className="p-5">
                <div className="flex items-center gap-2 mb-3">
                  <MessageSquare size={16} className="text-teal-400" />
                  <h2 className="text-sm font-semibold uppercase tracking-widest text-white/60">SMS Risk Alerts</h2>
                </div>
                {smsQuery.data?.is_active ? (
                  <div className="space-y-3">
                    <p className="text-xs text-white/55">Alerts for <span className="font-mono text-white">{smsQuery.data.phone_number}</span> when {smsQuery.data.risk_threshold.toLowerCase()} risk is reached.</p>
                    <button
                      onClick={() => unsubscribeSmsMutation.mutate()}
                      disabled={unsubscribeSmsMutation.isPending}
                      className="text-xs text-red-300 border border-red-300/25 rounded-lg px-3 py-2 hover:bg-red-300/10 transition disabled:opacity-50"
                    >
                      {unsubscribeSmsMutation.isPending ? 'Updating…' : 'Unsubscribe'}
                    </button>
                  </div>
                ) : (
                  <div className="space-y-2.5">
                    <input
                      value={phoneNumber}
                      onChange={(e) => setPhoneNumber(e.target.value)}
                      placeholder="+8801XXXXXXXXX"
                      aria-label="SMS phone number"
                      className="w-full px-3 py-2 rounded-lg text-sm text-white border border-white/10 bg-white/5 focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-400"
                    />
                    <div className="flex gap-2">
                      <select
                        value={smsThreshold}
                        onChange={(e) => setSmsThreshold(e.target.value as typeof smsThreshold)}
                        aria-label="SMS risk threshold"
                        className="flex-1 px-3 py-2 rounded-lg text-sm text-white border border-white/10 bg-white/5"
                      >
                        <option value="Medium" style={{ background: '#060B14' }}>Medium+</option>
                        <option value="High" style={{ background: '#060B14' }}>High+</option>
                        <option value="Critical" style={{ background: '#060B14' }}>Critical only</option>
                      </select>
                      <button
                        onClick={() => subscribeSmsMutation.mutate({ phone_number: phoneNumber, district: selectedDistrict, risk_threshold: smsThreshold }, { onSuccess: () => smsQuery.refetch() })}
                        disabled={!phoneNumber.trim() || subscribeSmsMutation.isPending}
                        className="px-3 py-2 rounded-lg text-xs font-semibold text-white transition disabled:opacity-50"
                        style={{ background: 'linear-gradient(135deg, #38BDF8, #2DD4BF)' }}
                      >
                        {subscribeSmsMutation.isPending ? 'Saving…' : 'Subscribe'}
                      </button>
                    </div>
                    {subscribeSmsMutation.isError && <p className="text-xs text-red-300">Could not save SMS subscription.</p>}
                    <p className="text-[10px] text-white/30">Provider delivery requires Twilio configuration on the backend.</p>
                  </div>
                )}
              </GlassCard>
            </motion.div>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
