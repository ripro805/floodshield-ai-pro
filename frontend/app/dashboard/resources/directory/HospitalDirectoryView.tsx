'use client';

/**
 * HospitalDirectoryView -- the new "Directory" tab on the Resources page.
 *
 * Three views the user can flip between:
 *   1. National  : the 64-district overview grid (counts + capacity).
 *   2. District  : per-hospital list for the picked district, with
 *                  type / status filters and search.
 *   3. Nearby    : "Use my location" (browser geolocation) and the
 *                  sorted haversine list of the N nearest hospitals.
 *
 * The data_source flag drives the "Sample data" badge in the corner
 * of the list; we never fabricate phone numbers, so the phone field
 * is conditionally rendered (and absent for the seeded rows).
 *
 * Capacity status (Available | Limited | Full) is computed in the
 * backend and surfaced here as a colour-coded pill.
 */
import { useEffect, useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Building2, MapPin, Phone, Search, Loader2, X, AlertCircle,
  Navigation, ArrowLeft, Filter, Globe, Upload,
} from 'lucide-react';
import { motion } from 'framer-motion';
import { useAuth, getToken } from '@/lib/auth';
import HospitalImportModal from '@/components/hospital/HospitalImportModal';
import type { HospitalImportSummary } from '@/lib/api';
import {
  getDistrictsSummary, getHospitals, getNearbyHospitals,
  isOperationalHospital, googleMapsDirectionsUrl,
} from '@/lib/api';
import { CAPACITY_COLORS, BANGLADESH_DISTRICTS } from '@/components/hospital/hospitalTheme';
import { statusColor } from '@/components/hospital/hospitalHelpers';
import type {
  DistrictsSummaryResponse, DistrictHospitalSummary, CapacityStatus,
  HospitalPublic, HospitalOperational, NearbyHospital,
} from '@/lib/types';
import GlassCard from '@/components/cards/GlassCard';
import HospitalMapClient from '@/components/hospital/HospitalMapClient';
import { Map as MapIcon, Edit3, Flag, MessageSquareWarning } from 'lucide-react';
import { useQuery as useRQ } from '@tanstack/react-query';
import HospitalEditModal from '@/components/hospital/HospitalEditModal';
import HospitalIssueModal from '@/components/hospital/HospitalIssueModal';
import HospitalDetailModal from '@/components/hospital/HospitalDetailModal';
import {
  listHospitalIssues, HOSPITAL_ISSUE_CATEGORIES,
  type HospitalIssue,
} from '@/lib/api';

type View = 'national' | 'district' | 'nearby';

const STATUS_PILL: Record<CapacityStatus, string> = {
  Available: 'rgba(45,212,191,0.18)',   // teal
  Limited:   'rgba(251,191,36,0.18)',   // amber
  Full:      'rgba(244,63,94,0.18)',    // rose
  Unknown:   'rgba(148,163,184,0.18)',  // slate
};
const STATUS_TEXT: Record<CapacityStatus, string> = {
  Available: '#5EEAD4',
  Limited:   '#FCD34D',
  Full:      '#FDA4AF',
  Unknown:   '#CBD5E1',
};

function StatusPill({ status }: { status: CapacityStatus }) {
  return (
    <span
      style={{
        background: STATUS_PILL[status] ?? 'rgba(148,163,184,0.18)',
        color: STATUS_TEXT[status] ?? '#CBD5E1',
      }}
      className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold border border-white/10"
    >
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: 'currentColor' }} />
      {status}
    </span>
  );
}

function SampleDataBadge() {
  return (
    <span
      title="This row is from the synthetic seed dataset; the real coordinates and contact details will be loaded from the official registry once available."
      style={{
        background: 'rgba(56,189,248,0.12)',
        color: '#7DD3FC',
        borderColor: 'rgba(56,189,248,0.3)',
      }}
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider border"
    >
      <Globe size={9} /> Sample data
    </span>
  );
}

function HospitalCard({
  h, index, origin,
}: {
  h: HospitalPublic | HospitalOperational | NearbyHospital;
  index: number;
  origin?: { lat: number; lng: number };
}) {
  const dist = (h as NearbyHospital).distance_km ?? null;
  const isOp = isOperationalHospital(h as HospitalPublic);
  const op = isOp ? (h as HospitalOperational) : null;
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.03 }}
    >
      <div
        className="rounded-2xl p-4 border transition-all hover:border-blue-300/30"
        style={{
          background: 'rgba(255,255,255,0.04)',
          borderColor: 'rgba(255,255,255,0.08)',
        }}
      >
        <div className="flex items-start justify-between gap-2 mb-2">
          <div className="flex items-center gap-2 min-w-0">
            <Building2 size={16} className="text-blue-300 shrink-0" />
            <h3 className="text-white font-semibold text-sm truncate" title={h.name}>{h.name}</h3>
          </div>
          {dist != null && (
            <span className="text-[11px] font-bold text-blue-200 whitespace-nowrap">
              {dist.toFixed(1)} km
            </span>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-1.5 mb-2">
          <StatusPill status={h.capacity_status} />
          {h.hospital_type && (
            <span className="text-[10px] px-2 py-0.5 rounded-md bg-white/5 text-white/50 border border-white/10">
              {h.hospital_type}
            </span>
          )}
          {h.data_source === 'seed' && <SampleDataBadge />}
        </div>

        {(h.address || h.district) && (
          <p className="text-white/50 text-xs flex items-start gap-1.5 mb-2">
            <MapPin size={11} className="shrink-0 mt-0.5" />
            <span className="line-clamp-2">{[h.address, h.upazila].filter(Boolean).join(' • ') || h.district}</span>
          </p>
        )}

        {/* Operational fields (only for ops roles) */}
        {op && (
          <div className="grid grid-cols-3 gap-2 mt-3 mb-2">
            <div className="text-center py-1.5 rounded-lg bg-white/[0.04]">
              <div className="text-[9px] uppercase text-white/40 tracking-wider">Beds</div>
              <div className="text-sm font-bold text-white">{op.beds_total}</div>
            </div>
            <div className="text-center py-1.5 rounded-lg bg-white/[0.04]">
              <div className="text-[9px] uppercase text-white/40 tracking-wider">Occ%</div>
              <div className="text-sm font-bold text-white">{op.occupancy_percent.toFixed(0)}%</div>
            </div>
            <div className="text-center py-1.5 rounded-lg bg-white/[0.04]">
              <div className="text-[9px] uppercase text-white/40 tracking-wider">Doctors</div>
              <div className="text-sm font-bold text-white">{op.doctors}</div>
            </div>
          </div>
        )}

        {op && (
          <div className="grid grid-cols-3 gap-1 mb-3">
            {([
              ['ORS', op.ors_stock, op.ors_low],
              ['IV', op.iv_saline_stock, op.iv_saline_low],
              ['AB', op.antibiotics_stock, op.antibiotics_low],
            ] as const).map(([label, stock, low]) => (
              <div
                key={label}
                className="text-center py-1 rounded-md text-[10px] font-semibold"
                style={{
                  background: low ? 'rgba(244,63,94,0.12)' : 'rgba(45,212,191,0.08)',
                  color: low ? '#FDA4AF' : '#5EEAD4',
                }}
                title={low ? 'Below low-stock threshold' : 'Stocked'}
              >
                {label}: {stock}{low ? ' ⚠' : ''}
              </div>
            ))}
          </div>
        )}

        <div className="flex items-center justify-between mt-2 pt-2 border-t border-white/5">
          <div className="flex items-center gap-2 text-[10px] text-white/40">
            {h.phone ? (
              <span className="flex items-center gap-1">
                <Phone size={10} className="text-emerald-300" />
                <a href={`tel:${h.phone}`} className="hover:text-emerald-200">{h.phone}</a>
              </span>
            ) : (
              <span className="flex items-center gap-1" title="Phone not on file — call 999 for medical emergencies.">
                <Phone size={10} className="text-amber-300" />
                <span>999 for emergency</span>
              </span>
            )}
          </div>
          {h.latitude != null && h.longitude != null && (
            <a
              href={googleMapsDirectionsUrl(h.latitude, h.longitude, origin?.lat, origin?.lng)}
              target="_blank"
              rel="noreferrer noopener"
              className="inline-flex items-center gap-1 text-[10px] font-semibold text-blue-300 hover:text-blue-200"
            >
              <Navigation size={10} /> Directions
            </a>
          )}
        </div>
      </div>
    </motion.div>
  );
}

function NationalGrid({
  data, loading, error, onPickDistrict,
}: {
  data: DistrictsSummaryResponse | undefined;
  loading: boolean;
  error: string | null;
  onPickDistrict: (d: string) => void;
}) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 size={28} className="text-blue-300 animate-spin" />
      </div>
    );
  }
  if (error) {
    return (
      <GlassCard className="p-6 flex items-center gap-3">
        <AlertCircle size={18} className="text-red-400 shrink-0" />
        <span className="text-red-300 text-sm">{error}</span>
      </GlassCard>
    );
  }
  if (!data) return null;
  return (
    <div>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3">
        {data.items.map((d: DistrictHospitalSummary) => (
          <button
            key={d.district}
            onClick={() => onPickDistrict(d.district)}
            className="text-left rounded-2xl p-3 border transition-all hover:scale-[1.02] hover:border-blue-300/40"
            style={{
              background: 'rgba(255,255,255,0.04)',
              borderColor: 'rgba(255,255,255,0.08)',
            }}
          >
            <div className="flex items-center justify-between gap-1 mb-1">
              <h3 className="text-white font-semibold text-xs truncate" title={d.district}>{d.district}</h3>
              <StatusPill status={d.capacity_status} />
            </div>
            <div className="flex items-baseline gap-1.5 mt-1">
              <span className="text-white text-lg font-bold leading-none">{d.hospital_count}</span>
              <span className="text-white/40 text-[10px]">facilities</span>
            </div>
            <div className="text-white/40 text-[10px] mt-1">
              {d.total_beds.toLocaleString()} beds · {d.mean_occupancy_percent.toFixed(0)}% occ
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

function DistrictView({
  district, onBack, onSelectHospital,
}: {
  district: string;
  onBack: () => void;
  onSelectHospital: (h: HospitalPublic | HospitalOperational) => void;
}) {
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<'' | 'Available' | 'Limited' | 'Full'>('');

  const { data, isLoading, error } = useQuery({
    queryKey: ['hospitals', district, search, typeFilter, statusFilter],
    queryFn: () => getHospitals({
      district,
      q: search || undefined,
      type: typeFilter || undefined,
      status: statusFilter || undefined,
      limit: 200,
    }),
  });

  const types = useMemo(() => {
    if (!data) return [];
    const set = new Set<string>();
    data.items.forEach((h) => { if (h.hospital_type) set.add(h.hospital_type); });
    return Array.from(set).sort();
  }, [data]);

  return (
    <div>
      <button
        onClick={onBack}
        className="inline-flex items-center gap-1 text-white/60 hover:text-white text-sm mb-4"
      >
        <ArrowLeft size={14} /> Back to national overview
      </button>

      <div className="flex items-baseline justify-between mb-4">
        <h2 className="text-2xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
          {district}
        </h2>
        {data && <span className="text-white/50 text-sm">{data.total} hospital{data.total === 1 ? '' : 's'}</span>}
      </div>

      {/* Filters */}
      <GlassCard className="p-3 mb-4">
        <div className="flex flex-col md:flex-row gap-2">
          <div className="flex-1 flex items-center gap-2 px-3 py-2 rounded-xl" style={{ background: 'rgba(255,255,255,0.05)' }}>
            <Search size={14} className="text-white/40" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by name…"
              className="bg-transparent flex-1 outline-none text-white text-sm"
            />
            {search && (
              <button onClick={() => setSearch('')} aria-label="Clear search">
                <X size={14} className="text-white/40 hover:text-white" />
              </button>
            )}
          </div>
          <div className="flex items-center gap-2 px-3 py-2 rounded-xl" style={{ background: 'rgba(255,255,255,0.05)' }}>
            <Filter size={14} className="text-white/40" />
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="bg-transparent outline-none text-white text-sm"
            >
              <option value="" style={{ background: '#060B14' }}>All types</option>
              {types.map((t) => <option key={t} value={t} style={{ background: '#060B14' }}>{t}</option>)}
            </select>
          </div>
          <div className="flex items-center gap-2 px-3 py-2 rounded-xl" style={{ background: 'rgba(255,255,255,0.05)' }}>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as typeof statusFilter)}
              className="bg-transparent outline-none text-white text-sm"
            >
              <option value="" style={{ background: '#060B14' }}>All status</option>
              <option value="Available" style={{ background: '#060B14' }}>Available</option>
              <option value="Limited" style={{ background: '#060B14' }}>Limited</option>
              <option value="Full" style={{ background: '#060B14' }}>Full</option>
            </select>
          </div>
        </div>
      </GlassCard>

      {isLoading && (
        <div className="flex items-center justify-center py-12"><Loader2 className="text-blue-300 animate-spin" /></div>
      )}
      {error && (
        <GlassCard className="p-4 text-red-300 text-sm flex items-center gap-2">
          <AlertCircle size={14} /> Failed to load hospitals.
        </GlassCard>
      )}
      {data && data.items.length === 0 && (
        <GlassCard className="p-8 text-center text-white/50 text-sm">
          No hospitals match these filters.
        </GlassCard>
      )}

      {data && data.items.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {data.items.map((h, i) => (
            <div key={h.id} onClick={() => onSelectHospital(h)} className="cursor-pointer">
              <HospitalCard h={h} index={i} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function NearbyView({
  onSelectHospital,
}: {
  onSelectHospital: (h: NearbyHospital) => void;
}) {
  const [coords, setCoords] = useState<{ lat: number; lng: number } | null>(null);
  const [geoError, setGeoError] = useState<string | null>(null);
  const [asking, setAsking] = useState(false);
  const [radius, setRadius] = useState(50);

  const useMyLocation = () => {
    if (!('geolocation' in navigator)) {
      setGeoError('Your browser does not support geolocation.');
      return;
    }
    setAsking(true);
    setGeoError(null);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setCoords({ lat: pos.coords.latitude, lng: pos.coords.longitude });
        setAsking(false);
      },
      (err) => {
        setGeoError(`Could not get your location: ${err.message}. You can search a district instead.`);
        setAsking(false);
      },
      { timeout: 10000, enableHighAccuracy: false, maximumAge: 60000 }
    );
  };

  // Out-of-Bangladesh guard: if geolocation returned somewhere obviously
  // outside the BB bbox, warn the user.
  const outside = coords && (coords.lat < 20.5 || coords.lat > 26.7 || coords.lng < 88.0 || coords.lng > 92.7);

  const { data, isFetching, error } = useQuery({
    queryKey: ['nearby', coords, radius],
    queryFn: () => getNearbyHospitals({ lat: coords!.lat, lng: coords!.lng, radius_km: radius, limit: 20 }),
    enabled: !!coords && !outside,
  });

  return (
    <div>
      <GlassCard className="p-4 mb-4">
        <div className="flex flex-col md:flex-row gap-3">
          <button
            onClick={useMyLocation}
            disabled={asking}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl font-semibold text-sm text-white disabled:opacity-50"
            style={{ background: 'linear-gradient(135deg, #38BDF8, #2DD4BF)' }}
          >
            {asking ? <Loader2 size={14} className="animate-spin" /> : <Navigation size={14} />}
            {asking ? 'Asking for permission…' : 'Use my location'}
          </button>
          <div className="flex items-center gap-2 text-sm text-white/60">
            <span>Radius:</span>
            <select
              value={radius}
              onChange={(e) => setRadius(parseInt(e.target.value, 10))}
              className="px-2 py-1 rounded-lg text-sm text-white border"
              style={{ background: 'rgba(255,255,255,0.05)', borderColor: 'rgba(255,255,255,0.1)' }}
            >
              {[10, 25, 50, 100, 200].map((r) => (
                <option key={r} value={r} style={{ background: '#060B14' }}>{r} km</option>
              ))}
            </select>
          </div>
          {coords && (
            <div className="text-xs text-white/50 flex items-center gap-1">
              <MapPin size={11} /> {coords.lat.toFixed(4)}, {coords.lng.toFixed(4)}
            </div>
          )}
        </div>
        {geoError && (
          <p className="text-amber-300 text-xs mt-3 flex items-center gap-1">
            <AlertCircle size={12} /> {geoError}
          </p>
        )}
        {outside && (
          <p className="text-amber-300 text-xs mt-3 flex items-center gap-1">
            <AlertCircle size={12} /> That location is outside Bangladesh ({coords.lat.toFixed(2)}, {coords.lng.toFixed(2)}).
            Hospital data is for the 64 Bangladesh districts.
          </p>
        )}
      </GlassCard>

      {isFetching && (
        <div className="flex items-center justify-center py-12"><Loader2 className="text-blue-300 animate-spin" /></div>
      )}
      {error && (
        <GlassCard className="p-4 text-red-300 text-sm flex items-center gap-2">
          <AlertCircle size={14} /> Failed to load nearby hospitals.
        </GlassCard>
      )}
      {data && data.length === 0 && coords && !outside && (
        <GlassCard className="p-8 text-center text-white/50 text-sm">
          No hospitals within {radius} km. Try increasing the radius.
        </GlassCard>
      )}
      {data && data.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {data.map((h, i) => (
            <div key={h.id} onClick={() => onSelectHospital(h)} className="cursor-pointer">
              <HospitalCard h={h} index={i} origin={coords ?? undefined} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

interface HospitalDirectoryViewProps {
  /** If set, the Directory opens in District view for this district. */
  initialDistrict?: string;
}

export default function HospitalDirectoryView({ initialDistrict }: HospitalDirectoryViewProps = {}) {
  const [view, setView] = useState<View>(initialDistrict ? 'district' : 'national');
  const [district, setDistrict] = useState<string | null>(initialDistrict ?? null);

  // Re-sync when the prop changes (e.g. chatbot deep-link fires
  // after the component is already mounted).
  useEffect(() => {
    if (initialDistrict) {
      setDistrict(initialDistrict);
      setView('district');
    }
  }, [initialDistrict]);
  const [selected, setSelected] = useState<HospitalPublic | HospitalOperational | NearbyHospital | null>(null);
  const [importOpen, setImportOpen] = useState(false);


  const queryClient = useQueryClient();
  // Cross-component deep-link from the chatbot widget: when a
  // 'fs:open-hospital' window event fires, switch to the district
  // view, set the district, and open the matching card.
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const onOpen = async (e: Event) => {
      const ce = e as CustomEvent<{ hospital_id: string; district?: string }>;
      const hid = ce.detail?.hospital_id;
      if (!hid) return;
      // If the chatbot told us a district, switch to it first.
      const d = ce.detail?.district;
      if (d) {
        setView('district');
        setDistrict(d);
      }
      // Wait a tick so the list query refetches with the new
      // district filter before we search for the id.
      await new Promise((r) => setTimeout(r, 50));
      // Try to find the hospital in any of the in-flight queries.
      const tryOpenFromCache = () => {
        const queries = queryClient.getQueryCache().findAll({ queryKey: ['hospitals'] });
        for (const q of queries) {
          const d2 = q.state.data as any;
          const items: any[] = Array.isArray(d2) ? d2 : (d2?.items ?? []);
          const hit = items.find((x) => x.id === hid);
          if (hit) {
            setSelected(hit);
            return true;
          }
        }
        return false;
      };
      if (!tryOpenFromCache()) {
        // Fall back to a direct fetch (no district filter, we just
        // need the row by id).
        try {
          const r = await fetch(
            `${process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'}/hospitals/${hid}`,
            { headers: { Authorization: `Bearer ${getToken()}` } },
          );
          if (r.ok) {
            const row = await r.json();
            setSelected(row);
          }
        } catch (err) {
          console.warn('fs:open-hospital fetch failed', err);
        }
      }
    };
    window.addEventListener('fs:open-hospital', onOpen as EventListener);
    return () => window.removeEventListener('fs:open-hospital', onOpen as EventListener);
  }, [queryClient]);
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  // Ops roles that can edit inventory + phone/address/upazila/beds_occupied.
  const isOps = ['admin','health_worker','hospital','ngo','government'].includes(user?.role ?? '');

  // National summary query (lifetime-cached for the page session).
  const { data: summary, isLoading: summaryLoading, error: summaryError } = useQuery({
    queryKey: ['districts-summary'],
    queryFn: () => getDistrictsSummary(),
    staleTime: 60_000,
  });

  const pickDistrict = (d: string) => {
    setDistrict(d);
    setView('district');
  };

  return (
    <div>
      {/* View switcher */}
      <div className="flex items-center gap-2 mb-5 p-1 rounded-xl border" style={{ background: 'rgba(255,255,255,0.04)', borderColor: 'rgba(255,255,255,0.08)' }}>
        {(['national', 'district', 'nearby'] as const).map((v) => (
          <button
            key={v}
            onClick={() => {
              if (v === 'national') { setDistrict(null); }
              setView(v);
            }}
            className={`flex-1 px-3 py-2 rounded-lg text-sm font-semibold transition ${
              view === v ? 'bg-blue-500/20 text-blue-200' : 'text-white/60 hover:text-white'
            }`}
          >
            {v === 'national' ? 'National overview' : v === 'district' ? 'District view' : 'Find near me'}
          </button>
        ))}
      </div>

      {view === 'national' && (
        <>
          {district && (
            <button
              onClick={() => { setDistrict(null); setView('national'); }}
              className="inline-flex items-center gap-1 text-white/60 hover:text-white text-sm mb-4"
            >
              <ArrowLeft size={14} /> Back
            </button>
          )}
          <div className="flex items-start justify-between gap-3 mb-1">
            <h2 className="text-xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
              Hospital resources across Bangladesh
            </h2>
            {isAdmin && (
              <button
                onClick={() => setImportOpen(true)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-white border border-white/10 hover:border-blue-300/40 shrink-0"
                style={{ background: 'rgba(255,255,255,0.04)' }}
                title="Admin: import a fresh CSV to replace the directory"
              >
                <Upload size={12} /> Import CSV
              </button>
            )}
          </div>
          <p className="text-white/50 text-sm mb-4">
            Click any district to see its facilities, capacity, and low-stock flags.
            {summary && ` ${summary.total_districts} districts covered.`}
          </p>
          <NationalGrid
            data={summary}
            loading={summaryLoading}
            error={summaryError ? 'Failed to load district summary.' : null}
            onPickDistrict={pickDistrict}
          />
        </>
      )}

      {view === 'district' && district && (
        <DistrictView
          district={district}
          onBack={() => { setDistrict(null); setView('national'); }}
          onSelectHospital={setSelected}
        />
      )}

      {view === 'nearby' && (
        <NearbyView onSelectHospital={(h) => setSelected(h as NearbyHospital)} />
      )}

      {/* Admin CSV import modal (only mounted for admins but the
          route is admin-only too, so a non-admin wouldn't reach the
          success state regardless) */}
      {isAdmin && (
        <HospitalImportModal
          open={importOpen}
          onClose={() => setImportOpen(false)}
          onImported={(_s: HospitalImportSummary) => {
            // Refresh every directory-related query so the new rows
            // are visible immediately.
            queryClient.invalidateQueries({ queryKey: ['districts-summary'] });
            queryClient.invalidateQueries({ queryKey: ['hospitals'] });
          }}
        />
      )}

      {/* Detail modal */}
      {selected && (
        <HospitalDetailModal
          selected={selected}
          onClose={() => setSelected(null)}
          isOps={isOps}
          isAdmin={isAdmin}
        />
      )}
    </div>
  );
}
