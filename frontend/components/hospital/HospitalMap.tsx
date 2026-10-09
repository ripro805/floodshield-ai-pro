'use client';

/**
 * HospitalMap -- a Leaflet + OpenStreetMap component for the Hospital
 * Directory.  Used in two places:
 *
 *  1. The District Detail page (`/dashboard/[district]`) -- with
 *     mode="district" to show one district's hospitals, fit to bbox.
 *  2. The Directory Nearby view -- with mode="nearby" to drop a "you
 *     are here" pin and the N nearest hospitals.
 *
 * Why a custom map (vs. reusing `DistrictRiskMap`)?
 *   - The risk map's reason for existing is the GeoJSON polygon
 *     overlay.  This component is much smaller and only shows
 *     hospital markers (with a darker user pin in nearby mode).
 *   - We never want a district polygon here, so the surface area is
 *     tiny and the page can ship without dragging in the
 *     bangladesh.geojson fetch.
 *
 * SSR
 * ---
 * Leaflet calls `window` at import time, so this module is always
 * loaded via `next/dynamic({ ssr: false })`.  See the two wrapper
 * components `DistrictHospitalMap` and `DirectoryMap` that the
 * consumers import.
 */
import { useEffect, useRef, useState } from 'react';
import { Loader2, AlertCircle } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { getHospitals, getNearbyHospitals } from '@/lib/api';
import type { HospitalPublic, NearbyHospital } from '@/lib/types';

export interface HospitalMapProps {
  mode: 'district' | 'nearby' | 'national';
  /** Required when mode='district'. */
  district?: string;
  /** Required when mode='nearby'. */
  centerLat?: number;
  centerLng?: number;
  /** km radius (default 50). Only used in nearby mode. */
  radiusKm?: number;
  /** Optional cap on hospitals to render (default 80). */
  maxMarkers?: number;
  /** Optional fixed height (default 480px). */
  height?: number | string;
  /** Optional className for the wrapping div. */
  className?: string;
}

const BD_CENTER: [number, number] = [23.6850, 90.3563];
const BD_MAX_BOUNDS: [[number, number], [number, number]] = [
  [20.5, 88.0],
  [26.7, 92.7],
];

export default function HospitalMap({
  mode,
  district,
  centerLat,
  centerLng,
  radiusKm = 50,
  maxMarkers = 80,
  height = 480,
  className,
}: HospitalMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const markerGroupRef = useRef<any>(null);
  const LRef = useRef<any>(null);
  const [error, setError] = useState<string | null>(null);

  // ─── Data ─────────────────────────────────────────────────────────
  const districtQuery = useQuery({
    queryKey: ['hospitals', 'for-map', district],
    queryFn: () => getHospitals({ district: district!, limit: 200 }),
    enabled: mode === 'district' && !!district,
    staleTime: 5 * 60 * 1000,
  });
  const nearbyQuery = useQuery({
    queryKey: ['hospitals', 'nearby', centerLat, centerLng, radiusKm],
    queryFn: () => getNearbyHospitals({ lat: centerLat!, lng: centerLng!, radius_km: radiusKm, limit: maxMarkers }),
    enabled:
      mode === 'nearby' &&
      typeof centerLat === 'number' &&
      typeof centerLng === 'number' &&
      Number.isFinite(centerLat) &&
      Number.isFinite(centerLng),
    staleTime: 5 * 60 * 1000,
  });
  // National mode: summarise counts from districts-summary (we
  // don't try to draw 262 markers -- just a national-level pin per
  // district.  Cap to first 64 ordered by hospital count.)
  const nationalQuery = useQuery({
    queryKey: ['hospitals', 'national-districts'],
    queryFn: async () => {
      // Lazy import: the directory imports it via api.ts.
      const { getDistrictsSummary } = await import('@/lib/api');
      return getDistrictsSummary();
    },
    enabled: mode === 'national',
    staleTime: 5 * 60 * 1000,
  });

  // ─── Leaflet init (one-time) ──────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    let cancelled = false;
    (async () => {
      try {
        const L = await import('leaflet');
        if (cancelled) return;
        LRef.current = L;
        const map = L.map(containerRef.current!, {
          center: BD_CENTER,
          zoom: 7,
          maxBounds: BD_MAX_BOUNDS,
          maxBoundsViscosity: 0.6,
          scrollWheelZoom: true,
        });
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
          attribution: '© OpenStreetMap contributors',
          maxZoom: 19,
        }).addTo(map);
        const group = L.layerGroup().addTo(map);
        mapRef.current = map;
        markerGroupRef.current = group;
      } catch (e: any) {
        setError(e?.message || 'Failed to load map');
      }
    })();
    return () => {
      cancelled = true;
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
        markerGroupRef.current = null;
      }
    };
  }, []);

  // ─── Marker rendering ─────────────────────────────────────────────
  useEffect(() => {
    const L = LRef.current;
    const map = mapRef.current;
    const group = markerGroupRef.current;
    if (!L || !map || !group) return;

    group.clearLayers();

    if (mode === 'district') {
      if (districtQuery.isLoading) return;
      if (districtQuery.isError || !districtQuery.data) {
        return;
      }
      const rows: HospitalPublic[] = districtQuery.data.items ?? [];
      if (rows.length === 0) return;
      const bounds: [number, number][] = [];
      rows.slice(0, maxMarkers).forEach((h) => {
        if (typeof h.latitude !== 'number' || typeof h.longitude !== 'number') return;
        const marker = L.marker([h.latitude, h.longitude], {
          icon: L.divIcon({
            className: 'fs-hospital-marker',
            iconSize: [22, 22],
            iconAnchor: [11, 11],
            html: `<span class="dot"></span><span class="label">${escapeHtml(h.name)}</span>`,
          }),
          title: h.name,
        });
        marker.bindTooltip(
          `<b>${escapeHtml(h.name)}</b><br/>` +
            (h.hospital_type ? `${escapeHtml(h.hospital_type)}<br/>` : '') +
            (h.address ? `${escapeHtml(h.address)}<br/>` : '') +
            (h.capacity_status ? `Status: ${h.capacity_status}` : ''),
          { direction: 'top', offset: [0, -8] }
        );
        marker.addTo(group);
        bounds.push([h.latitude, h.longitude]);
      });
      if (bounds.length > 0) {
        map.fitBounds(bounds, { padding: [30, 30], maxZoom: 11 });
      }
      return;
    }

    if (mode === 'nearby') {
      if (nearbyQuery.isLoading) return;
      if (nearbyQuery.isError || !nearbyQuery.data) return;
      const rows: NearbyHospital[] = nearbyQuery.data;
      if (typeof centerLat !== 'number' || typeof centerLng !== 'number') return;
      const bounds: [number, number][] = [];
      // User pin
      const youPin = L.marker([centerLat, centerLng], {
        icon: L.divIcon({
          className: 'fs-user-marker',
          iconSize: [22, 22],
          iconAnchor: [11, 11],
          html: '<span class="you">●</span>',
        }),
        zIndexOffset: 1000,
      });
      youPin.bindTooltip('You are here', { direction: 'top', offset: [0, -8] });
      youPin.addTo(group);
      bounds.push([centerLat, centerLng]);

      rows.forEach((h) => {
        if (typeof h.latitude !== 'number' || typeof h.longitude !== 'number') return;
        const marker = L.marker([h.latitude, h.longitude], {
          icon: L.divIcon({
            className: 'fs-hospital-marker',
            iconSize: [22, 22],
            iconAnchor: [11, 11],
            html: `<span class="dot"></span><span class="label">${escapeHtml(h.name)}</span>`,
          }),
          title: h.name,
        });
        marker.bindTooltip(
          `<b>${escapeHtml(h.name)}</b><br/>` +
            (typeof h.distance_km === 'number'
              ? `${h.distance_km.toFixed(1)} km away<br/>`
              : '') +
            (h.address ? `${escapeHtml(h.address)}<br/>` : ''),
          { direction: 'top', offset: [0, -8] }
        );
        marker.addTo(group);
        bounds.push([h.latitude, h.longitude]);
      });
      if (bounds.length > 1) {
        map.fitBounds(bounds, { padding: [40, 40], maxZoom: 13 });
      } else {
        map.setView([centerLat, centerLng], 10);
      }
      return;
    }

    if (mode === 'national') {
      if (nationalQuery.isLoading) return;
      if (nationalQuery.isError || !nationalQuery.data) return;
      // For the national mode we don't have per-district lat/lng on
      // hand (we have aggregates only).  We DO have lat/lng on the
      // Hospital model, so fall back to a 200-row hospital fetch for
      // the top districts.  Cheap enough at the country scale.
      (async () => {
        try {
          const { getHospitals } = await import('@/lib/api');
          const all = await getHospitals({ limit: 200, sort: 'occupancy' });
          const rows: HospitalPublic[] = all.items ?? [];
          const bounds: [number, number][] = [];
          rows.forEach((h) => {
            if (typeof h.latitude !== 'number' || typeof h.longitude !== 'number') return;
            const marker = L.marker([h.latitude, h.longitude], {
              icon: L.divIcon({
                className: 'fs-hospital-marker small',
                iconSize: [14, 14],
                iconAnchor: [7, 7],
                html: '<span class="dot"></span>',
              }),
              title: h.name,
            });
            marker.addTo(group);
            bounds.push([h.latitude, h.longitude]);
          });
          if (bounds.length > 0) {
            map.fitBounds(bounds, { padding: [20, 20] });
          }
        } catch {
          /* swallow */
        }
      })();
    }
  }, [
    mode,
    district,
    centerLat,
    centerLng,
    districtQuery.data,
    districtQuery.isLoading,
    districtQuery.isError,
    nearbyQuery.data,
    nearbyQuery.isLoading,
    nearbyQuery.isError,
    nationalQuery.data,
    nationalQuery.isLoading,
    nationalQuery.isError,
    maxMarkers,
  ]);

  // External state messages
  const showLoading =
    (mode === 'district' && districtQuery.isLoading) ||
    (mode === 'nearby' && nearbyQuery.isLoading) ||
    (mode === 'national' && nationalQuery.isLoading);

  return (
    <div className={`relative ${className || ''}`} style={{ height }}>
      <div
        ref={containerRef}
        className="w-full h-full rounded-2xl overflow-hidden border"
        style={{ borderColor: 'rgba(255,255,255,0.08)', minHeight: 280 }}
      />
      {error && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="px-3 py-2 rounded-lg bg-red-500/20 text-red-200 text-xs flex items-center gap-1">
            <AlertCircle size={12} /> {error}
          </div>
        </div>
      )}
      {showLoading && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="px-3 py-2 rounded-lg bg-black/40 text-white/80 text-xs flex items-center gap-2">
            <Loader2 size={12} className="animate-spin" /> Loading hospitals…
          </div>
        </div>
      )}

      {/* Marker styling -- light, with a dark label that auto-hides when stacked */}
      <style jsx global>{`
        .fs-hospital-marker .dot {
          display: block;
          width: 14px; height: 14px; border-radius: 50%;
          background: linear-gradient(135deg, #38BDF8, #2DD4BF);
          border: 2px solid rgba(255,255,255,0.9);
          box-shadow: 0 1px 6px rgba(0,0,0,0.45);
        }
        .fs-hospital-marker.small .dot {
          width: 9px; height: 9px; border-width: 1px;
        }
        .fs-hospital-marker .label {
          position: absolute;
          left: 16px; top: 50%;
          transform: translateY(-50%);
          font-size: 11px; color: #fff;
          text-shadow: 0 1px 2px rgba(0,0,0,0.6);
          white-space: nowrap;
          max-width: 200px;
          overflow: hidden; text-overflow: ellipsis;
        }
        .fs-user-marker .you {
          display: block;
          width: 22px; height: 22px; border-radius: 50%;
          background: #F43F5E;
          color: white;
          font-size: 16px; line-height: 22px; text-align: center;
          border: 3px solid white;
          box-shadow: 0 0 0 6px rgba(244,63,94,0.25);
        }
        .leaflet-container { background: #0b1320; }
      `}</style>
    </div>
  );
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
