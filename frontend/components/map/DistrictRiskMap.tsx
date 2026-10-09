'use client';

import { forwardRef, useEffect, useImperativeHandle, useMemo, useRef, useState } from 'react';
import type { Map as LeafletMap, GeoJSON as LeafletGeoJSON, Path, Marker as LeafletMarker } from 'leaflet';
import type { HotspotDistrict, RiskLevel } from '@/lib/types';
import { RISK_COLORS } from '@/lib/types';
import { apiClient } from '@/lib/api';
import { getToken } from '@/lib/auth';

const RISK_OPACITY: Record<RiskLevel, number> = {
  Low: 0.30,
  Medium: 0.45,
  High: 0.60,
  Critical: 0.75,
};

const CLUSTER_COLORS = ['#a78bfa', '#22d3ee', '#f472b6', '#84cc16', '#fb7185', '#facc15'];

interface DistrictRisk {
  district: string;
  riskLevel: RiskLevel;
  score?: number;
  hotspotCluster?: number;
}

function featureDistrictName(feature: GeoJSON.Feature): string {
  const properties = feature.properties as {
    ADM2_EN?: string;
    NAME_2?: string;
    district?: string;
    district_name?: string;
  } | null;
  return (
    properties?.ADM2_EN ??
    properties?.NAME_2 ??
    properties?.district ??
    properties?.district_name ??
    ''
  );
}

interface AllDistrictsRiskItem {
  district: string;
  risk_level: string;
  composite_score: number;
  flood_severity: string;
  predicted_outbreak_risk: string;
}

interface AllDistrictsRiskResponse {
  districts: AllDistrictsRiskItem[];
}

type DistrictGeometry =
  | { type: 'Polygon'; coordinates: number[][][] }
  | { type: 'MultiPolygon'; coordinates: number[][][][] };

interface DistrictGeometryEntry {
  name: string;
  center: [number, number];
  bounds: [[number, number], [number, number]]; // [[south, west], [north, east]]
}

function polygonRingExtent(ring: number[][]): {
  south: number; north: number; west: number; east: number;
} {
  let south = Infinity, west = Infinity, north = -Infinity, east = -Infinity;
  for (const point of ring) {
    const lng = point[0]; const lat = point[1];
    if (lat < south) south = lat;
    if (lat > north) north = lat;
    if (lng < west) west = lng;
    if (lng > east) east = lng;
  }
  return { south, north, west, east };
}

function geometryExtent(geom: DistrictGeometry) {
  if (geom.type === 'Polygon') {
    return polygonRingExtent(geom.coordinates[0]);
  }
  // MultiPolygon: union of every ring's extent
  let south = Infinity, west = Infinity, north = -Infinity, east = -Infinity;
  for (const poly of geom.coordinates) {
    const ext = polygonRingExtent(poly[0]);
    if (ext.south < south) south = ext.south;
    if (ext.north > north) north = ext.north;
    if (ext.west < west) west = ext.west;
    if (ext.east > east) east = ext.east;
  }
  return { south, north, west, east };
}

function ringCentroid(ring: number[][]): [number, number] {
  let sumLng = 0, sumLat = 0;
  for (const [lng, lat] of ring) { sumLng += lng; sumLat += lat; }
  return [sumLat / ring.length, sumLng / ring.length];
}

function geometryCentroid(geom: DistrictGeometry): [number, number] {
  if (geom.type === 'Polygon') return ringCentroid(geom.coordinates[0]);
  // MultiPolygon: area-weighted centroid across outer rings
  let sumLng = 0, sumLat = 0, sumWeight = 0;
  for (const poly of geom.coordinates) {
    const ring = poly[0];
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const [x, y] of ring) {
      if (x < minX) minX = x;
      if (x > maxX) maxX = x;
      if (y < minY) minY = y;
      if (y > maxY) maxY = y;
    }
    const w = Math.max(1, (maxX - minX) * (maxY - minY));
    const c = ringCentroid(ring);
    sumLng += c[1] * w; sumLat += c[0] * w; sumWeight += w;
  }
  return sumWeight === 0 ? BD_CENTER : [sumLat / sumWeight, sumLng / sumWeight];
}

function normalizeDistrictName(name: string): string {
  const aliases: Record<string, string> = {
    'chittagong': 'chattogram',
    'comilla': 'cumilla',
    'jessore': 'jashore',
    'bogra': 'bogura',
  };
  const lower = name.toLowerCase().trim();
  return aliases[lower] ?? lower;
}

interface DistrictRiskMapProps {
  districtRisks?: DistrictRisk[];
  selectedDistrict?: string;
  onDistrictClick?: (district: string) => void;
  height?: string;
  showSatellite?: boolean;
  hotspotDistricts?: HotspotDistrict[];
}

// Bangladesh centroid + zoom
const BD_CENTER: [number, number] = [23.685, 90.356];
const BD_ZOOM = 7;
// Bounding box that fences the map inside Bangladesh so users cannot pan
// out into the Bay of Bengal / Myanmar / India and lose the country context.
// Leaflet's setMaxBounds keeps the world bounded with rubber-banding past
// the limit, so a slightly tighter box is preferable to the literal polygon.
const BD_MAX_BOUNDS: [[number, number], [number, number]] = [
  [20.5, 88.0], // south-west (just inside the Sundarbans / Dinajpur)
  [26.6, 92.7], // north-east (Panchagarh / Chattogram Hill Tracts)
];
const BD_MIN_ZOOM = 6;
const BD_MAX_ZOOM = 12;

// Inline HTML for the selected-district marker (pin SVG + halo ring +
// district name label). Factored out of the effect body so both the
// "first placement" and "reuse" branches render the same DOM.
function markerHtml(displayName: string): string {
  return `
    <div class="floodshield-marker-halo"></div>
    <svg viewBox="0 0 32 44" height="44" width="32" class="floodshield-marker-pin">
      <path d="M16 0C7.16 0 0 7.16 0 16c0 11.2 16 28 16 28s16-16.8 16-28C32 7.16 24.84 0 16 0z"
        fill="#38BDF8" stroke="#0EA5E9" stroke-width="1.5" />
      <circle cx="16" cy="16" r="6" fill="#060B14" />
    </svg>
    <div class="floodshield-marker-label">${displayName}</div>
  `;
}

// Local GeoJSON (downloaded, no external dependency)
const GEOJSON_URL = '/data/bangladesh.geojson';

// Tile layer configurations – Google Maps style, no API key needed
const TILE_LAYERS = {
  roadmap: {
    url: 'https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}',
    label: 'Roadmap',
    attribution: '© Google Maps',
  },
  satellite: {
    url: 'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
    label: 'Satellite',
    attribution: '© Google Maps',
  },
  hybrid: {
    url: 'https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
    label: 'Hybrid',
    attribution: '© Google Maps',
  },
  terrain: {
    url: 'https://mt1.google.com/vt/lyrs=p&x={x}&y={y}&z={z}',
    label: 'Terrain',
    attribution: '© Google Maps',
  },
};

export interface DistrictRiskMapHandle {
  /** Imperatively fly to a district and drop a marker on its centroid. */
  flyToDistrict: (name: string) => void;
  /** Imperatively fly back to a country-level view (clears the marker). */
  flyToCountry: () => void;
}

const DistrictRiskMap = forwardRef<DistrictRiskMapHandle, DistrictRiskMapProps>(function DistrictRiskMap({
  districtRisks = [],
  selectedDistrict,
  onDistrictClick,
  height = '100%',
  showSatellite = false,
  hotspotDistricts = [],
}, ref) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const geojsonLayerRef = useRef<LeafletGeoJSON | null>(null);
  const selectedMarkerRef = useRef<LeafletMarker | null>(null);
  const tileLayerRef = useRef<any>(null);

  const [activeLayer, setActiveLayer] = useState<keyof typeof TILE_LAYERS>(
    showSatellite ? 'hybrid' : 'roadmap'
  );
  const [allRisks, setAllRisks] = useState<DistrictRisk[]>(districtRisks);
  const [loadingRisks, setLoadingRisks] = useState(true);
  // True once the Bangladesh districts GeoJSON has been fetched and added to
  // the map. The selected-district marker effect listens on this so the very
  // first selectedDistrict (e.g. the default "Feni") still gets a marker
  // even if the dropdown hasn't been touched since page load.
  const [geojsonReady, setGeojsonReady] = useState(false);
  const hotspotMap = useMemo(
    () => new Map(hotspotDistricts.map((item) => [item.district.toLowerCase(), item])),
    [hotspotDistricts]
  );

  // Fetch live risk data from backend
  useEffect(() => {
    const token = getToken();
    if (!token) {
      setLoadingRisks(false);
      return;
    }
    apiClient
      .get<AllDistrictsRiskResponse>('/predict/risk/all-districts', {
        params: { _v: 'environmental-v2' },
        headers: { Authorization: `Bearer ${token}` },
      })
      .then(({ data }) => {
        const mapped: DistrictRisk[] = data.districts.map((item) => ({
          district: item.district,
          riskLevel: item.risk_level as RiskLevel,
          score: item.composite_score,
        }));
        setAllRisks(mapped);
      })
      .catch((err) => {
        console.warn('Could not fetch all-districts risk data, using props fallback:', err);
        setAllRisks(districtRisks);
      })
      .finally(() => setLoadingRisks(false));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Initialize map once
  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (!mapContainerRef.current) return;

    // cancelled is set to true by the cleanup function. If React StrictMode
    // unmounts and remounts (double-fires the effect), the first async import
    // will see cancelled=true and bail out, leaving the second to initialise cleanly.
    let cancelled = false;

    // Clear any stale Leaflet state left on the DOM node (e.g. after Fast Refresh)
    const container = mapContainerRef.current as HTMLDivElement & { _leaflet_id?: number };
    if (container._leaflet_id) {
      mapRef.current?.remove();
      mapRef.current = null;
      delete container._leaflet_id;
    }

    import('leaflet').then((L) => {
      if (cancelled || !mapContainerRef.current) return;
      // Extra guard: if another effect run already created the map, skip
      if (mapRef.current) return;

      // Fix default icon paths for webpack
      // @ts-expect-error – _getIconUrl is not in types
      delete L.Icon.Default.prototype._getIconUrl;
      L.Icon.Default.mergeOptions({
        iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
        iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
        shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
      });

      const map = L.map(mapContainerRef.current!, {
        center: BD_CENTER,
        zoom: BD_ZOOM,
        minZoom: BD_MIN_ZOOM,
        maxZoom: BD_MAX_ZOOM,
        maxBounds: BD_MAX_BOUNDS,
        // Rubber-band past the bounds rather than showing a grey void, so
        // Bangladesh stays anchored but tiles can briefly peek outside.
        maxBoundsViscosity: 0.85,
        zoomControl: false,
        attributionControl: false,
      });

      // Belt-and-braces: re-apply the bounds after the first paint in case the
      // container had a weird initial size and Leaflet computed the wrong
      // viewport during init.
      map.fitBounds(BD_MAX_BOUNDS, { padding: [10, 10] });

      // Recompute the cached container size -- if the map mounted inside
      // a responsive container whose size is computed after this init,
      // flyToBounds silently no-ops. invalidateSize() forces a recalc.
      setTimeout(() => map.invalidateSize(), 0);
      window.addEventListener('resize', () => map.invalidateSize());

      mapRef.current = map;

      // Add zoom control (top-right, styled)
      L.control.zoom({ position: 'topright' }).addTo(map);

      // Initial tile layer
      const layerCfg = TILE_LAYERS[showSatellite ? 'hybrid' : 'roadmap'];
      L.tileLayer(layerCfg.url, { maxZoom: 19, tileSize: 256 }).addTo(map);
      L.control.attribution({ prefix: layerCfg.attribution, position: 'bottomright' }).addTo(map);
    });

    return () => {
      cancelled = true;
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Draw / redraw GeoJSON overlay whenever allRisks or selectedDistrict changes
  useEffect(() => {
    if (loadingRisks) return;
    if (!mapRef.current) {
      // Map not ready yet — wait a tick
      const timer = setTimeout(() => {
        // triggers re-render
      }, 300);
      return () => clearTimeout(timer);
    }

    import('leaflet').then((L) => {
      const map = mapRef.current;
      if (!map) return;

      // Remove existing GeoJSON layer
      if (geojsonLayerRef.current) {
        geojsonLayerRef.current.remove();
        geojsonLayerRef.current = null;
        setGeojsonReady(false);
      }

      const riskMap = new Map(allRisks.map((d) => [d.district.toLowerCase(), d]));
      const scoreMap = new Map(allRisks.map((d) => [d.district.toLowerCase(), d.score ?? 0]));

      // Normalize district names for matching
      const normalizeDistrictName = (name: string) => {
        const aliases: Record<string, string> = {
          'chittagong': 'chattogram',
          'comilla': 'cumilla',
          'jessore': 'jashore',
          'bogra': 'bogura',
        };
        const lower = name.toLowerCase().trim();
        return aliases[lower] ?? lower;
      };

      fetch(GEOJSON_URL)
        .then((r) => r.json())
        .then((geojson) => {
          const layer = L.geoJSON(geojson as GeoJSON.FeatureCollection, {
            style: (feature) => {
              const rawName = featureDistrictName(feature as GeoJSON.Feature);
              const key = normalizeDistrictName(rawName);
              const info = riskMap.get(key);
              const hotspot = hotspotMap.get(key);
              const risk: RiskLevel = info?.riskLevel ?? 'Low';
              const isSelected = selectedDistrict &&
                normalizeDistrictName(selectedDistrict) === key;

              return {
                fillColor: RISK_COLORS[risk],
                fillOpacity: isSelected ? 0.85 : RISK_OPACITY[risk],
                color: hotspot && !hotspot.is_noise
                  ? CLUSTER_COLORS[hotspot.cluster_id % CLUSTER_COLORS.length]
                  : isSelected ? '#ffffff' : 'rgba(255,255,255,0.18)',
                weight: hotspot && !hotspot.is_noise ? (isSelected ? 3 : 2) : isSelected ? 2.5 : 1,
                dashArray: hotspot && !hotspot.is_noise ? '5 4' : undefined,
              };
            },

            onEachFeature: (feature, layer) => {
              const rawName = featureDistrictName(feature as GeoJSON.Feature) || 'Unknown';
              const key = normalizeDistrictName(rawName);
              const info = riskMap.get(key);
              const hotspot = hotspotMap.get(key);
              const risk: RiskLevel = info?.riskLevel ?? 'Low';
              const score = scoreMap.get(key) ?? 0;

              const riskBadgeColor = RISK_COLORS[risk];
              const riskEmoji: Record<RiskLevel, string> = {
                Low: '🟢',
                Medium: '🟡',
                High: '🟠',
                Critical: '🔴',
              };

              layer.bindTooltip(
                `<div style="
                  background:rgba(6,11,22,0.95);
                  border:1px solid ${riskBadgeColor}40;
                  border-radius:10px;
                  padding:10px 14px;
                  font-family:Inter,system-ui,sans-serif;
                  min-width:200px;
                  box-shadow:0 4px 20px rgba(0,0,0,0.5);
                  display:flex;
                  align-items:center;
                  gap:12px;
                ">
                  <div id="gauge-container-${key}" style="width:40px;height:90px;flex-shrink:0;"></div>
                  <div>
                    <div style="color:#fff;font-weight:700;font-size:14px;letter-spacing:0.3px">${rawName}</div>
                    <div style="display:flex;align-items:center;gap:6px;margin-top:5px">
                      <span style="font-size:13px">${riskEmoji[risk]}</span>
                      <span style="color:${riskBadgeColor};font-size:12px;font-weight:600">${risk} Risk</span>
                    </div>
                    <div style="color:rgba(255,255,255,0.5);font-size:11px;margin-top:3px">Score: ${score.toFixed(2)} / 3.00</div>
                    ${hotspot ? `<div style="color:${hotspot.is_noise ? 'rgba(255,255,255,0.45)' : CLUSTER_COLORS[hotspot.cluster_id % CLUSTER_COLORS.length]};font-size:11px;margin-top:3px">${hotspot.is_noise ? 'Hotspot outlier' : `Disease cluster ${hotspot.cluster_id + 1}`}</div>` : ''}
                  </div>
                </div>`,
                { sticky: true, className: 'leaflet-risk-tooltip', opacity: 1 }
              );

              let tooltipRoot: any = null;
              layer.on('tooltipopen', () => {
                const container = document.getElementById(`gauge-container-${key}`);
                if (container) {
                  import('react-dom/client').then(({ createRoot }) => {
                    import('@/components/three/RiskGaugeTube').then((mod) => {
                      const RiskGaugeTube = mod.default;
                      tooltipRoot = createRoot(container);
                      tooltipRoot.render(
                        <RiskGaugeTube
                          value={Math.min(score / 3, 1)}
                          riskLevel={risk.toLowerCase() as any}
                          size="sm"
                        />
                      );
                    });
                  });
                }
              });

              layer.on('tooltipclose', () => {
                if (tooltipRoot) {
                  // Small delay to allow fade out
                  setTimeout(() => {
                    tooltipRoot?.unmount();
                    tooltipRoot = null;
                  }, 200);
                }
              });

              layer.on({
                mouseover: (e) => {
                  (e.target as Path).setStyle({
                    weight: hotspot && !hotspot.is_noise ? 3 : 2.5,
                    color: hotspot && !hotspot.is_noise ? CLUSTER_COLORS[hotspot.cluster_id % CLUSTER_COLORS.length] : '#ffffff',
                    fillOpacity: Math.min((RISK_OPACITY[risk] ?? 0.3) + 0.2, 0.9),
                  });
                  (e.target as Path).bringToFront();
                },
                mouseout: (e) => {
                  const isSelected = selectedDistrict &&
                    normalizeDistrictName(selectedDistrict) === key;
                  (e.target as Path).setStyle({
                    weight: hotspot && !hotspot.is_noise ? (isSelected ? 3 : 2) : isSelected ? 2.5 : 1,
                    color: hotspot && !hotspot.is_noise
                      ? CLUSTER_COLORS[hotspot.cluster_id % CLUSTER_COLORS.length]
                      : isSelected ? '#ffffff' : 'rgba(255,255,255,0.18)',
                    fillOpacity: isSelected ? 0.85 : RISK_OPACITY[risk],
                  });
                },
                click: () => {
                  onDistrictClick?.(rawName);
                },
              });
            },
          });

          layer.addTo(map!);
          geojsonLayerRef.current = layer;
          setGeojsonReady(true);
        })
        .catch((err) => console.error('GeoJSON load error:', err));
    });
  }, [allRisks, hotspotMap, loadingRisks, selectedDistrict, onDistrictClick]);

  // ----- Fallback centroids -----
  // Used when the selected district isn't present in the GeoJSON layer
  // (e.g. a legacy alias the local file doesn't have, or a typo). Keeps
  // the marker on the map and zooms to a sensible bbox instead of
  // silently doing nothing.
  const DISTRICT_FALLBACK_CENTROIDS: Record<string, { center: [number, number]; bounds: [[number, number], [number, number]] }> = {
    feni: { center: [22.97, 91.40], bounds: [[22.85, 91.30], [23.10, 91.55]] },
    cumilla: { center: [23.45, 90.85], bounds: [[23.30, 90.55], [23.60, 91.05]] },
    comilla: { center: [23.45, 90.85], bounds: [[23.30, 90.55], [23.60, 91.05]] },
    chattogram: { center: [22.30, 91.80], bounds: [[22.10, 91.65], [22.50, 91.95]] },
    chittagong: { center: [22.30, 91.80], bounds: [[22.10, 91.65], [22.50, 91.95]] },
    sylhet: { center: [24.90, 91.85], bounds: [[24.75, 91.65], [25.10, 92.05]] },
    dhaka: { center: [23.80, 90.40], bounds: [[23.55, 90.25], [24.05, 90.55]] },
    rajshahi: { center: [24.40, 88.65], bounds: [[24.15, 88.40], [24.65, 88.90]] },
    khulna: { center: [22.85, 89.55], bounds: [[22.55, 89.25], [23.10, 89.85]] },
    barishal: { center: [22.70, 90.37], bounds: [[22.50, 90.15], [22.95, 90.60]] },
    barisal: { center: [22.70, 90.37], bounds: [[22.50, 90.15], [22.95, 90.60]] },
    mymensingh: { center: [24.75, 90.40], bounds: [[24.55, 90.20], [24.95, 90.65]] },
    rangpur: { center: [25.75, 89.27], bounds: [[25.55, 89.05], [25.95, 89.50]] },
    bogura: { center: [24.85, 89.37], bounds: [[24.65, 89.15], [25.05, 89.60]] },
    bogra: { center: [24.85, 89.37], bounds: [[24.65, 89.15], [25.05, 89.60]] },
    jashore: { center: [23.17, 89.21], bounds: [[22.95, 88.95], [23.40, 89.50]] },
    jessore: { center: [23.17, 89.21], bounds: [[22.95, 88.95], [23.40, 89.50]] },
  };

  function lookupFallback(name: string) {
    return DISTRICT_FALLBACK_CENTROIDS[normalizeDistrictName(name)];
  }

  // ----- flyToDistrict(name) -----
  // Drops a pin at the district and smoothly flies the map to its bbox.
  // Reusable from the React effect below AND from the imperative handle.
  // Pure-side-effect: relies on mapRef / geojsonLayerRef /
  // selectedMarkerRef being current at call time.
  async function flyToDistrict(name: string) {
    if (!name) return;
    const map = mapRef.current;
    if (!map) return;

    let center: [number, number] | null = null;
    let bounds: [[number, number], [number, number]] | null = null;
    let displayName = name;

    // 1. Prefer the GeoJSON match (gives us the real district polygon).
    if (geojsonLayerRef.current) {
      const target = normalizeDistrictName(name);
      geojsonLayerRef.current.eachLayer((layer) => {
        const feat = (layer as any).feature as GeoJSON.Feature<DistrictGeometry> | undefined;
        if (!feat?.properties) return;
        const rawName = (feat.properties as { ADM2_EN?: string }).ADM2_EN ?? '';
        if (normalizeDistrictName(rawName) === target && feat.geometry) {
          const ext = geometryExtent(feat.geometry);
          center = geometryCentroid(feat.geometry);
          bounds = [[ext.south, ext.west], [ext.north, ext.east]];
          displayName = rawName || name;
        }
      });
    }

    // 2. Fall back to the curated centroid table if the GeoJSON has no match.
    if (!center || !bounds) {
      const fb = lookupFallback(name);
      if (fb) { center = fb.center; bounds = fb.bounds; }
    }

    // 3. Last resort: drop a pin at the country centroid and log.
    if (!center || !bounds) {
      center = BD_CENTER;
      bounds = BD_MAX_BOUNDS;
      console.warn('[DistrictRiskMap] No geometry or fallback for district:', name);
    }

    const L = await import('leaflet');

    // Reuse the marker when one exists so changing districts does not flicker.
    if (selectedMarkerRef.current) {
      selectedMarkerRef.current.setLatLng(center);
      selectedMarkerRef.current.unbindTooltip();
      selectedMarkerRef.current.bindTooltip(displayName, {
        direction: 'top',
        offset: [0, -38],
        className: 'leaflet-glass-tooltip',
      });
      selectedMarkerRef.current.setIcon(L.divIcon({
        className: 'floodshield-selected-marker',
        iconSize: [32, 44],
        iconAnchor: [16, 42],
        html: markerHtml(displayName),
      }));
    } else {
      const icon = L.divIcon({
        className: 'floodshield-selected-marker',
        iconSize: [32, 44],
        iconAnchor: [16, 42],
        html: markerHtml(displayName),
      });
      selectedMarkerRef.current = L.marker(center, { icon, riseOnHover: true })
        .addTo(map)
        .bindTooltip(displayName, {
          direction: 'top',
          offset: [0, -38],
          className: 'leaflet-glass-tooltip',
        });
    }

    // Two-step move: setView (instant) then flyTo (animated).
    // flyToBounds sometimes silently no-ops when the bbox is already
    // visible in the viewport -- setView first guarantees a camera
    // change, then flyTo animates the rest of the way.
    try {
      // Make sure Leaflet has the latest container size before
      // computing the target -- responsive containers can lag.
      map.invalidateSize();
      // Fixed target zoom: 9 works for any Bangladesh district at the
      // current tile viewport (~512px district diameter on screen).
      // We tried getBoundsZoom() before but it produced wildly
      // inconsistent values across browsers when the bbox was near
      // the viewport center.
      const targetZoom = 9;
      map.setView(center, targetZoom, { animate: false });
      map.flyTo(center, targetZoom, { duration: 0.8 });
    } catch (e) {
      console.error('[DistrictRiskMap] flyTo failed:', e);
    }
  }


  function flyToCountry() {
    const map = mapRef.current;
    if (!map) return;
    if (selectedMarkerRef.current) {
      selectedMarkerRef.current.remove();
      selectedMarkerRef.current = null;
    }
    map.flyToBounds(BD_MAX_BOUNDS, { padding: [10, 10], duration: 0.6 });
  }

  // When the user picks a district from the dropdown OR the page first
  // mounts with a default district, smoothly move the pin and fly to its bbox.
  // Runs:
  //   - on every change of selectedDistrict
  //   - on every flip of geojsonReady (so a default-selected district on a
  //     slow connection still gets its initial fly-to once the GeoJSON arrives)
  useEffect(() => {
    if (!selectedDistrict) return;
    if (!geojsonReady) return;
    flyToDistrict(selectedDistrict);
  }, [selectedDistrict, geojsonReady]);

  // Switch tile layers when activeLayer changes
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    import('leaflet').then((L) => {
      // Remove all existing tile layers from map
      map.eachLayer((lyr) => {
        if (lyr instanceof L.TileLayer) {
          map.removeLayer(lyr);
        }
      });

      const cfg = TILE_LAYERS[activeLayer];
      L.tileLayer(cfg.url, { maxZoom: 19, tileSize: 256 }).addTo(map);
      // Bring GeoJSON overlay on top
      geojsonLayerRef.current?.bringToFront();
    });
  }, [activeLayer]);

  // ----- Imperative handle: parent components can call these via ref -----
  useImperativeHandle(
    ref,
    () => ({
      flyToDistrict: (name: string) => { flyToDistrict(name); },
      flyToCountry: () => { flyToCountry(); },
    }),
    [geojsonReady]
  );

  const riskLegend: { level: RiskLevel; label: string }[] = [
    { level: 'Critical', label: 'Critical' },
    { level: 'High', label: 'High' },
    { level: 'Medium', label: 'Medium' },
    { level: 'Low', label: 'Low' },
  ];

  return (
    <div style={{ position: 'relative', height, width: '100%', borderRadius: '16px', overflow: 'hidden' }}>
      {/* Map container */}
      <div
        ref={mapContainerRef}
        style={{ height: '100%', width: '100%' }}
        aria-label="Bangladesh district flood risk map"
      />

      {hotspotDistricts.length > 0 && (
        <div style={{
          position: 'absolute', top: 58, left: 12, zIndex: 500,
          background: 'rgba(6,11,22,0.88)', borderRadius: '10px', padding: '8px 10px',
          color: 'rgba(255,255,255,0.75)', fontSize: '11px', border: '1px solid rgba(167,139,250,0.35)',
        }}>
          <span style={{ color: '#a78bfa', fontWeight: 700 }}>Dashed borders</span> = disease clusters
        </div>
      )}

      {/* Loading overlay */}
      {loadingRisks && (
        <div style={{
          position: 'absolute', inset: 0,
          background: 'rgba(6,11,22,0.7)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          zIndex: 1000,
          backdropFilter: 'blur(4px)',
        }}>
          <div style={{ color: '#fff', fontSize: '14px', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ display: 'inline-block', width: 18, height: 18, border: '2px solid #3b82f6', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
            Loading risk data…
          </div>
        </div>
      )}

      {/* Layer switcher */}
      <div style={{
        position: 'absolute', top: 12, left: 12, zIndex: 500,
        display: 'flex', gap: '6px', flexWrap: 'wrap',
      }}>
        {(Object.keys(TILE_LAYERS) as Array<keyof typeof TILE_LAYERS>).map((key) => (
          <button
            key={key}
            onClick={() => setActiveLayer(key)}
            style={{
              padding: '5px 10px',
              borderRadius: '6px',
              border: 'none',
              fontSize: '11px',
              fontWeight: 600,
              fontFamily: 'Inter, sans-serif',
              cursor: 'pointer',
              background: activeLayer === key ? '#3b82f6' : 'rgba(6,11,22,0.85)',
              color: activeLayer === key ? '#fff' : 'rgba(255,255,255,0.7)',
              backdropFilter: 'blur(8px)',
              transition: 'all 0.2s',
            }}
          >
            {TILE_LAYERS[key].label}
          </button>
        ))}
      </div>

      {/* Risk legend */}
      <div style={{
        position: 'absolute', bottom: 16, left: 12, zIndex: 500,
        background: 'rgba(6,11,22,0.88)',
        borderRadius: '10px',
        padding: '10px 14px',
        backdropFilter: 'blur(8px)',
        border: '1px solid rgba(255,255,255,0.08)',
      }}>
        <div style={{ color: 'rgba(255,255,255,0.6)', fontSize: '10px', fontWeight: 700, letterSpacing: '0.8px', marginBottom: '8px', fontFamily: 'Inter,sans-serif', textTransform: 'uppercase' }}>
          Risk Level
        </div>
        {riskLegend.map(({ level, label }) => (
          <div key={level} style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
            <div style={{
              width: 12, height: 12, borderRadius: '3px',
              background: RISK_COLORS[level],
              opacity: 0.9,
              flexShrink: 0,
            }} />
            <span style={{ color: 'rgba(255,255,255,0.8)', fontSize: '11px', fontFamily: 'Inter,sans-serif' }}>{label}</span>
          </div>
        ))}
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        .leaflet-risk-tooltip { background: transparent !important; border: none !important; box-shadow: none !important; }
        .leaflet-risk-tooltip .leaflet-tooltip-top::before,
        .leaflet-risk-tooltip .leaflet-tooltip-bottom::before { display: none !important; }
        .leaflet-control-zoom { margin-top: 50px !important; }
        .leaflet-control-zoom a {
          background: rgba(6,11,22,0.9) !important;
          color: rgba(255,255,255,0.9) !important;
          border: 1px solid rgba(255,255,255,0.12) !important;
          backdrop-filter: blur(8px);
        }
        .leaflet-control-zoom a:hover {
          background: rgba(59,130,246,0.8) !important;
        }
      `}</style>
    </div>
  );
});

export default DistrictRiskMap;
