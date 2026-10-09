'use client';

import { useEffect, useRef, useState } from 'react';
import type { Map as LeafletMap } from 'leaflet';
import type { FloodExtentResponse } from '@/lib/types';

interface SatelliteOverlayProps {
  data: FloodExtentResponse | null;
  isLoading?: boolean;
  district: string;
  height?: string;
  /** Districts currently registered in the backend registry, used to make
   *  the empty-state hint accurate instead of hard-coding 'only Feni'. */
  availableDistricts?: string[];
}

const BD_CENTER: [number, number] = [23.685, 90.356];

export default function SatelliteOverlay({
  data,
  isLoading,
  district,
  height = '300px',
  availableDistricts = [],
}: SatelliteOverlayProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const beforeLayerRef = useRef<any>(null);
  const afterLayerRef = useRef<any>(null);
  const [comparisonValue, setComparisonValue] = useState(50);
  const hasComparison = Boolean(data?.before_geojson && (data.after_geojson || data.geojson));

  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (!mapContainerRef.current) return;

    let cancelled = false;

    // Clear stale Leaflet state (Fast Refresh)
    const container = mapContainerRef.current as HTMLDivElement & { _leaflet_id?: number };
    if (container._leaflet_id) {
      mapRef.current?.remove();
      mapRef.current = null;
      delete container._leaflet_id;
    }

    import('leaflet').then((L) => {
      if (cancelled || !mapContainerRef.current) return;
      if (mapRef.current) return;

      const map = L.map(mapContainerRef.current, {
        center: BD_CENTER,
        zoom: 9,
        zoomControl: true,
        attributionControl: false,
      });

      mapRef.current = map;

      // Free dark tiles – no API key required
      L.tileLayer('https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}{r}.png', {
        maxZoom: 20,
        attribution: '© <a href="https://stadiamaps.com/">Stadia Maps</a> © <a href="https://openmaptiles.org/">OpenMapTiles</a> © <a href="https://openstreetmap.org">OpenStreetMap</a>',
      }).addTo(map);

      if (data?.geojson) {
        const afterGeoJson = data.after_geojson ?? data.geojson;
        const geoLayer = L.geoJSON(afterGeoJson as GeoJSON.FeatureCollection, {
          style: {
            fillColor: '#2DD4BF',
            fillOpacity: 0.35,
            color: '#2DD4BF',
            weight: 1.5,
          },
        }).addTo(map);
        afterLayerRef.current = geoLayer;

        if (data.before_geojson) {
          beforeLayerRef.current = L.geoJSON(data.before_geojson as GeoJSON.FeatureCollection, {
            style: { fillColor: '#38BDF8', fillOpacity: 0.35, color: '#38BDF8', weight: 1.5 },
          }).addTo(map);
          beforeLayerRef.current.setStyle({ opacity: comparisonValue / 100, fillOpacity: 0.35 * comparisonValue / 100 });
        }

        // Fit map to satellite data bounds
        try {
          map.fitBounds(geoLayer.getBounds(), { padding: [20, 20] });
        } catch {
          // If empty geometry, stay on BD_CENTER
        }

        // Satellite legend
        const LegendControl = L.Control.extend({
          options: { position: 'bottomright' },
          onAdd: () => {
            const div = L.DomUtil.create('div');
            div.innerHTML = `
              <div style="background:rgba(6,11,20,0.9);border:1px solid rgba(255,255,255,0.1);border-radius:8px;padding:8px 12px;font-family:Inter,sans-serif;font-size:11px;color:rgba(255,255,255,0.7)">
                <div style="color:#2DD4BF;font-weight:600;margin-bottom:4px">■ Satellite flood extent</div>
                <div>${data.event_label}</div>
              </div>
            `;
            return div;
          }
        });
        new LegendControl().addTo(map);
      }
    });

    return () => {
      cancelled = true;
      mapRef.current?.remove();
      mapRef.current = null;
      beforeLayerRef.current = null;
      afterLayerRef.current = null;
    };
  }, [data]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!beforeLayerRef.current || !afterLayerRef.current) return;
    beforeLayerRef.current.setStyle({ opacity: comparisonValue / 100, fillOpacity: 0.35 * comparisonValue / 100 });
    afterLayerRef.current.setStyle({ opacity: 1 - comparisonValue / 100, fillOpacity: 0.35 * (1 - comparisonValue / 100) });
  }, [comparisonValue]);

  if (isLoading) {
    return (
      <div
        className="rounded-2xl bg-white/05 border border-white/10 animate-pulse flex items-center justify-center"
        style={{ height }}
      >
        <span className="text-white/30 text-sm font-mono">Loading satellite data…</span>
      </div>
    );
  }

  if (!data?.geojson) {
    return (
      <div
        className="rounded-2xl bg-white/05 border border-white/10 flex flex-col items-center justify-center gap-3 text-center px-6"
        style={{ height }}
      >
        <div className="w-10 h-10 rounded-full bg-white/05 flex items-center justify-center text-xl">🛰️</div>
        <div>
          <p className="text-white/60 text-sm font-semibold">No satellite data available yet</p>
          <p className="text-white/30 text-xs mt-1">
            Sentinel-1 SAR coverage for <span className="font-mono">{district}</span> hasn&apos;t been registered.
            {availableDistricts.length > 0 ? (
              <>Currently available: {availableDistricts.map((d, i) => (
                <span key={d} className="font-mono text-teal-400">{d}{i < availableDistricts.length - 1 ? ', ' : ''}</span>
              ))}.</>
            ) : (
              <>No districts have been registered yet.</>
            )}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="relative" style={{ height }}>
      <div
        ref={mapContainerRef}
        style={{ height: '100%', width: '100%', borderRadius: '16px', overflow: 'hidden' }}
        aria-label={`Satellite flood extent map for ${district}`}
      />
      {hasComparison && (
        <div className="absolute bottom-3 left-3 right-3 z-[500] rounded-xl border border-white/10 bg-black/70 px-3 py-2 backdrop-blur">
          <div className="flex justify-between text-[10px] text-white/60 mb-1"><span>Before</span><span>After</span></div>
          <input aria-label="Before and after comparison" type="range" min="0" max="100" value={comparisonValue} onChange={(event) => setComparisonValue(Number(event.target.value))} className="w-full accent-teal-400" />
        </div>
      )}
      {!hasComparison && (
        <div className="absolute bottom-3 left-3 z-[500] rounded-lg border border-white/10 bg-black/70 px-3 py-2 text-[10px] text-white/60 backdrop-blur">
          Before/after comparison unavailable for this export
        </div>
      )}
    </div>
  );
}

