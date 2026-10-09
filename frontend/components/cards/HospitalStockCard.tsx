'use client';

import GlassCard from './GlassCard';
import type { RecommendationResponse } from '@/lib/types';
import { motion } from 'framer-motion';
import { Pill, Droplet, Syringe } from 'lucide-react';

interface HospitalStockCardProps {
  data: RecommendationResponse;
}

function MiniGauge({
  label,
  icon: Icon,
  value,
  color,
}: {
  label: string;
  icon: React.ElementType;
  value: number;
  color: string;
}) {
  return (
    <div className="flex flex-col items-center gap-2">
      {/* Vertical glass bar */}
      <div className="relative w-8 h-24 rounded-full bg-white/10 overflow-hidden border border-white/10">
        <motion.div
          className="absolute bottom-0 w-full rounded-full"
          style={{ backgroundColor: color }}
          initial={{ height: 0 }}
          animate={{ height: `${value}%` }}
          transition={{ duration: 1.2, ease: 'easeOut' }}
        />
      </div>
      <Icon size={14} style={{ color }} />
      <div className="text-center">
        <div className="font-mono text-xs font-bold" style={{ color }}>
          {value}%
        </div>
        <div className="text-white/40 text-[10px] leading-tight">{label}</div>
      </div>
    </div>
  );
}

export default function HospitalStockCard({ data }: HospitalStockCardProps) {
  // Parse recommendations text for resource mentions, or use heuristic from occupancy
  const occ = data.occupancy_percent;
  const orsLevel = Math.max(15, 100 - occ * 0.8);
  const ivLevel = Math.max(10, 100 - occ * 0.9);
  const abLevel = Math.max(20, 100 - occ * 0.7);

  const orsColor = orsLevel < 30 ? '#F43F5E' : orsLevel < 60 ? '#FBBF24' : '#2DD4BF';
  const ivColor = ivLevel < 30 ? '#F43F5E' : ivLevel < 60 ? '#FBBF24' : '#2DD4BF';
  const abColor = abLevel < 30 ? '#F43F5E' : abLevel < 60 ? '#FBBF24' : '#2DD4BF';

  return (
    <GlassCard className="p-6">
      <h3 className="text-sm font-semibold uppercase tracking-widest text-white/60 mb-5">
        Medical Supply Levels
      </h3>

      <div className="flex justify-around items-end">
        <MiniGauge label="ORS" icon={Droplet} value={Math.round(orsLevel)} color={orsColor} />
        <MiniGauge label="IV Fluids" icon={Syringe} value={Math.round(ivLevel)} color={ivColor} />
        <MiniGauge label="Antibiotics" icon={Pill} value={Math.round(abLevel)} color={abColor} />
      </div>

      <p className="text-xs text-white/30 mt-4 text-center">
        Estimated from hospital occupancy ({Math.round(occ)}%)
      </p>
    </GlassCard>
  );
}
