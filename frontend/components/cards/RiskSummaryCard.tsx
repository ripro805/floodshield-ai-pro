'use client';

import { motion, animate, useMotionValue, useTransform } from 'framer-motion';
import { useEffect } from 'react';
import dynamic from 'next/dynamic';
import GlassCard from './GlassCard';
import type { FloodPredictionResponse } from '@/lib/types';
import { RISK_COLORS, RISK_GLOW } from '@/lib/types';
import { Droplets, AlertTriangle, TrendingUp } from 'lucide-react';
import DistrictName from '@/components/common/DistrictName';

const RiskGaugeTube = dynamic(() => import('@/components/three/RiskGaugeTube'), { ssr: false });

function AnimatedNumber({ value, decimals = 1 }: { value: number; decimals?: number }) {
  const count = useMotionValue(0);
  const rounded = useTransform(count, (v) => v.toFixed(decimals));

  useEffect(() => {
    const controls = animate(count, value, { duration: 1.2, ease: 'easeOut' });
    return controls.stop;
  }, [value, count]);

  return <motion.span>{rounded}</motion.span>;
}

interface RiskSummaryCardProps {
  data: FloodPredictionResponse;
  loading?: boolean;
  /** Optional district name; rendered as a header with a Bangla subtitle. */
  district?: string | null;
}

const severityMap: Record<string, string> = {
  Minor: 'text-teal-400',
  Moderate: 'text-amber-400',
  Severe: 'text-red-400',
};

const riskLevelMap: Record<string, 'low' | 'medium' | 'high' | 'critical'> = {
  Low: 'low',
  Medium: 'medium',
  High: 'high',
  Critical: 'critical',
};

export default function RiskSummaryCard({ data, loading, district }: RiskSummaryCardProps) {
  const riskKey = data.flood_risk_level as keyof typeof RISK_COLORS;
  const color = RISK_COLORS[riskKey];
  const glow = RISK_GLOW[riskKey];
  const gaugeLevel = riskLevelMap[data.flood_risk_level] ?? 'low';

  if (loading) {
    return (
      <GlassCard className="p-6 animate-pulse">
        <div className="h-5 w-32 bg-white/10 rounded mb-4" />
        <div className="flex gap-6 items-center">
          <div className="w-16 h-40 bg-white/10 rounded-xl" />
          <div className="flex-1 space-y-3">
            <div className="h-8 w-24 bg-white/10 rounded" />
            <div className="h-4 w-40 bg-white/10 rounded" />
            <div className="h-4 w-32 bg-white/10 rounded" />
          </div>
        </div>
      </GlassCard>
    );
  }

  return (
    <GlassCard glowColor={glow.replace(')', ', 0.3)').replace('rgba', 'rgba')} className="p-6">
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        <Droplets size={18} className="text-blue-400" />
        <span className="text-sm font-semibold uppercase tracking-widest text-white/60">
          Flood Risk Assessment
        </span>
        {district && <DistrictName en={district} size="sm" layout="inline" />}
      </div>

      <div className="flex gap-6 items-center">
        {/* 3D Gauge */}
        <RiskGaugeTube
          value={data.flood_probability}
          riskLevel={gaugeLevel}
          label="Probability"
          height={150}
        />

        {/* Data panel */}
        <div className="flex-1 space-y-4">
          {/* Big probability */}
          <div>
            <div
              className="text-5xl font-black font-mono tabular-nums"
              style={{ color, textShadow: glow }}
            >
              <AnimatedNumber value={data.flood_probability * 100} decimals={1} />
              <span className="text-2xl">%</span>
            </div>
            <p className="text-xs text-white/40 mt-1 font-mono">flood probability</p>
          </div>

          {/* Risk level badge */}
          <div className="flex items-center gap-2">
            <span
              className="px-3 py-1 rounded-full text-xs font-bold uppercase tracking-widest border"
              style={{ color, borderColor: color, boxShadow: glow }}
            >
              {data.flood_risk_level}
            </span>
            <span className="text-white/40 text-xs">risk level</span>
          </div>

          {/* Severity */}
          <div className="flex items-center gap-2 text-sm">
            <AlertTriangle size={14} className={severityMap[data.likely_severity_if_flood]} />
            <span className="text-white/60">Severity if flood: </span>
            <span className={`font-semibold ${severityMap[data.likely_severity_if_flood]}`}>
              {data.likely_severity_if_flood}
            </span>
          </div>
        </div>
      </div>
    </GlassCard>
  );
}
