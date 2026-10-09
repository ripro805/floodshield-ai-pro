'use client';

/**
 * SSR-safe Leaflet wrapper.  Leaflet uses `window` at import time,
 * so any module that imports it directly will crash Next.js's
 * server render.  This file is the only thing consumers should
 * import -- it defers the actual Leaflet import to the client.
 */
import dynamic from 'next/dynamic';
import type { HospitalMapProps } from './HospitalMap';

const HospitalMap = dynamic(() => import('./HospitalMap'), {
  ssr: false,
  loading: () => (
    <div
      className="w-full rounded-2xl flex items-center justify-center text-white/50 text-sm"
      style={{ background: '#0b1320', minHeight: 280 }}
    >
      Loading map…
    </div>
  ),
});

export default function HospitalMapClient(props: HospitalMapProps) {
  return <HospitalMap {...props} />;
}
