'use client';

/**
 * /dashboard/admin/issues -- the admin "issue inbox".
 *
 * Lists every hospital issue report, with filters (district / status
 * / category) and a one-click ack / resolve / dismiss mutation.
 * The summary cards on top give a quick read of total reports and
 * the open / resolved / dismissed split, plus the per-district
 * hotlist.
 *
 * RBAC: all endpoints behind this page are admin-only.  We still
 * wrap the page in <AuthGuard> (any signed-in user can reach the
 * page) so a non-admin sees a friendly "not allowed" instead of
 * a raw 403.
 */
import { motion } from 'framer-motion';
import { useEffect, useState, useCallback, useMemo } from 'react';
import {
  Inbox, CheckCircle2, Clock, XCircle, Loader2, RefreshCw,
  MapPin, Tag, ChevronRight, AlertTriangle, ListFilter,
  CheckSquare, Square,
} from 'lucide-react';
import AuthGuard from '@/components/layout/AuthGuard';
import GlassCard from '@/components/cards/GlassCard';
import {
  adminListHospitalIssues,
  adminInboxSummary,
  adminUpdateIssueStatus,
  adminBulkUpdateIssueStatus,
  getApiErrorMessage,
} from '@/lib/api';
import type {
  AdminIssueRow, AdminIssueStatus, AdminIssueCategory,
  AdminInboxSummary, AdminInboxDistrictBucket, AdminInboxStatusBucket,
} from '@/lib/api';
import { BANGLADESH_DISTRICTS } from '@/lib/types';
import { useAuth } from '@/lib/auth';

const STATUS_FILTERS: { value: '' | AdminIssueStatus; label: string; tone: string }[] = [
  { value: '',         label: 'All',      tone: '#94A3B8' },
  { value: 'open',     label: 'Open',     tone: '#F59E0B' },
  { value: 'ack',      label: 'Ack',      tone: '#38BDF8' },
  { value: 'resolved', label: 'Resolved', tone: '#34D399' },
  { value: 'dismissed',label: 'Dismissed',tone: '#94A3B8' },
];

const CATEGORY_LABELS: Record<AdminIssueCategory, string> = {
  phone_wrong: 'Phone wrong',
  address_wrong: 'Address wrong',
  name_wrong: 'Name wrong',
  closed: 'Closed',
  no_doctor: 'No doctor',
  no_stock: 'No stock',
  coordinates_wrong: 'Coordinates wrong',
  other: 'Other',
};

const CATEGORY_TONE: Record<AdminIssueCategory, string> = {
  phone_wrong: '#F87171',
  address_wrong: '#FBBF24',
  name_wrong: '#A78BFA',
  closed: '#94A3B8',
  no_doctor: '#F472B6',
  no_stock: '#FB7185',
  coordinates_wrong: '#22D3EE',
  other: '#94A3B8',
};

function StatusPill({ s }: { s: AdminIssueStatus }) {
  const map: Record<AdminIssueStatus, { label: string; bg: string; fg: string; icon: React.ReactNode }> = {
    open:      { label: 'Open',      bg: 'rgba(245,158,11,0.15)', fg: '#F59E0B', icon: <Clock size={12} /> },
    ack:       { label: 'Ack',       bg: 'rgba(56,189,248,0.15)', fg: '#38BDF8', icon: <Loader2 size={12} /> },
    resolved:  { label: 'Resolved',  bg: 'rgba(52,211,153,0.15)', fg: '#34D399', icon: <CheckCircle2 size={12} /> },
    dismissed: { label: 'Dismissed', bg: 'rgba(148,163,184,0.15)', fg: '#94A3B8', icon: <XCircle size={12} /> },
  };
  const m = map[s];
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium"
      style={{ background: m.bg, color: m.fg }}
    >
      {m.icon}{m.label}
    </span>
  );
}

function SummaryCard({ label, value, icon, tone }: {
  label: string; value: number | string; icon: React.ReactNode; tone: string;
}) {
  return (
    <GlassCard className="!p-4">
      <div className="flex items-start justify-between">
        <div>
          <div className="text-xs uppercase tracking-wider text-slate-400">{label}</div>
          <div className="mt-1 text-2xl font-semibold text-white">{value}</div>
        </div>
        <div
          className="rounded-lg p-2"
          style={{ background: `${tone}22`, color: tone }}
        >
          {icon}
        </div>
      </div>
    </GlassCard>
  );
}

function DistrictHotList({ rows }: { rows: AdminInboxDistrictBucket[] }) {
  if (rows.length === 0) {
    return <div className="text-sm text-slate-400">No reports yet.</div>;
  }
  return (
    <div className="space-y-1.5">
      {rows.slice(0, 6).map((d) => (
        <div key={d.district} className="flex items-center justify-between text-sm">
          <span className="flex items-center gap-1.5 text-slate-200">
            <MapPin size={12} className="text-sky-400" />
            {d.district}
          </span>
          <span className="flex items-center gap-2 text-xs">
            <span className="text-amber-300">{d.open} open</span>
            <span className="text-slate-500">·</span>
            <span className="text-emerald-300">{d.resolved} resolved</span>
            <span className="ml-1 rounded bg-slate-800 px-1.5 py-0.5 text-slate-300">
              {d.count}
            </span>
          </span>
        </div>
      ))}
    </div>
  );
}

function CategoryBreakdown({ rows }: { rows: AdminInboxStatusBucket[] }) {
  if (rows.length === 0) {
    return <div className="text-sm text-slate-400">No reports yet.</div>;
  }
  const max = Math.max(...rows.map((r) => r.count), 1);
  return (
    <div className="space-y-1.5">
      {rows.map((r) => (
        <div key={r.status} className="flex items-center gap-2 text-sm">
          <span className="w-32 text-slate-300">
            {CATEGORY_LABELS[r.status as AdminIssueCategory] || r.status}
          </span>
          <div className="h-2 flex-1 overflow-hidden rounded bg-slate-800">
            <div
              className="h-full"
              style={{
                width: `${Math.max(8, (r.count / max) * 100)}%`,
                background: CATEGORY_TONE[r.status as AdminIssueCategory] || '#94A3B8',
              }}
            />
          </div>
          <span className="w-8 text-right text-slate-300">{r.count}</span>
        </div>
      ))}
    </div>
  );
}

export default function AdminIssuesPage() {
  return (
    <AuthGuard>
      <IssuesInbox />
    </AuthGuard>
  );
}

function IssuesInbox() {
  const { user, isLoading: authLoading } = useAuth();
  const isAdmin = user?.role === 'admin';

  const [summary, setSummary] = useState<AdminInboxSummary | null>(null);
  const [rows, setRows] = useState<AdminIssueRow[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [district, setDistrict] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<'' | AdminIssueStatus>('');
  const [category, setCategory] = useState<string>('');

  const [pendingId, setPendingId] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkPending, setBulkPending] = useState<Exclude<AdminIssueStatus, 'open'> | null>(null);

  const load = useCallback(async () => {
    if (!isAdmin) return;
    setLoading(true);
    setError(null);
    try {
      const [s, r] = await Promise.all([
        adminInboxSummary(),
        adminListHospitalIssues({
          district: district || undefined,
          status: statusFilter || undefined,
          category: (category || undefined) as AdminIssueCategory | undefined,
          limit: 100,
        }),
      ]);
      setSummary(s);
      setRows(r.items);
      setTotal(r.total);
    } catch (e) {
      setError(getApiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [isAdmin, district, statusFilter, category]);

  useEffect(() => { if (!authLoading) load(); }, [load, authLoading]);
  useEffect(() => { setSelectedIds(new Set()); }, [district, statusFilter, category]);

  const onMutate = useCallback(async (id: string, next: Exclude<AdminIssueStatus, 'open'>) => {
    setPendingId(id);
    try {
      await adminUpdateIssueStatus(id, next);
      // Optimistic local update, then a refetch so the summary rolls.
      setRows((prev) => prev.map((r) => (r.id === id ? { ...r, status: next } : r)));
      const fresh = await adminInboxSummary();
      setSummary(fresh);
    } catch (e) {
      setError(getApiErrorMessage(e));
    } finally {
      setPendingId(null);
    }
  }, []);

  const onBulk = useCallback(async (next: Exclude<AdminIssueStatus, 'open'>) => {
    if (selectedIds.size === 0) return;
    setBulkPending(next);
    try {
      const ids = Array.from(selectedIds);
      const res = await adminBulkUpdateIssueStatus(ids, next);
      // Optimistic local update for every row we know was updated.
      setRows((prev) => prev.map((r) => (ids.includes(r.id) ? { ...r, status: next } : r)));
      const fresh = await adminInboxSummary();
      setSummary(fresh);
      setSelectedIds(new Set());
      if (res.not_found && res.not_found.length > 0) {
        setError(`${res.updated} updated, ${res.not_found.length} missing (refresh to see latest).`);
      }
    } catch (e) {
      setError(getApiErrorMessage(e));
    } finally {
      setBulkPending(null);
    }
  }, [selectedIds]);

  const toggleSelected = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }, []);

  const toggleAllSelected = useCallback(() => {
    // Only rows still in 'open' or 'ack' are bulk-actionable; we
    // don't let admins mass-resolve or mass-dismiss an already-closed
    // report (the per-row button is still there for that).
    const actionable = rows.filter((r) => r.status === 'open' || r.status === 'ack');
    setSelectedIds((prev) => {
      const allOn = actionable.every((r) => prev.has(r.id));
      if (allOn) return new Set();
      return new Set(actionable.map((r) => r.id));
    });
  }, [rows]);

  const byStatus = useMemo(() => {
    const m: Record<string, number> = { open: 0, ack: 0, resolved: 0, dismissed: 0 };
    (summary?.by_status || []).forEach((b) => { m[b.status] = b.count; });
    return m;
  }, [summary]);

  if (authLoading) {
    return (
      <div className="flex h-64 items-center justify-center text-slate-400">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" /> Loading…
      </div>
    );
  }

  if (!isAdmin) {
    return (
      <div className="mx-auto max-w-xl py-16 text-center">
        <AlertTriangle className="mx-auto mb-3 h-10 w-10 text-amber-400" />
        <h1 className="text-xl font-semibold text-white">Admin only</h1>
        <p className="mt-2 text-sm text-slate-400">
          The issue inbox is only visible to administrators. If you believe
          you should have access, ask a colleague with the admin role to
          promote you.
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <div className="mb-6 flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2 text-sky-300">
              <Inbox size={20} />
              <h1 className="text-2xl font-semibold text-white">Issue inbox</h1>
            </div>
            <p className="mt-1 text-sm text-slate-400">
              Every hospital issue report, newest first. Resolve or dismiss
              as you work through them.
            </p>
          </div>
          <button
            onClick={load}
            disabled={loading}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800 px-3 py-1.5 text-sm text-slate-200 hover:bg-slate-700 disabled:opacity-50"
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>

        {error && (
          <div className="mb-4 rounded-lg border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
            {error}
          </div>
        )}

        {/* Summary cards */}
        <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4">
          <SummaryCard
            label="Total reports" value={summary?.total ?? total}
            icon={<Inbox size={18} />} tone="#38BDF8"
          />
          <SummaryCard
            label="Open" value={byStatus.open || 0}
            icon={<Clock size={18} />} tone="#F59E0B"
          />
          <SummaryCard
            label="Resolved" value={byStatus.resolved || 0}
            icon={<CheckCircle2 size={18} />} tone="#34D399"
          />
          <SummaryCard
            label="Dismissed" value={byStatus.dismissed || 0}
            icon={<XCircle size={18} />} tone="#94A3B8"
          />
        </div>

        <div className="mb-6 grid gap-3 md:grid-cols-2">
          <GlassCard className="!p-4">
            <h2 className="mb-2 text-sm font-medium text-slate-300">Hot districts</h2>
            <DistrictHotList rows={summary?.by_district || []} />
          </GlassCard>
          <GlassCard className="!p-4">
            <h2 className="mb-2 text-sm font-medium text-slate-300">By category</h2>
            <CategoryBreakdown rows={summary?.by_category || []} />
          </GlassCard>
        </div>

        {/* Filters */}
        <GlassCard className="mb-4 !p-3">
          <div className="flex flex-wrap items-center gap-2">
            <ListFilter size={14} className="text-slate-400" />
            <select
              value={district}
              onChange={(e) => setDistrict(e.target.value)}
              className="rounded border border-slate-700 bg-slate-800 px-2 py-1.5 text-sm text-slate-200"
            >
              <option value="">All districts</option>
              {BANGLADESH_DISTRICTS.map((d) => (
                <option key={d} value={d}>{d}</option>
              ))}
            </select>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="rounded border border-slate-700 bg-slate-800 px-2 py-1.5 text-sm text-slate-200"
            >
              <option value="">All categories</option>
              {Object.entries(CATEGORY_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
            <div className="ml-auto flex flex-wrap items-center gap-1">
              {STATUS_FILTERS.map((f) => (
                <button
                  key={f.value || 'all'}
                  onClick={() => setStatusFilter(f.value)}
                  className={`rounded-full border px-2.5 py-1 text-xs font-medium transition ${
                    statusFilter === f.value
                      ? 'border-sky-400/60 bg-sky-400/15 text-sky-200'
                      : 'border-slate-700 bg-slate-800 text-slate-300 hover:bg-slate-700'
                  }`}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </div>
        </GlassCard>

        {/* Bulk action bar (sticky when items are selected) */}
        {selectedIds.size > 0 && (
          <div
            className="mb-3 flex flex-wrap items-center gap-2 rounded-lg border border-sky-500/40 bg-sky-500/10 px-3 py-2 text-sm"
            data-testid="bulk-bar"
          >
            <span className="font-medium text-sky-200">
              {selectedIds.size} selected
            </span>
            <span className="text-sky-300/60">·</span>
            <span className="text-xs text-sky-300/80">
              Only open and ack rows are bulk-actionable.
            </span>
            <div className="ml-auto flex items-center gap-1">
              <button
                onClick={() => onBulk('ack')}
                disabled={bulkPending !== null}
                className="rounded border border-sky-500/40 bg-sky-500/10 px-2.5 py-1 text-xs text-sky-200 hover:bg-sky-500/20 disabled:opacity-50"
              >
                {bulkPending === 'ack' ? 'Acking…' : 'Acknowledge'}
              </button>
              <button
                onClick={() => onBulk('resolved')}
                disabled={bulkPending !== null}
                className="rounded border border-emerald-500/40 bg-emerald-500/10 px-2.5 py-1 text-xs text-emerald-200 hover:bg-emerald-500/20 disabled:opacity-50"
              >
                {bulkPending === 'resolved' ? 'Resolving…' : 'Resolve'}
              </button>
              <button
                onClick={() => onBulk('dismissed')}
                disabled={bulkPending !== null}
                className="rounded border border-slate-600 bg-slate-800 px-2.5 py-1 text-xs text-slate-300 hover:bg-slate-700 disabled:opacity-50"
              >
                {bulkPending === 'dismissed' ? 'Dismissing…' : 'Dismiss'}
              </button>
              <button
                onClick={() => setSelectedIds(new Set())}
                disabled={bulkPending !== null}
                className="rounded border border-slate-700 bg-slate-900 px-2.5 py-1 text-xs text-slate-400 hover:bg-slate-800 disabled:opacity-50"
              >
                Clear
              </button>
            </div>
          </div>
        )}

                {/* Table */}
        <GlassCard className="!p-0">
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-slate-900/60 text-xs uppercase tracking-wider text-slate-400">
                <tr>
                  <th className="px-3 py-2.5 w-8">
                    <button
                      onClick={toggleAllSelected}
                      className="rounded p-0.5 text-slate-400 hover:text-white"
                      title="Select all actionable rows"
                    >
                      {rows.filter((r) => r.status === 'open' || r.status === 'ack').every((r) => selectedIds.has(r.id)) && rows.some((r) => r.status === 'open' || r.status === 'ack') ? (
                        <CheckSquare size={14} />
                      ) : (
                        <Square size={14} />
                      )}
                    </button>
                  </th>
                  <th className="px-4 py-2.5">Hospital</th>
                  <th className="px-4 py-2.5">District</th>
                  <th className="px-4 py-2.5">Category</th>
                  <th className="px-4 py-2.5">Description</th>
                  <th className="px-4 py-2.5">Reporter</th>
                  <th className="px-4 py-2.5">Status</th>
                  <th className="px-4 py-2.5">When</th>
                  <th className="px-4 py-2.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {loading && rows.length === 0 && (
                  <tr>
                    <td colSpan={9} className="px-4 py-10 text-center text-slate-400">
                      <Loader2 className="mr-2 inline h-4 w-4 animate-spin" /> Loading…
                    </td>
                  </tr>
                )}
                {!loading && rows.length === 0 && (
                  <tr>
                    <td colSpan={9} className="px-4 py-10 text-center text-slate-400">
                      No reports match these filters.
                    </td>
                  </tr>
                )}
                {rows.map((r) => {
                  const isPending = pendingId === r.id;
                  const actionable = r.status === 'open' || r.status === 'ack';
                  const isSelected = selectedIds.has(r.id);
                  return (
                    <tr key={r.id} className="border-t border-slate-800/60 align-top hover:bg-slate-900/30">
                      <td className="px-3 py-2.5">
                        {actionable ? (
                          <button
                            onClick={() => toggleSelected(r.id)}
                            className="rounded p-0.5"
                            title={isSelected ? 'Unselect' : 'Select'}
                          >
                            {isSelected
                              ? <CheckSquare size={14} className="text-sky-400" />
                              : <Square size={14} className="text-slate-500" />}
                          </button>
                        ) : (
                          <span className="block h-4 w-4" />
                        )}
                      </td>
                      <td className="px-4 py-2.5">
                        <div className="flex items-start gap-1.5">
                          <ChevronRight size={14} className="mt-0.5 text-slate-500" />
                          <div>
                            <div className="font-medium text-white">{r.hospital_name}</div>
                            <div className="text-[10px] text-slate-500">{r.hospital_id.slice(0, 8)}</div>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-2.5 text-slate-300">{r.district || '—'}</td>
                      <td className="px-4 py-2.5">
                        <span
                          className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs"
                          style={{
                            background: `${CATEGORY_TONE[r.category] || '#94A3B8'}22`,
                            color: CATEGORY_TONE[r.category] || '#94A3B8',
                          }}
                        >
                          <Tag size={10} />
                          {CATEGORY_LABELS[r.category] || r.category}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 max-w-md text-slate-200">
                        <div className="line-clamp-2 whitespace-pre-wrap">{r.description}</div>
                      </td>
                      <td className="px-4 py-2.5 text-xs text-slate-400">
                        <div>{r.reporter_role || '—'}</div>
                        <div className="text-slate-500">{r.reporter_email || ''}</div>
                      </td>
                      <td className="px-4 py-2.5"><StatusPill s={r.status} /></td>
                      <td className="px-4 py-2.5 text-xs text-slate-400">
                        {new Date(r.created_at).toLocaleString()}
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        {r.status === 'open' && (
                          <div className="inline-flex gap-1">
                            <button
                              onClick={() => onMutate(r.id, 'ack')}
                              disabled={isPending}
                              className="rounded border border-sky-500/40 bg-sky-500/10 px-2 py-1 text-xs text-sky-200 hover:bg-sky-500/20 disabled:opacity-50"
                            >
                              Ack
                            </button>
                            <button
                              onClick={() => onMutate(r.id, 'resolved')}
                              disabled={isPending}
                              className="rounded border border-emerald-500/40 bg-emerald-500/10 px-2 py-1 text-xs text-emerald-200 hover:bg-emerald-500/20 disabled:opacity-50"
                            >
                              Resolve
                            </button>
                            <button
                              onClick={() => onMutate(r.id, 'dismissed')}
                              disabled={isPending}
                              className="rounded border border-slate-600 bg-slate-800 px-2 py-1 text-xs text-slate-300 hover:bg-slate-700 disabled:opacity-50"
                            >
                              Dismiss
                            </button>
                          </div>
                        )}
                        {r.status === 'ack' && (
                          <div className="inline-flex gap-1">
                            <button
                              onClick={() => onMutate(r.id, 'resolved')}
                              disabled={isPending}
                              className="rounded border border-emerald-500/40 bg-emerald-500/10 px-2 py-1 text-xs text-emerald-200 hover:bg-emerald-500/20 disabled:opacity-50"
                            >
                              Resolve
                            </button>
                            <button
                              onClick={() => onMutate(r.id, 'dismissed')}
                              disabled={isPending}
                              className="rounded border border-slate-600 bg-slate-800 px-2 py-1 text-xs text-slate-300 hover:bg-slate-700 disabled:opacity-50"
                            >
                              Dismiss
                            </button>
                          </div>
                        )}
                        {(r.status === 'resolved' || r.status === 'dismissed') && (
                          <span className="text-xs text-slate-500">closed</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {total > 100 && (
            <div className="border-t border-slate-800/60 px-4 py-2 text-xs text-slate-400">
              Showing {rows.length} of {total} — refine filters to narrow.
            </div>
          )}
        </GlassCard>
      </motion.div>
    </div>
  );
}
