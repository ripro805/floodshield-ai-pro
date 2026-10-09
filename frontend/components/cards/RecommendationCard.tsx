'use client';

import GlassCard from './GlassCard';
import type { RecommendationResponse } from '@/lib/types';
import { CheckCircle2, BedDouble, Users } from 'lucide-react';
import { motion } from 'framer-motion';

interface RecommendationCardProps {
  data: RecommendationResponse;
}

export default function RecommendationCard({ data }: RecommendationCardProps) {
  const occupancyColor =
    data.occupancy_percent >= 90
      ? '#F43F5E'
      : data.occupancy_percent >= 70
      ? '#FB923C'
      : '#2DD4BF';

  return (
    <GlassCard className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-widest text-white/60">
          AI Recommendations — {data.district}
        </h3>
        <span
          className="text-xs font-mono px-2 py-0.5 rounded border"
          style={{
            color: occupancyColor,
            borderColor: occupancyColor,
          }}
        >
          {data.risk_level}
        </span>
      </div>

      {/* Hospital capacity */}
      <div className="space-y-2">
        <div className="flex items-center gap-2 text-sm text-white/70">
          <BedDouble size={15} className="text-blue-400" />
          <span>
            <span className="font-mono font-bold text-white">{data.hospital_beds_available}</span>{' '}
            beds available
          </span>
          <Users size={15} className="ml-auto text-white/40" />
          <span className="text-white/40">
            <span className="font-mono" style={{ color: occupancyColor }}>
              {data.occupancy_percent.toFixed(0)}%
            </span>{' '}
            occupancy
          </span>
        </div>
        {/* Occupancy bar */}
        <div className="w-full h-2 rounded-full bg-white/10 overflow-hidden">
          <motion.div
            className="h-full rounded-full"
            style={{ backgroundColor: occupancyColor }}
            initial={{ width: 0 }}
            animate={{ width: `${data.occupancy_percent}%` }}
            transition={{ duration: 1, ease: 'easeOut' }}
          />
        </div>
      </div>

      {/* Recommendations list */}
      <ul className="space-y-2">
        {data.recommendations.map((rec, i) => (
          <motion.li
            key={i}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.08 }}
            className="flex items-start gap-3 text-sm text-white/80"
          >
            <CheckCircle2 size={15} className="text-teal-400 mt-0.5 shrink-0" />
            <span>{rec}</span>
          </motion.li>
        ))}
      </ul>
    </GlassCard>
  );
}
