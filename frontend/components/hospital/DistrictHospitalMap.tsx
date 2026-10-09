'use client';

/**
 * DistrictHospitalMap -- SSR-safe map of every hospital in one
 * district, fit to the district's bounds.  Used on the
 * /dashboard/[district] page.
 */
import HospitalMapClient from './HospitalMapClient';
import GlassCard from '@/components/cards/GlassCard';
import { Map } from 'lucide-react';

export default function DistrictHospitalMap({ district }: { district: string }) {
  return (
    <GlassCard className="p-4">
      <div className="flex items-center justify-between mb-3 px-2">
        <h2 className="text-lg font-bold text-white flex items-center gap-2">
          <Map size={16} className="text-blue-300" /> Hospitals near {district}
        </h2>
        <p className="text-xs text-white/40">OpenStreetMap · Leaflet</p>
      </div>
      <HospitalMapClient mode="district" district={district} height={420} />
    </GlassCard>
  );
}
