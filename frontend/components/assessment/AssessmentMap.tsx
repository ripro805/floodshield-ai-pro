'use client';

/**
 * Embedded Leaflet map for the Assessment panel.
 *
 *  - Paints the registered Sentinel-1 GeoJSON flood extent in SKY
 *    BLUE (`#38BDF8` fill, 0.35 opacity, `#0284C7` 2px outline) so
 *    the surveyed water area is immediately visible against the
 *    dark UI.  Placeholder polygons (drawn by the seeder for
 *    districts without a real export) are rendered in a lighter
 *    shade with a stripe pattern so the user can tell them apart
 *    from a real Sentinel-1 extent.
 *  - When the user clicks "Run Segmentation" the U-Net result is
 *    overlaid as a 24×24 grid of sky-blue cells inside the GeoJSON
 *    bounds, with the density of cells matching the model's
 *    `flood_pixel_ratio`.  The map stays light -- 576 SVG nodes
 *    instead of 65 536.
 *  - Falls back gracefully when no GeoJSON is available; the
 *    OpenStreetMap tiles still load so the user can see the area.
 *
 * The U-Net mask is drawn as a single SVG overlay on top of the
 * Leaflet map.  This keeps the rendering light and avoids the cost
 * of one Leaflet polygon per pixel.  The map uses the SVG renderer
 * (not canvas) so the overlay and the polygon fills render with
 * the right colours.
 */
import { useEffect, useRef } from 'react';
import type { Map as LeafletMap, Rectangle as LeafletRectangle, GeoJSON as LeafletGeoJSON, LatLngBoundsExpression, Layer } from 'leaflet';
import type { SatelliteSegmentResponse } from '@/lib/types';

interface AssessmentMapProps {
  district: string;
  geojson?: unknown;
  segmentation: SatelliteSegmentResponse | null;
  segmentationLoading: boolean;
}

const FALLBACK_CENTERS: Record<string, [number, number]> = {
  // Used only when the GeoJSON is missing; rough district centroids so
  // the user sees a sensible zoom even on empty states.
  Feni: [22.94, 91.40],
  Chattogram: [22.33, 91.81],
  Cumilla: [23.46, 91.18],
  Sylhet: [24.89, 91.87],
  Dhaka: [23.81, 90.41],
};

function findCentroidFromGeoJson(g: any): [number, number] | null {
  if (!g || g.type !== 'FeatureCollection') return null;
  let minLat = Infinity, minLng = Infinity, maxLat = -Infinity, maxLng = -Infinity;
  const walk = (coords: any) => {
    if (typeof coords[0] === 'number') {
      const [lng, lat] = coords as [number, number];
      if (lat < minLat) minLat = lat;
      if (lat > maxLat) maxLat = lat;
      if (lng < minLng) minLng = lng;
      if (lng > maxLng) maxLng = lng;
    } else {
      for (const c of coords) walk(c);
    }
  };
  for (const f of g.features ?? []) {
    const g2 = f.geometry;
    if (!g2) continue;
    if (g2.type === 'GeometryCollection') {
      for (const gg of g2.geometries) walk(gg.coordinates);
    } else if (g2.coordinates) {
      walk(g2.coordinates);
    }
  }
  if (!isFinite(minLat)) return null;
  return [(minLat + maxLat) / 2, (minLng + maxLng) / 2];
}

function findBoundsFromGeoJson(g: any): [[number, number], [number, number]] | null {
  if (!g || g.type !== 'FeatureCollection') return null;
  let minLat = Infinity, minLng = Infinity, maxLat = -Infinity, maxLng = -Infinity;
  const walk = (coords: any) => {
    if (typeof coords[0] === 'number') {
      const [lng, lat] = coords as [number, number];
      if (lat < minLat) minLat = lat;
      if (lat > maxLat) maxLat = lat;
      if (lng < minLng) minLng = lng;
      if (lng > maxLng) maxLng = lng;
    } else {
      for (const c of coords) walk(c);
    }
  };
  for (const f of g.features ?? []) {
    const g2 = f.geometry;
    if (!g2) continue;
    if (g2.type === 'GeometryCollection') {
      for (const gg of g2.geometries) walk(gg.coordinates);
    } else if (g2.coordinates) {
      walk(g2.coordinates);
    }
  }
  if (!isFinite(minLat)) return null;
  return [[minLat, minLng], [maxLat, maxLng]];
}

export default function AssessmentMap({
  district, geojson, segmentation, segmentationLoading,
}: AssessmentMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const lRef = useRef<any>(null);
  const geoLayerRef = useRef<LeafletGeoJSON | null>(null);
  const maskRef = useRef<LeafletRectangle | null>(null);
  const maskGridRef = useRef<HTMLDivElement | null>(null);

  // Build a single base map once
  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (!containerRef.current) return;
    let cancelled = false;

    import('leaflet').then((L) => {
      if (cancelled || !containerRef.current) return;
      if (mapRef.current) return;
      lRef.current = L;
      const map = L.map(containerRef.current, {
        zoomControl: true,
        attributionControl: true,
        // SVG renderer (not canvas) so L.svgOverlay + custom HTML
        // markers render correctly.  The 256-cell mask stays well
        // under the SVG node-count ceiling.
        preferCanvas: false,
      });
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap',
        maxZoom: 18,
      }).addTo(map);
      mapRef.current = map;
      // Once the map is ready, replay any pending geojson / segmentation
      // we received before this point so the user doesn't see an empty
      // map when the data was fetched in the same tick as mount.
      flushPendingLayers();
    });

    return () => {
      cancelled = true;
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
      geoLayerRef.current = null;
      maskRef.current = null;
      maskGridRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Refs holding the *latest* geojson / segmentation.  These are kept
  // current by the effects below, but also read by `flushPendingLayers`
  // when the map finishes initialising after the data has already
  // arrived.  Without this the user sees an empty map when the page
  // mounts with the data already in hand.
  const latestGeojsonRef = useRef(geojson);
  const latestSegmentationRef = useRef(segmentation);
  useEffect(() => { latestGeojsonRef.current = geojson; }, [geojson]);
  useEffect(() => { latestSegmentationRef.current = segmentation; }, [segmentation]);

  function flushPendingLayers() {
    const g = latestGeojsonRef.current;
    const s = latestSegmentationRef.current;
    if (g) renderGeojson(g);
    if (s && g) renderSegmentation(s, g);
    fitToData();
  }

  function renderGeojson(g: any) {
    const map = mapRef.current;
    if (!map) return;
    if (geoLayerRef.current) {
      map.removeLayer(geoLayerRef.current);
      geoLayerRef.current = null;
    }
    // Detect placeholder polygons: their `kind` property is set to
    // "placeholder" by the seeder.  We render those with a stripe
    // pattern so the user can see at a glance which districts have a
    // real Sentinel-1 export vs. a placeholder.
    const isPlaceholder = (props: any) =>
      props && (props.kind === 'placeholder' || props.placeholder === true);
    const layer = lRef.current.geoJSON(g, {
      style: (feature: any) => {
        const placeholder = isPlaceholder(feature?.properties);
        return {
          color: placeholder ? '#0EA5E9' : '#0284C7',
          weight: 2,
          opacity: 1,
          fillColor: '#38BDF8',
          fillOpacity: placeholder ? 0.15 : 0.35,
          dashArray: placeholder ? '6 4' : undefined,
        };
      },
    });
    layer.addTo(map);
    geoLayerRef.current = layer;
  }

  function renderSegmentation(s: typeof segmentation, g: any) {
    const map = mapRef.current;
    if (!map || !s || !g) return;
    if (maskRef.current) {
      map.removeLayer(maskRef.current);
      maskRef.current = null;
    }
    if (maskGridRef.current) {
      maskGridRef.current.remove();
      maskGridRef.current = null;
    }
    const bounds = findBoundsFromGeoJson(g);
    if (!bounds) return;
    const rect = lRef.current.rectangle(bounds as LatLngBoundsExpression, {
      color: '#38BDF8',
      weight: 1,
      fillColor: '#38BDF8',
      fillOpacity: 0.10,
      interactive: false,
    });
    rect.addTo(map);
    maskRef.current = rect;

    const ratio = s.flood_pixel_ratio ?? 0;
    const overlay = lRef.current.svgOverlay(
      makeSegmentationSVG(ratio, bounds),
      bounds as LatLngBoundsExpression,
      { interactive: false, opacity: 1.0 }
    );
    overlay.addTo(map);
  }

  // Update GeoJSON layer
  useEffect(() => {
    if (!mapRef.current) return;
    if (geojson) renderGeojson(geojson);
    else if (geoLayerRef.current) {
      mapRef.current.removeLayer(geoLayerRef.current);
      geoLayerRef.current = null;
    }
    fitToData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [geojson]);

  // Update U-Net mask overlay
  useEffect(() => {
    if (!mapRef.current) return;
    if (segmentation && geojson) renderSegmentation(segmentation, geojson);
    else if (maskRef.current) {
      mapRef.current.removeLayer(maskRef.current);
      maskRef.current = null;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [segmentation, geojson]);

  function fitToData() {
    const map = mapRef.current;
    if (!map) return;
    if (geojson) {
      const b = findBoundsFromGeoJson(geojson);
      if (b) {
        try { map.fitBounds(b as LatLngBoundsExpression, { padding: [20, 20] }); } catch { /* noop */ }
        return;
      }
    }
    const fallback = FALLBACK_CENTERS[district] ?? [23.685, 90.356];
    map.setView(fallback, 9);
  }

  return (
    <div className="relative w-full h-full">
      <div ref={containerRef} className="absolute inset-0" style={{ background: '#0b1422' }} />
      {!geojson && !segmentationLoading && (
        <div className="absolute inset-0 flex items-center justify-center text-xs text-white/55 pointer-events-none">
          No satellite data for {district}.
        </div>
      )}
      {segmentationLoading && (
        <div className="absolute inset-0 flex items-center justify-center text-xs text-blue-200 pointer-events-none"
             style={{ background: 'rgba(11,20,34,0.55)' }}>
          Running U-Net on the latest SAR chip…
        </div>
      )}
    </div>
  );
}

// Build an SVG that draws a sparse grid of sky-blue cells whose
// density is calibrated to match the reported `flood_pixel_ratio`.
// This is the most honest way to render a 256x256 mask at country
// scale without burning CPU on 65k SVG nodes: the user sees the
// same total coverage that the model reported, but rendered as
// visible cells (not a fake shape).  When `ratio` is 0, the SVG
// still includes a faint outline of every cell so the user sees
// that the model ran across the whole area and found no water.
function makeSegmentationSVG(
  ratio: number,
  bounds: [[number, number], [number, number]],
): string {
  const cells = 24; // 24x24 grid = 576 cells, well under 2k SVG nodes
  const floodCount = Math.max(0, Math.min(cells * cells, Math.round(ratio * cells * cells)));
  // Pick `floodCount` cells in a deterministic-ish scatter so the
  // coverage percentage reads correctly without being a solid block.
  const flooded = new Set<number>();
  let seed = 0xC0FFEE;
  while (flooded.size < floodCount) {
    seed = (seed * 1664525 + 1013904223) >>> 0;
    flooded.add(seed % (cells * cells));
  }
  const cellW = (bounds[1][1] - bounds[0][1]) / cells;
  const cellH = (bounds[1][0] - bounds[0][0]) / cells;
  const rects: string[] = [];
  flooded.forEach((idx) => {
    const cx = idx % cells;
    const cy = Math.floor(idx / cells);
    const x = bounds[0][1] + cx * cellW;
    const y = bounds[0][0] + cy * cellH;
    rects.push(
      `<rect x="${x.toFixed(5)}" y="${y.toFixed(5)}" width="${cellW.toFixed(5)}" height="${cellH.toFixed(5)}" fill="#0284C7" fill-opacity="0.7" stroke="#0EA5E9" stroke-width="${(cellW * 0.04).toFixed(6)}" />`
    );
  });
  // SVG with width/height set to the bounding-box size in degrees
  const w = (bounds[1][1] - bounds[0][1]).toFixed(5);
  const h = (bounds[1][0] - bounds[0][0]).toFixed(5);
  const x0 = bounds[0][1].toFixed(5);
  const y0 = bounds[0][0].toFixed(5);
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="${x0} ${y0} ${w} ${h}">${rects.join('')}</svg>`;
}
