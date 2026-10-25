'use client';

/**
 * DistrictNearestHospitals -- a 3-row "nearest hospitals" card to drop
 * into the District Detail page.  It uses the /hospitals/nearby
 * endpoint with the district's centroid (or, if the browser gave us a
 * GPS fix, the user's actual location) so the result is always
 * locally relevant.
 *
 * NOTE: this file lives under components/hospital/ rather than
 * components/cards/ so it's discoverable next to the other
 * hospital-related components.  It's a self-contained card -- no
 * extra props other than `district` are required.
 */
import { useQuery } from '@tanstack/react-query';
import { Building2, Loader2, AlertCircle, Navigation, MapPin } from 'lucide-react';
import { useMemo, useState } from 'react';
import { getNearbyHospitals, googleMapsDirectionsUrl, isOperationalHospital } from '@/lib/api';
import type { HospitalPublic, HospitalOperational, NearbyHospital } from '@/lib/types';
import { BANGLADESH_DISTRICTS, CAPACITY_COLORS } from './hospitalTheme';
import { districtCentroid, statusColor } from './hospitalHelpers';

interface Props {
  district: string;
  /** Optional user location to bias the "nearby" search. */
  userLocation?: { lat: number; lng: number } | null;
}

export default function DistrictNearestHospitals({ district, userLocation }: Props) {
  const [askingGeo, setAskingGeo] = useState(false);
  const [geoCoord, setGeoCoord] = useState<{ lat: number; lng: number } | null>(null);
  const [geoError, setGeoError] = useState<string | null>(null);

  // Prefer user GPS; fall back to district centroid.
  const origin = useMemo<{ lat: number; lng: number }>(() => {
    if (geoCoord) return geoCoord;
    if (userLocation) return userLocation;
    const c = districtCentroid(district);
    if (c) return c;
    return { lat: 23.7, lng: 90.4 }; // central Bangladesh fallback
  }, [geoCoord, userLocation, district]);

  const { data, isLoading, error } = useQuery({
    queryKey: ['nearest-hospitals', district, origin],
    queryFn: () => getNearbyHospitals({ lat: origin.lat, lng: origin.lng, radius_km: 30, limit: 3 }),
    enabled: !!origin,
  });

  const useMyLocation = () => {
    if (!('geolocation' in navigator)) {
      setGeoError('Your browser does not support geolocation.');
      return;
    }
    setAskingGeo(true);
    setGeoError(null);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setGeoCoord({ lat: pos.coords.latitude, lng: pos.coords.longitude });
        setAskingGeo(false);
      },
      (err) => {
        setGeoError(err.message);
        setAskingGeo(false);
      },
      { timeout: 8000 }
    );
  };

  return (
    <div
      className="rounded-2xl p-4 border"
      style={{ background: 'rgba(255,255,255,0.04)', borderColor: 'rgba(255,255,255,0.08)' }}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Building2 size={16} className="text-blue-300" />
          <h3 className="text-white font-semibold text-sm">Nearest hospitals</h3>
        </div>
        <button
          onClick={useMyLocation}
          disabled={askingGeo}
          className="text-[10px] inline-flex items-center gap-1 px-2 py-1 rounded-md text-blue-200 hover:text-white disabled:opacity-50"
          style={{ background: 'rgba(56,189,248,0.10)' }}
        >
          {askingGeo ? <Loader2 size={10} className="animate-spin" /> : <MapPin size={10} />}
          {askingGeo ? 'Locating…' : 'Use my location'}
        </button>
      </div>

      {geoError && (
        <p className="text-amber-300 text-[11px] mb-2">Couldn&apos;t get your location: {geoError}</p>
      )}

      {isLoading && (
        <div className="flex items-center justify-center py-6">
          <Loader2 className="text-blue-300 animate-spin" size={18} />
        </div>
      )}

      {error && (
        <p className="text-red-300 text-xs flex items-center gap-1">
          <AlertCircle size={11} /> Failed to load nearby hospitals.
        </p>
      )}

      {data && data.length === 0 && (
        <p className="text-white/50 text-xs">No hospitals within 30 km.</p>
      )}

      {data && data.length > 0 && (
        <div className="space-y-2">
          {data.map((h, i) => {
            const isOp = isOperationalHospital(h as HospitalPublic);
            const op = isOp ? (h as HospitalOperational) : null;
            return (
              <a
                key={h.id}
                href={googleMapsDirectionsUrl(h.latitude!, h.longitude!, origin.lat, origin.lng)}
                target="_blank"
                rel="noreferrer noopener"
                className="flex items-center gap-3 p-2 rounded-lg hover:bg-white/5 transition"
              >
                <div className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold text-white" style={{ background: 'rgba(56,189,248,0.18)' }}>
                  {i + 1}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-white text-xs font-semibold truncate" title={h.name}>{h.name}</p>
                  <p className="text-white/40 text-[10px] flex items-center gap-1">
                    <span style={{ color: statusColor(h.capacity_status) }}>●</span>
                    {h.capacity_status} · {h.district}
                    {op && ` · ${op.beds_total} beds`}
                  </p>
                </div>
                <div className="text-right shrink-0">
                  <div className="text-white text-xs font-bold">{h.distance_km.toFixed(1)} km</div>
                  <Navigation size={10} className="text-blue-300 ml-auto mt-0.5" />
                </div>
              </a>
            );
          })}
        </div>
      )}
    </div>
  );
}
