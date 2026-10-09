'use client';

/**
 * HospitalDetailModal -- the "view one hospital" experience on the
 * Directory.  Wraps the existing HospitalCard (the same tile that
 * shows up in the list) with two new affordances:
 *
 *   - "Edit" (ops only)   -- opens HospitalEditModal so an ops
 *     user can fix inventory, phone, address, etc.  Hidden for
 *     citizens.
 *   - "Report issue" (any auth'd user) -- opens HospitalIssueModal
 *     so a citizen can flag a wrong phone number, closed
 *     facility, etc.
 *
 * Below the card is a "Recent reports" panel that lists the most
 * recent issues for this hospital.  Both the panel and the issue
 * modal re-fetch on successful submit so the user can immediately
 * see their report at the top of the list.
 */
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Edit3, Flag, Loader2, AlertCircle, MessageSquareWarning, History, CheckCircle2, Clock, XCircle, MessageCirclePlus } from 'lucide-react';
import { listHospitalIssues, getHospitalIssueHistory, HOSPITAL_ISSUE_CATEGORIES } from '@/lib/api';
import type { HospitalIssueHistoryEvent } from '@/lib/api';
import type {
  HospitalPublic, HospitalOperational, NearbyHospital,
} from '@/lib/types';
import { isOperationalHospital } from '@/lib/api';
import HospitalEditModal from './HospitalEditModal';
import HospitalIssueModal from './HospitalIssueModal';

interface Props {
  selected: HospitalPublic | HospitalOperational | NearbyHospital;
  onClose: () => void;
  isOps: boolean;
  isAdmin: boolean;
}

export default function HospitalDetailModal({ selected, onClose, isOps }: Props) {
  const [editOpen, setEditOpen] = useState(false);
  const [reportOpen, setReportOpen] = useState(false);

  // Pull the operational-shaped card so we can pass it to the edit
  // modal.  In practice, if the user can see the edit button they're
  // already an ops role and the response shape is operational.
  const isOp = isOperationalHospital(selected as HospitalPublic);
  const op = isOp ? (selected as HospitalOperational) : null;

  // Recent reports for this hospital.  We re-fetch on modal mount
  // (the queryKey includes `selected.id` so opening a different
  // hospital triggers a fresh request).
  const issues = useQuery({
    queryKey: ['hospital-issues', selected.id],
    queryFn: () => listHospitalIssues(selected.id, { status: 'open' }),
    enabled: !!selected.id,
    staleTime: 30_000,
  });

  // Per-hospital issue timeline.  Distinct from `issues` above: the
  // timeline surfaces every event (reported, ack, resolved, dismissed)
  // for this hospital in one merged, newest-first stream so admins and
  // ops can see the full audit log without joining tables client-side.
  const history = useQuery({
    queryKey: ['hospital-issue-history', selected.id],
    queryFn: () => getHospitalIssueHistory(selected.id, 200),
    enabled: !!selected.id,
    staleTime: 30_000,
  });

  // Event-kind -> (icon, tone) for the timeline pills.
  const KIND_META: Record<HospitalIssueHistoryEvent['kind'], { label: string; tone: string; icon: React.ReactNode }> = {
    reported:  { label: 'Reported',  tone: '#F59E0B', icon: <MessageCirclePlus size={12} /> },
    ack:       { label: 'Acknowledged', tone: '#38BDF8', icon: <Clock size={12} /> },
    resolved:  { label: 'Resolved',  tone: '#34D399', icon: <CheckCircle2 size={12} /> },
    dismissed: { label: 'Dismissed', tone: '#94A3B8', icon: <XCircle size={12} /> },
  };

  const renderTimeline = () => {
    if (history.isLoading) {
      return (
        <div className="flex items-center gap-2 text-white/50 text-xs py-1">
          <Loader2 size={12} className="animate-spin" /> Loading timeline…
        </div>
      );
    }
    if (history.isError) {
      return (
        <p className="text-amber-300 text-xs flex items-center gap-1">
          <AlertCircle size={12} /> Could not load history.
        </p>
      );
    }
    const events = (history.data?.events || []).slice(0, 8);
    if (events.length === 0) {
      return (
        <p className="text-white/40 text-xs py-1">No history yet.</p>
      );
    }
    return (
      <ul className="space-y-1">
        {events.map((e, idx) => {
          const meta = KIND_META[e.kind] || KIND_META.reported;
          return (
            <li
              key={`${e.issue_id}-${e.kind}-${idx}`}
              className="flex items-start gap-2 text-[11px]"
            >
              <span
                className="mt-0.5 inline-flex items-center gap-1 rounded-full px-1.5 py-0.5"
                style={{ background: `${meta.tone}22`, color: meta.tone }}
              >
                {meta.icon}
                {meta.label}
              </span>
              <span className="text-white/60 leading-snug">
                {e.kind === 'reported' ? (
                  <>
                    <span className="text-white/80">{labelFor(e.category)}</span>
                    {e.description && (
                      <span className="text-white/50"> · {e.description.slice(0, 60)}{e.description.length > 60 ? '…' : ''}</span>
                    )}
                  </>
                ) : (
                  <span className="text-white/50">by admin</span>
                )}
              </span>
              <span className="ml-auto text-white/30 whitespace-nowrap">
                {e.at ? new Date(e.at).toLocaleDateString() : ''}
              </span>
            </li>
          );
        })}
        {history.data && history.data.total > events.length && (
          <li className="text-white/30 text-[10px] pt-0.5">
            +{history.data.total - events.length} more event{history.data.total - events.length === 1 ? '' : 's'} on this hospital
          </li>
        )}
      </ul>
    );
  };

  const labelFor = (cat: string) =>
    HOSPITAL_ISSUE_CATEGORIES.find((c) => c.value === cat)?.label ?? cat;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)' }}
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="max-w-md w-full max-h-[90vh] overflow-y-auto"
      >
        {/* The existing list-style card.  We re-mount it on a new
            hospital selection by keying on `selected.id`. */}
        <DetailCard selected={selected} key={selected.id} />

        {/* Action row */}
        <div className="mt-3 grid grid-cols-2 gap-2">
          {isOps && op && (
            <button
              onClick={() => setEditOpen(true)}
              className="inline-flex items-center justify-center gap-1.5 py-2 rounded-xl text-sm font-semibold text-white"
              style={{ background: 'linear-gradient(135deg, #38BDF8, #2DD4BF)' }}
            >
              <Edit3 size={14} /> Edit
            </button>
          )}
          <button
            onClick={() => setReportOpen(true)}
            className={`inline-flex items-center justify-center gap-1.5 py-2 rounded-xl text-sm font-semibold text-white border ${
              isOps ? 'border-white/10' : 'col-span-2'
            }`}
            style={{ background: 'rgba(255,255,255,0.06)' }}
          >
            <Flag size={14} /> Report issue
          </button>
        </div>

        {/* Recent reports panel */}
        <div
          className="mt-3 rounded-2xl border p-3"
          style={{ background: 'rgba(255,255,255,0.03)', borderColor: 'rgba(255,255,255,0.08)' }}
        >
          <h4 className="text-[11px] uppercase tracking-wider text-white/50 flex items-center gap-1 mb-2">
            <MessageSquareWarning size={12} /> Recent reports
          </h4>
          {issues.isLoading && (
            <div className="flex items-center gap-2 text-white/50 text-xs py-2">
              <Loader2 size={12} className="animate-spin" /> Loading…
            </div>
          )}
          {issues.isError && (
            <p className="text-amber-300 text-xs flex items-center gap-1">
              <AlertCircle size={12} /> Could not load recent reports.
            </p>
          )}
          {issues.data && issues.data.length === 0 && (
            <p className="text-white/40 text-xs py-1">No open reports for this hospital.</p>
          )}
          {issues.data && issues.data.length > 0 && (
            <ul className="space-y-1.5">
              {issues.data.slice(0, 5).map((r) => (
                <li
                  key={r.id}
                  className="rounded-lg p-2"
                  style={{ background: 'rgba(255,255,255,0.04)' }}
                >
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-white/90 text-xs font-semibold">
                      {labelFor(r.category)}
                    </p>
                    <p className="text-white/30 text-[10px]">
                      {r.created_at?.slice(0, 10) ?? ''}
                    </p>
                  </div>
                  <p className="text-white/60 text-[11px] mt-0.5 line-clamp-2">{r.description}</p>
                  {r.reporter_role && (
                    <p className="text-white/30 text-[10px] mt-0.5">by {r.reporter_role}</p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Issue history timeline -- merges reported / ack / resolved /
            dismissed events into one newest-first stream so an operator
            can audit who changed what on this hospital. */}
        <div
          className="mt-3 rounded-2xl border p-3"
          style={{ background: 'rgba(255,255,255,0.03)', borderColor: 'rgba(255,255,255,0.08)' }}
          data-testid="hospital-issue-history"
        >
          <h4 className="text-[11px] uppercase tracking-wider text-white/50 flex items-center gap-1.5 mb-1.5">
            <History size={11} /> Issue history
          </h4>
          {renderTimeline()}
        </div>

        <button
          onClick={onClose}
          className="mt-3 w-full py-2 rounded-xl text-sm font-semibold text-white/80 hover:text-white"
          style={{ background: 'rgba(255,255,255,0.06)' }}
        >
          Close
        </button>

        {/* Sub-modals (only mounted on open) */}
        {op && (
          <HospitalEditModal
            hospital={op}
            open={editOpen}
            onClose={() => setEditOpen(false)}
          />
        )}
        <HospitalIssueModal
          hospitalId={selected.id}
          hospitalName={selected.name}
          open={reportOpen}
          onClose={() => setReportOpen(false)}
          onCreated={() => issues.refetch()}
        />
      </div>
    </div>
  );
}

// Re-implement the list-card layout here (instead of importing
// HospitalCard) so we can keep the modal self-contained.  The list
// view continues to use the original HospitalCard.
import { motion } from 'framer-motion';
import { Building2, MapPin, Phone, Navigation, X } from 'lucide-react';
import GlassCard from '@/components/cards/GlassCard';
import { statusColor } from '@/components/hospital/hospitalHelpers';
import { googleMapsDirectionsUrl } from '@/lib/api';

function DetailCard({
  selected,
}: {
  selected: HospitalPublic | HospitalOperational | NearbyHospital;
}) {
  const isOp = isOperationalHospital(selected as HospitalPublic);
  const op = isOp ? (selected as HospitalOperational) : null;
  const dist = (selected as NearbyHospital).distance_km ?? null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
    >
      <GlassCard className="p-5">
        <div className="flex items-start justify-between gap-2 mb-1">
          <div className="flex items-center gap-2">
            <Building2 size={18} className="text-blue-300" />
            <h3 className="text-lg font-bold text-white">{selected.name}</h3>
          </div>
          <span
            className="text-[10px] px-2 py-0.5 rounded-md"
            style={{ color: statusColor(selected.capacity_status) }}
          >
            {selected.capacity_status}
          </span>
        </div>

        <div className="flex items-center gap-2 mb-2">
          {selected.hospital_type && (
            <span className="text-[10px] px-2 py-0.5 rounded-md bg-white/5 text-white/50 border border-white/10">
              {selected.hospital_type}
            </span>
          )}
          {selected.data_source === 'seed' && (
            <span className="text-[10px] px-2 py-0.5 rounded-md bg-amber-500/10 text-amber-300 border border-amber-500/20">
              Sample data
            </span>
          )}
        </div>

        {(selected.address || selected.district) && (
          <p className="text-white/70 text-sm flex items-start gap-1.5 mb-2">
            <MapPin size={12} className="shrink-0 mt-0.5" />
            <span>{[selected.address, selected.upazila].filter(Boolean).join(' • ') || selected.district}</span>
          </p>
        )}

        {op && (
          <div className="grid grid-cols-3 gap-2 my-3">
            <div className="text-center py-1.5 rounded-lg bg-white/[0.04]">
              <div className="text-[9px] uppercase text-white/40 tracking-wider">Beds</div>
              <div className="text-sm font-bold text-white">{op.beds_total}</div>
            </div>
            <div className="text-center py-1.5 rounded-lg bg-white/[0.04]">
              <div className="text-[9px] uppercase text-white/40 tracking-wider">Occupied</div>
              <div className="text-sm font-bold text-white">
                {op.beds_occupied ?? '—'}
              </div>
            </div>
            <div className="text-center py-1.5 rounded-lg bg-white/[0.04]">
              <div className="text-[9px] uppercase text-white/40 tracking-wider">Occ %</div>
              <div className="text-sm font-bold text-white">{op.occupancy_percent.toFixed(1)}%</div>
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
              >
                {label}: {stock}{low ? ' ⚠' : ''}
              </div>
            ))}
          </div>
        )}

        <div className="flex items-center justify-between text-[11px] text-white/60">
          {selected.phone ? (
            <span className="flex items-center gap-1">
              <Phone size={10} /> {selected.phone}
            </span>
          ) : (
            <span className="flex items-center gap-1" title="Phone not on file — call 999 for medical emergencies.">
              <Phone size={10} className="text-amber-300" />
              <span>999 for emergency</span>
            </span>
          )}
          {dist != null && (
            <span className="font-mono">{dist.toFixed(1)} km</span>
          )}
        </div>

        {selected.latitude != null && selected.longitude != null && (
          <a
            href={googleMapsDirectionsUrl(selected.latitude, selected.longitude)}
            target="_blank"
            rel="noreferrer noopener"
            className="mt-2 inline-flex items-center gap-1 text-[10px] font-semibold text-blue-300 hover:text-blue-200"
          >
            <Navigation size={10} /> Get directions
          </a>
        )}
      </GlassCard>
    </motion.div>
  );
}
