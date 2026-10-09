'use client';

import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import GlassCard from '@/components/cards/GlassCard';
import { postRiskScore } from '@/lib/api';
import type { RiskScoreResponse } from '@/lib/types';
import { RISK_COLORS, RISK_GLOW } from '@/lib/types';
import { Bell, AlertTriangle, Clock, RefreshCw } from 'lucide-react';

// High-priority districts to monitor
const MONITOR_DISTRICTS = [
  { name: 'Feni', river_level_m: 8.5 },
  { name: 'Sylhet', river_level_m: 7.2 },
  { name: 'Sunamganj', river_level_m: 6.8 },
  { name: 'Netrokona', river_level_m: 5.5 },
  { name: 'Noakhali', river_level_m: 4.9 },
  { name: 'Jamalpur', river_level_m: 6.1 },
];

const SHARED_PARAMS = {
  flood_depth_cm: 40,
  population_density: 1800,
  sanitation_score: 0.35,
  water_quality_index: 52,
  previous_week_cases: 150,
  previous_two_week_cases: 130,
  season: 'Monsoon' as const,
};

interface AlertItemProps {
  district: string;
  risk: string;
  score: number;
  index: number;
}

function AlertItem({ district, risk, score, index }: AlertItemProps) {
  const color = RISK_COLORS[risk as keyof typeof RISK_COLORS];
  const glow = RISK_GLOW[risk as keyof typeof RISK_GLOW];
  const isCritical = risk === 'Critical';

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.07 }}
    >
      <GlassCard
        glowColor={glow?.replace(')', ', 0.2)')}
        className="p-4 flex items-center gap-4"
        style={isCritical ? { borderColor: 'rgba(244,63,94,0.3)' } : {}}
      >
        {/* Pulsing ring for critical */}
        <div className="relative shrink-0">
          <div
            className="w-10 h-10 rounded-full flex items-center justify-center"
            style={{ background: `${color}18` }}
          >
            <AlertTriangle size={16} style={{ color }} />
          </div>
          {isCritical && (
            <span
              className="absolute inset-0 rounded-full animate-ping opacity-30"
              style={{ background: color }}
            />
          )}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-white truncate">{district}</span>
            <span
              className="text-xs font-bold uppercase px-2 py-0.5 rounded-full border font-mono shrink-0"
              style={{ color, borderColor: color }}
            >
              {risk}
            </span>
          </div>
          <p className="text-xs text-white/40 mt-0.5">
            Composite score: <span className="font-mono" style={{ color }}>{score.toFixed(0)}/100</span>
          </p>
        </div>

        <div className="flex items-center gap-1 text-xs text-white/30 shrink-0">
          <Clock size={11} />
          Live
        </div>
      </GlassCard>
    </motion.div>
  );
}

export default function AlertsPage() {
  const [results, setResults] = useState<Record<string, RiskScoreResponse>>({});
  const [isRefreshing, setIsRefreshing] = useState(false);

  const runAssessments = async () => {
    setIsRefreshing(true);
    try {
      const entries = await Promise.all(MONITOR_DISTRICTS.map(async (district) => {
        const result = await postRiskScore({
        location: district.name,
        river_level_m: district.river_level_m,
        ...SHARED_PARAMS,
        });
        return [district.name, result] as const;
      }));
      setResults(Object.fromEntries(entries));
    } finally {
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    runAssessments();
    const interval = setInterval(() => { void runAssessments(); }, 30_000); // poll every 30s
    return () => clearInterval(interval);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const alerts = MONITOR_DISTRICTS.map((d) => ({
    district: d.name,
    data: results[d.name],
  }))
    .filter((a) => a.data)
    .sort((a, b) => {
      const order = { Critical: 0, High: 1, Medium: 2, Low: 3 };
      return (order[a.data!.final_risk_level as keyof typeof order] ?? 4) - (order[b.data!.final_risk_level as keyof typeof order] ?? 4);
    });

  const criticalCount = alerts.filter((a) => a.data?.final_risk_level === 'Critical').length;
  const highCount = alerts.filter((a) => a.data?.final_risk_level === 'High').length;

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-black text-white" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
            Live Alerts
          </h1>
          <p className="text-white/50 mt-1">Monitoring {MONITOR_DISTRICTS.length} high-risk districts · refreshes every 30s</p>
        </div>
        <button
          onClick={runAssessments}
          className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm text-white/60 border border-white/10 hover:text-white hover:border-white/20 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
        >
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {/* Summary badges */}
      {alerts.length > 0 && (
        <div className="flex gap-3 flex-wrap">
          {criticalCount > 0 && (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full border border-red-400/30 bg-red-400/08 text-red-400 text-xs font-semibold">
              <span className="w-2 h-2 rounded-full bg-red-400 animate-pulse" />
              {criticalCount} Critical
            </div>
          )}
          {highCount > 0 && (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full border border-orange-400/30 bg-orange-400/08 text-orange-400 text-xs font-semibold">
              {highCount} High
            </div>
          )}
        </div>
      )}

      {/* Loading skeletons */}
      {isRefreshing && alerts.length === 0 && (
        <div className="space-y-3">
          {MONITOR_DISTRICTS.map((_, i) => (
            <GlassCard key={i} className="p-4 h-16 animate-pulse">
              <div />
            </GlassCard>
          ))}
        </div>
      )}

      {/* Alert list */}
      <AnimatePresence>
        <div className="space-y-3">
          {alerts.map((a, i) => (
            <AlertItem
              key={a.district}
              district={a.district}
              risk={a.data!.final_risk_level}
              score={a.data!.composite_score}
              index={i}
            />
          ))}
        </div>
      </AnimatePresence>

      {alerts.length === 0 && !isRefreshing && (
        <GlassCard className="p-12 text-center">
          <Bell size={36} className="text-white/20 mx-auto mb-3" />
          <p className="text-white/50">No alert data yet — run assessments or wait for auto-refresh</p>
        </GlassCard>
      )}
    </div>
  );
}
