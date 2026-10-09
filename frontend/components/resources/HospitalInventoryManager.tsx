'use client';

import { useEffect, useMemo, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuth } from '@/lib/auth';
import {
  listHospitals,
  updateHospitalInventory,
  getHospitalHistory,
} from '@/lib/api';
import { getApiErrorMessage } from '@/lib/api';
import type {
  HospitalRecord,
  HospitalUpdateHistoryResponse,
  HospitalUpdateHistoryItem,
} from '@/lib/types';
import { BANGLADESH_DISTRICTS } from '@/lib/types';
import {
  Hospital, Edit3, Save, X, RefreshCw, Search,
  CheckCircle, AlertCircle, Pill, Stethoscope, Bed,
  History, Clock, UserCircle2, ChevronRight, ArrowRight,
} from 'lucide-react';
import GlassCard from '@/components/cards/GlassCard';

// Wire field keys. The directory router returns the operational payload
// with `beds_total` (the user-facing "Beds" column), while the inventory
// PATCH endpoint takes `beds` (the column name on the Hospital row). We
// store the *read* key in `readKey` and the *write* key in `writeKey`.
// When the two are identical (every other field), only `key` is set.
const FIELDS = [
  { key: 'beds', readKey: 'beds_total', writeKey: 'beds', label: 'Beds', icon: Bed, color: '#38BDF8' },
  { key: 'doctors', label: 'Doctors', icon: Stethoscope, color: '#2DD4BF' },
  { key: 'nurses', label: 'Nurses', icon: Stethoscope, color: '#818CF8' },
  { key: 'ors_stock', label: 'ORS stock', icon: Pill, color: '#FBBF24' },
  { key: 'iv_saline_stock', label: 'IV saline', icon: Pill, color: '#FB923C' },
  { key: 'antibiotics_stock', label: 'Antibiotics', icon: Pill, color: '#F43F5E' },
  { key: 'occupancy_percent', label: 'Occupancy %', icon: Hospital, color: '#A78BFA' },
] as const;

// Safe formatter used by the read-only tile.  Treats null / undefined /
// NaN as "—" instead of crashing the render.  Without this guard a single
// missing field on any hospital row throws
// `Cannot read properties of undefined (reading 'toLocaleString')` from
// line 386 of the previous fix and unmounts the whole page.
function formatFieldValue(raw: unknown, opts: { percent?: boolean } = {}): string {
  if (raw === null || raw === undefined || raw === '') return '—';
  const n = typeof raw === 'number' ? raw : Number(raw);
  if (!Number.isFinite(n)) return '—';
  if (opts.percent) return `${n.toFixed(1)}%`;
  return n.toLocaleString();
}

type FieldKey = typeof FIELDS[number]['key'];

// Resolve the wire key to use when *reading* a field off a hospital
// record.  Default = the field's own `key`; the Beds row overrides to
// `beds_total` because that's what /hospitals returns today.
function readKeyOf(f: (typeof FIELDS)[number]): string {
  return (f as { readKey?: string }).readKey ?? f.key;
}

// Resolve the wire key to use when *writing* (PATCH) a field.  Default
// = the field's own `key`; the Beds row overrides to `beds` to match the
// HospitalInventoryPatch pydantic schema (column name on the row).
function writeKeyOf(f: (typeof FIELDS)[number]): string {
  return (f as { writeKey?: string }).writeKey ?? f.key;
}

function timeAgo(iso: string | null): string {
  if (!iso) return 'never';
  const then = new Date(iso).getTime();
  const diff = Date.now() - then;
  if (diff < 60_000) return 'just now';
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} min ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)} h ago`;
  const days = Math.floor(diff / 86_400_000);
  if (days < 30) return `${days} d ago`;
  return new Date(iso).toLocaleDateString();
}

export default function HospitalInventoryManager() {
  const { user } = useAuth();
  const [district, setDistrict] = useState<string>(user?.district || 'Dhaka');
  const [hospitals, setHospitals] = useState<HospitalRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState<Partial<Record<FieldKey, number | string>>>({});
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);
  const [lastAggregate, setLastAggregate] = useState<Record<string, unknown> | null>(null);

  // History modal state (Gap A)
  const [historyFor, setHistoryFor] = useState<HospitalRecord | null>(null);
  const [historyData, setHistoryData] = useState<HospitalUpdateHistoryResponse | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyErr, setHistoryErr] = useState<string | null>(null);

  const load = useCallback(async (d: string) => {
    setLoading(true); setErr(null);
    try {
      const rows = await listHospitals({ district: d, limit: 200 });
      setHospitals(rows);
    } catch (e) {
      setErr(getApiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(district); }, [load, district]);

  const startEdit = (h: HospitalRecord) => {
    setEditing(h.id);
    // Pre-fill the edit form by *reading* from the wire shape (beds_total
    // for Beds, not `beds`).  The form-state keys stay aligned with the
    // field key in FIELDS, not the wire key, so the inputs render the
    // value the user sees on the tile.
    const d: Record<string, number | undefined> = {};
    for (const f of FIELDS) {
      const v = h[readKeyOf(f) as keyof HospitalRecord] as number | undefined;
      d[f.key] = v;
    }
    setDraft(d as Record<FieldKey, number>);
  };

  const cancelEdit = () => {
    setEditing(null);
    setDraft({});
  };

  const save = async (h: HospitalRecord) => {
    setSaving(true); setErr(null);
    try {
      const patch: Record<string, number> = {};
      for (const f of FIELDS) {
        const wkey = writeKeyOf(f);
        const raw = draft[f.key];
        if (raw === undefined || raw === '' || raw === null) continue;
        const n = Number(raw);
        if (Number.isNaN(n)) {
          throw new Error(`Field "${f.label}" must be a number`);
        }
        if (f.key === 'occupancy_percent' && (n < 0 || n > 100)) {
          throw new Error('Occupancy must be between 0 and 100');
        }
        if (f.key !== 'occupancy_percent' && n < 0) {
          throw new Error(`Field "${f.label}" cannot be negative`);
        }
        const current = h[readKeyOf(f) as keyof HospitalRecord] as number | undefined;
        if (current !== undefined && n !== current) {
          patch[wkey] = n;
        }
      }
      if (Object.keys(patch).length === 0) {
        cancelEdit();
        return;
      }
      const result = await updateHospitalInventory(h.id, patch);
      setLastAggregate(result.district_aggregate);
      setSuccess(
        `${h.name}: ${result.changed_fields?.join(', ') || 'updated'}; ` +
        `audit id ${String(result.audit_id).slice(0, 8)}… recorded.`
      );
      setTimeout(() => setSuccess(null), 4500);
      cancelEdit();
      await load(district);
    } catch (e) {
      setErr(getApiErrorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  const openHistory = async (h: HospitalRecord) => {
    setHistoryFor(h);
    setHistoryData(null);
    setHistoryErr(null);
    setHistoryLoading(true);
    try {
      setHistoryData(await getHospitalHistory(h.id, 20));
    } catch (e) {
      setHistoryErr(getApiErrorMessage(e));
    } finally {
      setHistoryLoading(false);
    }
  };

  const totalStock = useMemo(() => {
    // Read off the *wire* shape: `beds_total` (not `beds`) on the read
    // side, even though the PATCH write side uses `beds`.  Treat
    // null/undefined as 0 so a missing value never poisons the sum.
    return hospitals.reduce(
      (acc, h) => ({
        beds: acc.beds + (h.beds_total ?? 0),
        doctors: acc.doctors + (h.doctors ?? 0),
        ors: acc.ors + (h.ors_stock ?? 0),
        iv: acc.iv + (h.iv_saline_stock ?? 0),
        antibiotics: acc.antibiotics + (h.antibiotics_stock ?? 0),
      }),
      { beds: 0, doctors: 0, ors: 0, iv: 0, antibiotics: 0 }
    );
  }, [hospitals]);

  const canEditDistrict = !user
    || user.role === 'admin'
    || user.role === 'government'
    || (user.district && user.district === district);

  return (
    <div className="space-y-5">
      <GlassCard className="p-5">
        <div className="flex items-center gap-3 mb-4">
          <Hospital size={18} className="text-blue-400" />
          <div>
            <h2 className="text-lg font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
              Hospital stock & inventory
            </h2>
            <p className="text-white/40 text-sm">
              Pick a district, edit any facility's stock, and the district rollup is recomputed automatically. Every edit is logged.
            </p>
          </div>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <label className="block text-[11px] font-semibold text-white/50 uppercase tracking-wider mb-1.5">
              District
            </label>
            <div className="relative">
              <select
                value={district}
                onChange={(e) => { setDistrict(e.target.value); cancelEdit(); }}
                className="w-full pl-9 pr-3 py-2.5 rounded-xl text-sm text-white border focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
                style={{ background: 'rgba(255,255,255,0.05)', borderColor: 'rgba(255,255,255,0.1)' }}
              >
                {BANGLADESH_DISTRICTS.map((d) => (
                  <option key={d} value={d} style={{ background: '#060B14' }}>{d}</option>
                ))}
              </select>
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-white/40" />
            </div>
          </div>
          <div className="sm:col-span-2 flex items-end justify-end">
            <button
              onClick={() => load(district)}
              disabled={loading}
              className="px-4 py-2.5 rounded-xl text-sm font-semibold text-white flex items-center gap-2 disabled:opacity-50"
              style={{ background: 'rgba(59,130,246,0.18)', border: '1px solid rgba(59,130,246,0.35)' }}
            >
              <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
              {loading ? 'Loading…' : `Refresh (${hospitals.length})`}
            </button>
          </div>
        </div>

        {!canEditDistrict && (
          <div className="mt-3 p-3 rounded-lg flex items-start gap-2"
            style={{ background: 'rgba(251,191,36,0.08)', border: '1px solid rgba(251,191,36,0.25)' }}>
            <AlertCircle size={14} className="text-amber-400 mt-0.5 shrink-0" />
            <p className="text-amber-200/80 text-xs">
              Your account is registered to <strong>{user?.district ?? 'no district'}</strong>.
              You can view hospitals in other districts but only edit your own.
            </p>
          </div>
        )}
      </GlassCard>

      {lastAggregate && (
        <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
          <GlassCard className="p-4 flex flex-wrap items-center gap-4"
            style={{ background: 'rgba(45,212,191,0.06)', borderColor: 'rgba(45,212,191,0.25)' }}>
            <CheckCircle size={16} className="text-teal-400 shrink-0" />
            <div className="text-xs text-teal-200/80 mr-2">
              <strong className="text-teal-200">District rollup refreshed:</strong>
            </div>
            <div className="flex flex-wrap gap-3 text-xs text-white/80">
              <span><strong>{String(lastAggregate.hospital_count ?? '—')}</strong> hospitals</span>
              <span><strong>{String(lastAggregate.beds ?? 0)}</strong> beds</span>
              <span><strong>{String(lastAggregate.doctors ?? 0)}</strong> doctors</span>
              <span><strong>{String(lastAggregate.ors_stock ?? 0)}</strong> ORS</span>
              <span><strong>{String(lastAggregate.iv_saline_stock ?? 0)}</strong> IV</span>
              <span><strong>{String(lastAggregate.antibiotics_stock ?? 0)}</strong> antibiotics</span>
              <span>occ <strong>{String(lastAggregate.occupancy_percent ?? 0)}%</strong></span>
            </div>
          </GlassCard>
        </motion.div>
      )}

      {success && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <GlassCard className="p-3 flex items-center gap-2"
            style={{ background: 'rgba(45,212,191,0.06)', borderColor: 'rgba(45,212,191,0.2)' }}>
            <CheckCircle size={14} className="text-teal-400" />
            <p className="text-teal-200 text-sm">{success}</p>
          </GlassCard>
        </motion.div>
      )}

      {err && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <GlassCard className="p-3 flex items-center gap-2"
            style={{ background: 'rgba(244,63,94,0.08)', borderColor: 'rgba(244,63,94,0.2)' }}>
            <AlertCircle size={14} className="text-red-400 shrink-0" />
            <p className="text-red-200 text-sm">{err}</p>
          </GlassCard>
        </motion.div>
      )}

      {hospitals.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          {[
            { label: 'Beds', value: totalStock.beds, color: '#38BDF8' },
            { label: 'Doctors', value: totalStock.doctors, color: '#2DD4BF' },
            { label: 'ORS', value: totalStock.ors, color: '#FBBF24' },
            { label: 'IV saline', value: totalStock.iv, color: '#FB923C' },
            { label: 'Antibiotics', value: totalStock.antibiotics, color: '#F43F5E' },
          ].map((s) => (
            <GlassCard key={s.label} className="p-3">
              <div style={{ color: s.color, fontSize: 22, fontWeight: 800, fontFamily: 'JetBrains Mono, monospace' }}>
                {s.value}
              </div>
              <div className="text-white/50 text-xs">{s.label} ({hospitals.length} facilities)</div>
            </GlassCard>
          ))}
        </div>
      )}

      {loading ? (
        <GlassCard className="p-12 flex items-center justify-center gap-2 text-white/50">
          <RefreshCw size={16} className="animate-spin" /> Loading hospitals…
        </GlassCard>
      ) : hospitals.length === 0 ? (
        <GlassCard className="p-12 text-center text-white/40">
          No hospitals registered for {district}.
        </GlassCard>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {hospitals.map((h) => {
            const isEditing = editing === h.id;
            const isMine = h.last_edited_by_id && user?.id && h.last_edited_by_id === user.id;
            return (
              <GlassCard key={h.id} className="p-4">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <div className="text-white font-semibold text-sm" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
                      {h.name}
                    </div>
                    <div className="text-white/40 text-xs mt-0.5">
                      {h.hospital_type ?? '—'} · {h.district}
                    </div>
                  </div>
                  {isEditing ? (
                    <div className="flex gap-1">
                      <button
                        onClick={() => save(h)}
                        disabled={saving}
                        className="px-2.5 py-1.5 rounded-md text-[11px] font-semibold text-teal-200 flex items-center gap-1 disabled:opacity-50"
                        style={{ background: 'rgba(45,212,191,0.15)', border: '1px solid rgba(45,212,191,0.3)' }}
                      >
                        {saving ? <RefreshCw size={11} className="animate-spin" /> : <Save size={11} />}
                        Save
                      </button>
                      <button
                        onClick={cancelEdit}
                        disabled={saving}
                        className="px-2.5 py-1.5 rounded-md text-[11px] font-semibold text-white/70 flex items-center gap-1"
                        style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)' }}
                      >
                        <X size={11} /> Cancel
                      </button>
                    </div>
                  ) : (
                    <div className="flex gap-1">
                      <button
                        onClick={() => openHistory(h)}
                        title="View edit history"
                        className="px-2.5 py-1.5 rounded-md text-[11px] font-semibold text-purple-200 flex items-center gap-1"
                        style={{ background: 'rgba(168,85,247,0.12)', border: '1px solid rgba(168,85,247,0.3)' }}
                      >
                        <History size={11} /> History
                      </button>
                      <button
                        onClick={() => startEdit(h)}
                        disabled={!canEditDistrict}
                        title={!canEditDistrict ? 'You can only edit hospitals in your registered district' : 'Edit stock'}
                        className="px-2.5 py-1.5 rounded-md text-[11px] font-semibold text-blue-200 flex items-center gap-1 disabled:opacity-30"
                        style={{ background: 'rgba(59,130,246,0.15)', border: '1px solid rgba(59,130,246,0.3)' }}
                      >
                        <Edit3 size={11} /> Edit
                      </button>
                    </div>
                  )}
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  {FIELDS.map((f) => {
                    const Icon = f.icon;
                    const rkey = readKeyOf(f);
                    const current = h[rkey as keyof HospitalRecord] as number | undefined;
                    const draftValue = draft[f.key];
                    return (
                      <div
                        key={f.key}
                        className="px-2.5 py-2 rounded-md"
                        style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}
                      >
                        <div className="flex items-center gap-1.5 mb-0.5">
                          <Icon size={11} style={{ color: f.color }} />
                          <span className="text-[10px] text-white/50 uppercase tracking-wider font-semibold">
                            {f.label}
                          </span>
                        </div>
                        {isEditing ? (
                          <input
                            type="number"
                            value={draftValue === undefined ? '' : String(draftValue)}
                            onChange={(e) => setDraft((d) => ({ ...d, [f.key]: e.target.value }))}
                            min={0}
                            max={f.key === 'occupancy_percent' ? 100 : undefined}
                            step={f.key === 'occupancy_percent' ? 0.1 : 1}
                            className="w-full bg-transparent text-white text-sm font-semibold outline-none border-b border-white/10 focus:border-blue-400"
                          />
                        ) : (
                          <div className="text-white text-sm font-semibold" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
                            {formatFieldValue(current, { percent: f.key === 'occupancy_percent' })}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>

                {/* Gap A: audit footer */}
                <div
                  className="mt-3 pt-3 flex items-center gap-2 text-[11px] text-white/45"
                  style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}
                >
                  <Clock size={11} className="opacity-60" />
                  {h.last_edited_at ? (
                    <>
                      <span>
                        Last edited <span className="text-white/65">{timeAgo(h.last_edited_at)}</span>
                      </span>
                      <span>·</span>
                      <span className={isMine ? 'text-teal-300' : 'text-white/55'}>
                        {isMine ? 'by you' : 'by another editor'}
                      </span>
                      <button
                        onClick={() => openHistory(h)}
                        className="ml-auto text-purple-300 hover:text-purple-200 flex items-center gap-1"
                      >
                        View log <ChevronRight size={11} />
                      </button>
                    </>
                  ) : (
                    <span>No edit history yet</span>
                  )}
                </div>
              </GlassCard>
            );
          })}
        </div>
      )}

      {/* History modal */}
      <AnimatePresence>
        {historyFor && (
          <HistoryModal
            hospital={historyFor}
            data={historyData}
            loading={historyLoading}
            err={historyErr}
            onClose={() => setHistoryFor(null)}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

function HistoryModal({ hospital, data, loading, err, onClose }: {
  hospital: HospitalRecord;
  data: HospitalUpdateHistoryResponse | null;
  loading: boolean;
  err: string | null;
  onClose: () => void;
}) {
  return (
    <div
      role="dialog"
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        zIndex: 50, padding: 16,
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        style={{ width: '100%', maxWidth: 720, maxHeight: '90vh', overflowY: 'auto' }}
      >
        <GlassCard className="p-6">
          <div className="flex items-start justify-between mb-4">
            <div>
              <h3 className="text-white text-lg font-bold" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
                {hospital.name} — edit history
              </h3>
              <p className="text-white/50 text-xs mt-0.5">
                {hospital.district} · audit log (last 20 changes)
              </p>
            </div>
            <button
              onClick={onClose}
              style={{ color: 'rgba(255,255,255,0.5)', cursor: 'pointer', background: 'none', border: 'none' }}
              aria-label="Close history"
            >
              <X size={18} />
            </button>
          </div>

          {loading && (
            <div className="flex items-center gap-2 text-white/50 py-6">
              <RefreshCw size={14} className="animate-spin" /> Loading audit log…
            </div>
          )}

          {err && (
            <div className="p-3 rounded-lg flex items-center gap-2"
              style={{ background: 'rgba(244,63,94,0.08)', border: '1px solid rgba(244,63,94,0.2)' }}>
              <AlertCircle size={14} className="text-red-400" />
              <p className="text-red-200 text-sm">{err}</p>
            </div>
          )}

          {data && (
            <>
              <div className="mb-3 p-3 rounded-lg text-xs flex items-center gap-2"
                style={{ background: 'rgba(56,189,248,0.06)', border: '1px solid rgba(56,189,248,0.2)' }}>
                <UserCircle2 size={13} className="text-blue-300" />
                <span className="text-white/70">
                  Last editor:{' '}
                  {data.last_edited_by
                    ? <strong className="text-white">{data.last_edited_by.full_name}</strong>
                    : <em className="text-white/40">unknown</em>}
                  {data.last_edited_at && (
                    <span className="text-white/40"> · {timeAgo(data.last_edited_at)}</span>
                  )}
                </span>
              </div>

              {data.items.length === 0 ? (
                <div className="text-center text-white/40 py-6 text-sm">
                  No edits recorded yet.
                </div>
              ) : (
                <div className="space-y-2">
                  {data.items.map((it) => (
                    <HistoryItem key={it.id} item={it} />
                  ))}
                </div>
              )}
              <div className="mt-3 text-[11px] text-white/35 text-right">
                {data.count} change{data.count === 1 ? '' : 's'} on file
              </div>
            </>
          )}
        </GlassCard>
      </motion.div>
    </div>
  );
}

function HistoryItem({ item }: { item: HospitalUpdateHistoryItem }) {
  const fields = Object.keys(item.changes);
  return (
    <div className="p-3 rounded-lg"
      style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
      <div className="flex items-center justify-between text-[11px] text-white/55 mb-2">
        <span className="flex items-center gap-1.5">
          <UserCircle2 size={11} />
          {item.editor ? <strong className="text-white/80">{item.editor.full_name}</strong> : <em>unknown</em>}
          <span className="text-white/30">·</span>
          <span>{item.editor?.role ?? '—'}</span>
        </span>
        <span>{item.created_at ? new Date(item.created_at).toLocaleString() : '—'}</span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {fields.map((f) => {
          const c = item.changes[f];
          const color = f === 'ors_stock' ? '#FBBF24'
            : f === 'iv_saline_stock' ? '#FB923C'
            : f === 'antibiotics_stock' ? '#F43F5E'
            : f === 'occupancy_percent' ? '#A78BFA'
            : f === 'beds' ? '#38BDF8'
            : '#2DD4BF';
          return (
            <span
              key={f}
              className="inline-flex items-center gap-1 text-[10.5px] font-mono px-1.5 py-0.5 rounded"
              style={{ background: `${color}1A`, border: `1px solid ${color}40`, color }}
            >
              {f}: {c.from} <ArrowRight size={9} /> {c.to}
            </span>
          );
        })}
      </div>
    </div>
  );
}
