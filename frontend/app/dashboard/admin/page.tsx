'use client';

import { motion, AnimatePresence } from 'framer-motion';
import { useEffect, useState, useCallback, useMemo } from 'react';
import GlassCard from '@/components/cards/GlassCard';
import AuthGuard from '@/components/layout/AuthGuard';
import { getToken, useAuth } from '@/lib/auth';
import {
  Settings, AlertCircle, CheckCircle, User, Shield,
  Trash2, ChevronDown, RefreshCw, Users, Database,
  Activity, BookOpen, MessageSquare, UserPlus, Edit3, Plus,
  Save, X, Inbox, ExternalLink,
} from 'lucide-react';
import { getApiErrorMessage } from '@/lib/api';
import {
  loadDistrictBanglaMap,
  lookupBangla,
} from '@/lib/api';
import {
  adminCreateUser,
  adminListAllPredictions,
  adminListKnowledge,
  adminCreateKnowledge,
  adminUpdateKnowledge,
  adminDeleteKnowledge,
  adminDataStatus,
  adminListChatHistory,
  adminGetChatConversation,
} from '@/lib/api';
import type {
  AdminPredictionAuditItem,
  AdminKnowledgeArticle,
  AdminDataStatusResponse,
  AdminChatHistoryItem,
  AdminChatHistoryDetail,
  AdminCreateUserPayload,
} from '@/lib/types';
import { BANGLADESH_DISTRICTS } from '@/lib/types';

const cardVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.1, duration: 0.4 },
  }),
};

// Local UI role labels used by the existing user-list table. The backend
// roles are `ngo` and `government`; we keep the old display strings here
// to avoid breaking the table the user already has working.
type LocalRole = 'citizen' | 'health_worker' | 'ngo_partner' | 'district_official' | 'researcher' | 'admin';

// Backend roles that the /admin/users POST endpoint accepts (Gap 1).
type AdminRole = 'health_worker' | 'hospital' | 'ngo' | 'government' | 'admin';

interface UserRecord {
  id: string;
  email: string;
  full_name: string;
  role: LocalRole;
  district: string | null;
  created_at: string | null;
}

const ROLE_COLORS: Record<LocalRole, string> = {
  citizen: '#38BDF8',
  health_worker: '#2DD4BF',
  ngo_partner: '#818CF8',
  district_official: '#F59E0B',
  researcher: '#A78BFA',
  admin: '#F43F5E',
};

const ROLE_OPTIONS: LocalRole[] = [
  'citizen', 'health_worker', 'ngo_partner',
  'district_official', 'researcher', 'admin',
];

const OPERATIONAL_ROLES: AdminRole[] = ['health_worker', 'hospital', 'ngo', 'government', 'admin'];
const OPERATIONAL_ROLE_LABELS: Record<AdminRole, string> = {
  health_worker: 'Health Worker',
  hospital: 'Hospital',
  ngo: 'NGO',
  government: 'Government',
  admin: 'Admin',
};

type Tab = 'users' | 'predictions' | 'knowledge' | 'data' | 'chat';

const TABS: Array<{ id: Tab; label: string; icon: typeof Users }> = [
  { id: 'users', label: 'Users', icon: Users },
  { id: 'predictions', label: 'Predictions', icon: Activity },
  { id: 'knowledge', label: 'Knowledge', icon: BookOpen },
  { id: 'data', label: 'Data Status', icon: Database },
  { id: 'chat', label: 'Chat History', icon: MessageSquare },
];

export default function AdminPage() {
  const { user } = useAuth();
  const [tab, setTab] = useState<Tab>('users');
  const [users, setUsers] = useState<UserRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const token = getToken();

  const fetchUsers = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'}/admin/users`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`Server returned ${res.status}`);
      const data: UserRecord[] = await res.json();
      setUsers(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load users');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { fetchUsers(); }, [fetchUsers]);

  const handleRoleChange = async (userId: string, newRole: LocalRole) => {
    if (!token) return;
    setUpdatingId(userId);
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'}/admin/users/${userId}/role`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
          body: JSON.stringify({ role: newRole }),
        }
      );
      if (!res.ok) throw new Error(`Role update failed: ${res.status}`);
      setUsers((prev) =>
        prev.map((u) => (u.id === userId ? { ...u, role: newRole } : u))
      );
      setSuccessMsg('Role updated successfully');
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Role update failed');
    } finally {
      setUpdatingId(null);
    }
  };

  const handleDelete = async (userId: string, email: string) => {
    if (!token) return;
    if (!confirm(`Delete user "${email}"? This cannot be undone.`)) return;
    setDeletingId(userId);
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'}/admin/users/${userId}`,
        { method: 'DELETE', headers: { Authorization: `Bearer ${token}` } }
      );
      if (!res.ok && res.status !== 204) throw new Error(`Delete failed: ${res.status}`);
      setUsers((prev) => prev.filter((u) => u.id !== userId));
      setSuccessMsg('User deleted');
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Delete failed');
    } finally {
      setDeletingId(null);
    }
  };

  const stats = [
    { label: 'Total Users', value: loading ? '…' : users.length.toString(), icon: User, color: '#38BDF8' },
    { label: 'Admin Users', value: loading ? '…' : users.filter((u) => u.role === 'admin').length.toString(), icon: Shield, color: '#F43F5E' },
    { label: 'Health Workers', value: loading ? '…' : users.filter((u) => u.role === 'health_worker').length.toString(), icon: CheckCircle, color: '#2DD4BF' },
    { label: 'Active Roles', value: loading ? '…' : new Set(users.map((u) => u.role)).size.toString(), icon: Users, color: '#818CF8' },
  ];

  return (
    <AuthGuard allowedRoles={['admin']}>
      <div className="max-w-7xl mx-auto space-y-6 pb-12">
        {/* Header */}
        <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-red-500 to-pink-500 flex items-center justify-center">
              <Settings size={20} className="text-white" />
            </div>
            <div>
              <h1 className="text-4xl font-black text-white" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
                Admin Panel
              </h1>
              <p className="text-white/50 mt-1">User management, prediction audit, knowledge base, and data coverage</p>
            </div>
            <div className="ml-auto flex items-center gap-2">
              <a
                href="/dashboard/admin/issues"
                className="inline-flex items-center gap-1.5 rounded-lg border border-sky-500/40 bg-sky-500/10 px-3 py-1.5 text-sm text-sky-200 hover:bg-sky-500/20"
              >
                <Inbox size={14} />
                Issue inbox
                <ExternalLink size={12} className="opacity-60" />
              </a>
            </div>
          </div>
        </motion.div>

        {/* Alerts */}
        {error && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            <GlassCard className="p-4 border-red-400/20 flex items-start gap-3" style={{ borderColor: 'rgba(244,63,94,0.2)', background: 'rgba(244,63,94,0.05)' }}>
              <AlertCircle size={18} className="text-red-400 mt-0.5 shrink-0" />
              <div>
                <p className="text-red-300 text-sm font-semibold">Error</p>
                <p className="text-red-200/60 text-xs mt-1">{error}</p>
              </div>
            </GlassCard>
          </motion.div>
        )}

        {successMsg && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            <GlassCard className="p-4 flex items-start gap-3" style={{ borderColor: 'rgba(45,212,191,0.25)', background: 'rgba(45,212,191,0.05)' }}>
              <CheckCircle size={18} className="text-teal-400 mt-0.5 shrink-0" />
              <p className="text-teal-300 text-sm font-semibold">{successMsg}</p>
            </GlassCard>
          </motion.div>
        )}

        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <GlassCard className="p-4 flex items-start gap-3" style={{ borderColor: 'rgba(251,191,36,0.2)', background: 'rgba(251,191,36,0.05)' }}>
            <AlertCircle size={18} className="text-amber-400 mt-0.5 shrink-0" />
            <div>
              <p className="text-amber-300 text-sm font-semibold">Admin Access Granted</p>
              <p className="text-amber-200/60 text-xs mt-1">
                Logged in as <span className="font-mono">{user?.email}</span>. Role changes are permanent.
              </p>
            </div>
          </GlassCard>
        </motion.div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {stats.map((stat, i) => {
            const Icon = stat.icon;
            return (
              <motion.div key={i} custom={i + 1} variants={cardVariants} initial="hidden" animate="visible">
                <GlassCard className="p-5">
                  <div className="flex items-start justify-between mb-3">
                    <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ background: `${stat.color}18` }}>
                      <Icon size={18} style={{ color: stat.color }} />
                    </div>
                  </div>
                  <div className="text-3xl font-black text-white mb-1" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
                    {stat.value}
                  </div>
                  <div className="text-white/50 text-sm">{stat.label}</div>
                </GlassCard>
              </motion.div>
            );
          })}
        </div>

        {/* Tab bar */}
        <div className="flex flex-wrap gap-2 border-b border-white/10 pb-1">
          {TABS.map((t) => {
            const Icon = t.icon;
            const active = tab === t.id;
            return (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                style={{
                  display: 'flex', alignItems: 'center', gap: '8px',
                  padding: '10px 18px', borderRadius: '10px 10px 0 0',
                  background: active ? 'rgba(244,63,94,0.12)' : 'transparent',
                  color: active ? '#FCA5A5' : 'rgba(255,255,255,0.55)',
                  fontSize: '14px', fontWeight: 600, cursor: 'pointer',
                  borderBottom: active ? '2px solid #F43F5E' : '2px solid transparent',
                }}
              >
                <Icon size={15} /> {t.label}
              </button>
            );
          })}
        </div>

        {/* Tab content */}
        <AnimatePresence mode="wait">
          <motion.div key={tab} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
            {tab === 'users' && (
              <UsersTab
                users={users}
                loading={loading}
                deletingId={deletingId}
                updatingId={updatingId}
                onRefresh={fetchUsers}
                onRoleChange={handleRoleChange}
                onDelete={handleDelete}
                onCreated={() => { fetchUsers(); setSuccessMsg('User created'); setTimeout(() => setSuccessMsg(null), 3000); }}
                onError={(msg) => setError(msg)}
                currentUserId={user?.id ?? null}
              />
            )}
            {tab === 'predictions' && <PredictionsTab />}
            {tab === 'knowledge' && <KnowledgeTab />}
            {tab === 'data' && <DataStatusTab />}
            {tab === 'chat' && <ChatHistoryTab />}
          </motion.div>
        </AnimatePresence>

        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    </AuthGuard>
  );
}

// ───────────────────────────────────────────────────────────────────────
// UsersTab — list + create user
// ───────────────────────────────────────────────────────────────────────
function UsersTab(props: {
  users: UserRecord[];
  loading: boolean;
  deletingId: string | null;
  updatingId: string | null;
  onRefresh: () => void;
  onRoleChange: (id: string, role: LocalRole) => void;
  onDelete: (id: string, email: string) => void;
  onCreated: () => void;
  onError: (msg: string) => void;
  currentUserId: string | null;
}) {
  return (
    <div className="space-y-6">
      <CreateUserCard onCreated={props.onCreated} onError={props.onError} />
      <UserListCard {...props} />
    </div>
  );
}

function CreateUserCard({ onCreated, onError }: { onCreated: () => void; onError: (m: string) => void }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [role, setRole] = useState<AdminRole>('health_worker');
  const [district, setDistrict] = useState('');
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const payload: AdminCreateUserPayload = {
        email: email.trim(),
        password,
        full_name: fullName.trim(),
        role,
        district: district || null,
      };
      await adminCreateUser(payload);
      setEmail(''); setPassword(''); setFullName(''); setDistrict(''); setRole('health_worker');
      onCreated();
    } catch (err) {
      onError(getApiErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <GlassCard className="p-6">
      <div className="flex items-center gap-2 mb-4">
        <UserPlus size={18} className="text-teal-400" />
        <h2 className="text-xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
          Create operational user
        </h2>
      </div>
      <p className="text-white/40 text-sm mb-4">
        Provision health_worker / hospital / ngo / government / admin accounts.
        Citizens self-register via the public signup form.
      </p>
      <form onSubmit={onSubmit} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <Field label="Full name" value={fullName} onChange={setFullName} required minLength={2} />
        <Field label="Email" type="email" value={email} onChange={setEmail} required />
        <Field label="Password (min 8 chars)" type="password" value={password} onChange={setPassword} required minLength={8} />
        <SelectField
          label="Role"
          value={role}
          onChange={(v) => setRole(v as AdminRole)}
          options={OPERATIONAL_ROLES.map((r) => ({ value: r, label: OPERATIONAL_ROLE_LABELS[r] }))}
        />
        <SelectField
          label="District (optional)"
          value={district}
          onChange={setDistrict}
          options={[{ value: '', label: '— none —' }, ...BANGLADESH_DISTRICTS.map((d) => ({ value: d, label: d }))]}
        />
        <div className="flex items-end">
          <button
            type="submit"
            disabled={busy}
            style={{
              display: 'flex', alignItems: 'center', gap: '6px',
              padding: '10px 18px', borderRadius: '8px',
              background: 'rgba(45,212,191,0.15)', border: '1px solid rgba(45,212,191,0.3)',
              color: '#5EEAD4', fontSize: '14px', fontWeight: 600,
              cursor: busy ? 'wait' : 'pointer', opacity: busy ? 0.5 : 1,
            }}
          >
            {busy ? <RefreshCw size={14} className="animate-spin" /> : <Plus size={14} />}
            Create user
          </button>
        </div>
      </form>
    </GlassCard>
  );
}

function UserListCard(props: {
  users: UserRecord[];
  loading: boolean;
  deletingId: string | null;
  updatingId: string | null;
  onRefresh: () => void;
  onRoleChange: (id: string, role: LocalRole) => void;
  onDelete: (id: string, email: string) => void;
  currentUserId: string | null;
}) {
  return (
    <motion.div custom={5} variants={cardVariants} initial="hidden" animate="visible">
      <GlassCard className="p-6">
        <div className="flex items-center justify-between mb-5">
          <div>
            <h2 className="text-xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
              User Management
            </h2>
            <p className="text-white/40 text-sm mt-0.5">
              {props.loading ? 'Loading…' : `${props.users.length} registered users`}
            </p>
          </div>
          <button
            onClick={props.onRefresh}
            disabled={props.loading}
            style={{
              display: 'flex', alignItems: 'center', gap: '6px',
              padding: '8px 14px', borderRadius: '8px',
              background: 'rgba(59,130,246,0.15)', border: '1px solid rgba(59,130,246,0.3)',
              color: '#93C5FD', fontSize: '13px', fontWeight: 600, cursor: 'pointer',
              opacity: props.loading ? 0.5 : 1,
            }}
          >
            <RefreshCw size={14} className={props.loading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>

        {props.loading ? (
          <div className="flex justify-center py-12">
            <div style={{ width: 32, height: 32, border: '2px solid #3b82f6', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
          </div>
        ) : props.users.length === 0 ? (
          <div className="text-center py-12 text-white/40">
            <Users size={40} className="mx-auto mb-3 opacity-30" />
            <p>No users found</p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                  {['Name / Email', 'District', 'Role', 'Joined', 'Actions'].map((h) => (
                    <th key={h} style={{ padding: '10px 14px', textAlign: 'left', color: 'rgba(255,255,255,0.4)', fontWeight: 600, fontSize: '11px', letterSpacing: '0.6px', textTransform: 'uppercase', whiteSpace: 'nowrap' }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {props.users.map((u) => (
                  <tr
                    key={u.id}
                    style={{ borderBottom: '1px solid rgba(255,255,255,0.04)', transition: 'background 0.2s' }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.03)')}
                    onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                  >
                    <td style={{ padding: '12px 14px' }}>
                      <div style={{ color: '#fff', fontWeight: 600 }}>{u.full_name || '—'}</div>
                      <div style={{ color: 'rgba(255,255,255,0.4)', fontSize: '12px', marginTop: 2 }}>{u.email}</div>
                    </td>
                    <td style={{ padding: '12px 14px', color: 'rgba(255,255,255,0.6)' }}>
                      {u.district || <span style={{ color: 'rgba(255,255,255,0.25)', fontStyle: 'italic' }}>N/A</span>}
                    </td>
                    <td style={{ padding: '12px 14px' }}>
                      <div style={{ position: 'relative', display: 'inline-block' }}>
                        <select
                          value={u.role}
                          disabled={props.updatingId === u.id || u.id === props.currentUserId}
                          onChange={(e) => props.onRoleChange(u.id, e.target.value as LocalRole)}
                          style={{
                            appearance: 'none',
                            padding: '5px 28px 5px 10px',
                            borderRadius: '6px',
                            border: `1px solid ${ROLE_COLORS[u.role]}40`,
                            background: `${ROLE_COLORS[u.role]}18`,
                            color: ROLE_COLORS[u.role],
                            fontSize: '12px', fontWeight: 600,
                            cursor: props.updatingId === u.id || u.id === props.currentUserId ? 'not-allowed' : 'pointer',
                            outline: 'none',
                            opacity: props.updatingId === u.id ? 0.5 : 1,
                          }}
                        >
                          {ROLE_OPTIONS.map((r) => (
                            <option key={r} value={r} style={{ background: '#0d1117', color: '#fff' }}>
                              {r.replace('_', ' ')}
                            </option>
                          ))}
                        </select>
                        <ChevronDown size={12} style={{ position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)', color: ROLE_COLORS[u.role], pointerEvents: 'none' }} />
                      </div>
                    </td>
                    <td style={{ padding: '12px 14px', color: 'rgba(255,255,255,0.4)', whiteSpace: 'nowrap', fontSize: '12px' }}>
                      {u.created_at ? new Date(u.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : '—'}
                    </td>
                    <td style={{ padding: '12px 14px' }}>
                      <button
                        disabled={props.deletingId === u.id || u.id === props.currentUserId}
                        onClick={() => props.onDelete(u.id, u.email)}
                        title={u.id === props.currentUserId ? 'Cannot delete yourself' : `Delete ${u.email}`}
                        style={{
                          padding: '6px 10px', borderRadius: '6px',
                          background: 'rgba(244,63,94,0.12)', border: '1px solid rgba(244,63,94,0.25)',
                          color: '#F43F5E', cursor: u.id === props.currentUserId ? 'not-allowed' : 'pointer',
                          opacity: u.id === props.currentUserId ? 0.3 : props.deletingId === u.id ? 0.5 : 1,
                          display: 'flex', alignItems: 'center', gap: '5px', fontSize: '12px', fontWeight: 600,
                        }}
                      >
                        <Trash2 size={13} />
                        {props.deletingId === u.id ? 'Deleting…' : 'Delete'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </GlassCard>
    </motion.div>
  );
}

// ───────────────────────────────────────────────────────────────────────
// PredictionsTab — Gap 2: cross-user prediction audit
// ───────────────────────────────────────────────────────────────────────
function PredictionsTab() {
  const [items, setItems] = useState<AdminPredictionAuditItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [filterModel, setFilterModel] = useState('');
  const [filterDistrict, setFilterDistrict] = useState('');
  const [filterUser, setFilterUser] = useState('');

  const load = useCallback(async () => {
    setLoading(true); setErr(null);
    try {
      const data = await adminListAllPredictions({
        model_name: filterModel || undefined,
        district: filterDistrict || undefined,
        user_email: filterUser || undefined,
        limit: 100,
      });
      setItems(data.items);
    } catch (e) {
      setErr(getApiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [filterModel, filterDistrict, filterUser]);

  useEffect(() => { load(); }, [load]);

  return (
    <GlassCard className="p-6">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
            Cross-user prediction audit
          </h2>
          <p className="text-white/40 text-sm mt-0.5">
            Every operational prediction in the system, with the issuing user and role.
          </p>
        </div>
        <button
          onClick={load}
          disabled={loading}
          style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 14px', borderRadius: '8px', background: 'rgba(59,130,246,0.15)', border: '1px solid rgba(59,130,246,0.3)', color: '#93C5FD', fontSize: '13px', fontWeight: 600, cursor: 'pointer', opacity: loading ? 0.5 : 1 }}
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
        <Field label="Model" value={filterModel} onChange={setFilterModel} placeholder="flood / disease / ..." />
        <Field label="District" value={filterDistrict} onChange={setFilterDistrict} placeholder="Feni" />
        <Field label="User email" value={filterUser} onChange={setFilterUser} placeholder="someone@" />
      </div>

      {err && <ErrorBanner msg={err} />}

      {loading ? <CenteredSpinner /> : items.length === 0 ? <EmptyState text="No predictions match these filters." /> : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                {['When', 'User', 'Role', 'Model', 'District', 'Risk', 'Prob.'].map((h) => (
                  <th key={h} style={{ padding: '10px 12px', textAlign: 'left', color: 'rgba(255,255,255,0.4)', fontWeight: 600, fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.6px' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.map((p) => (
                <tr key={p.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                  <td style={{ padding: '10px 12px', color: 'rgba(255,255,255,0.55)', fontSize: '12px', whiteSpace: 'nowrap' }}>
                    {new Date(p.created_at).toLocaleString()}
                  </td>
                  <td style={{ padding: '10px 12px', color: 'rgba(255,255,255,0.8)', fontSize: '12px' }}>{p.user_email}</td>
                  <td style={{ padding: '10px 12px', color: 'rgba(255,255,255,0.6)', fontSize: '12px' }}>{p.user_role}</td>
                  <td style={{ padding: '10px 12px', color: 'rgba(255,255,255,0.8)' }}>{p.model_name}</td>
                  <td style={{ padding: '10px 12px', color: 'rgba(255,255,255,0.6)' }}>{p.district ?? '—'}</td>
                  <td style={{ padding: '10px 12px', color: 'rgba(255,255,255,0.7)' }}>{p.risk_level ?? '—'}</td>
                  <td style={{ padding: '10px 12px', color: 'rgba(255,255,255,0.7)', fontFamily: 'JetBrains Mono, monospace', fontSize: '12px' }}>
                    {p.probability != null ? p.probability.toFixed(3) : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </GlassCard>
  );
}

// ───────────────────────────────────────────────────────────────────────
// KnowledgeTab — Gap 4: knowledge article CRUD
// ───────────────────────────────────────────────────────────────────────
function KnowledgeTab() {
  const [items, setItems] = useState<AdminKnowledgeArticle[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [editing, setEditing] = useState<AdminKnowledgeArticle | null>(null);
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setErr(null);
    try {
      const data = await adminListKnowledge();
      setItems(data.items);
    } catch (e) {
      setErr(getApiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleDelete = async (a: AdminKnowledgeArticle) => {
    if (!confirm(`Delete article "${a.disease_name}"?`)) return;
    try {
      await adminDeleteKnowledge(a.id);
      load();
    } catch (e) {
      setErr(getApiErrorMessage(e));
    }
  };

  return (
    <GlassCard className="p-6">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
            Medical knowledge base
          </h2>
          <p className="text-white/40 text-sm mt-0.5">
            Articles the chatbot consults for disease / symptom / treatment questions.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setCreating(true)}
            style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 14px', borderRadius: '8px', background: 'rgba(45,212,191,0.15)', border: '1px solid rgba(45,212,191,0.3)', color: '#5EEAD4', fontSize: '13px', fontWeight: 600, cursor: 'pointer' }}
          >
            <Plus size={14} /> New article
          </button>
          <button
            onClick={load}
            disabled={loading}
            style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 14px', borderRadius: '8px', background: 'rgba(59,130,246,0.15)', border: '1px solid rgba(59,130,246,0.3)', color: '#93C5FD', fontSize: '13px', fontWeight: 600, cursor: 'pointer', opacity: loading ? 0.5 : 1 }}
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
          </button>
        </div>
      </div>

      {err && <ErrorBanner msg={err} />}

      {loading ? <CenteredSpinner /> : items.length === 0 ? <EmptyState text="No knowledge articles yet." /> : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {items.map((a) => (
            <div key={a.id} style={{ padding: '14px', borderRadius: '10px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
              <div className="flex items-start justify-between mb-2">
                <h3 style={{ color: '#fff', fontSize: '15px', fontWeight: 700 }}>{a.disease_name}</h3>
                <div className="flex gap-1">
                  <button
                    onClick={() => setEditing(a)}
                    title="Edit"
                    style={{ padding: '4px 8px', borderRadius: '6px', background: 'rgba(59,130,246,0.15)', border: '1px solid rgba(59,130,246,0.3)', color: '#93C5FD', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px', fontSize: '12px' }}
                  >
                    <Edit3 size={12} /> Edit
                  </button>
                  <button
                    onClick={() => handleDelete(a)}
                    title="Delete"
                    style={{ padding: '4px 8px', borderRadius: '6px', background: 'rgba(244,63,94,0.12)', border: '1px solid rgba(244,63,94,0.25)', color: '#F43F5E', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px', fontSize: '12px' }}
                  >
                    <Trash2 size={12} /> Delete
                  </button>
                </div>
              </div>
              <p style={{ color: 'rgba(255,255,255,0.65)', fontSize: '12.5px', lineHeight: 1.5 }}><strong style={{ color: 'rgba(255,255,255,0.5)' }}>Symptoms:</strong> {a.symptoms}</p>
              {a.prevention_tips && <p style={{ color: 'rgba(255,255,255,0.55)', fontSize: '12px', marginTop: 6 }}><strong style={{ color: 'rgba(255,255,255,0.45)' }}>Prevention:</strong> {a.prevention_tips}</p>}
              {a.reference && <p style={{ color: 'rgba(255,255,255,0.4)', fontSize: '11px', marginTop: 6, fontStyle: 'italic' }}>Source: {a.reference}</p>}
            </div>
          ))}
        </div>
      )}

      {(creating || editing) && (
        <KnowledgeEditorModal
          article={editing}
          onClose={() => { setCreating(false); setEditing(null); }}
          onSaved={() => { setCreating(false); setEditing(null); load(); }}
          onError={(m) => setErr(m)}
        />
      )}
    </GlassCard>
  );
}

function KnowledgeEditorModal({ article, onClose, onSaved, onError }: {
  article: AdminKnowledgeArticle | null;
  onClose: () => void;
  onSaved: () => void;
  onError: (m: string) => void;
}) {
  const [diseaseName, setDiseaseName] = useState(article?.disease_name ?? '');
  const [symptoms, setSymptoms] = useState(article?.symptoms ?? '');
  const [causes, setCauses] = useState(article?.causes ?? '');
  const [prevention, setPrevention] = useState(article?.prevention_tips ?? '');
  const [homeCare, setHomeCare] = useState(article?.home_care_guidance ?? '');
  const [whenToSeeDoctor, setWhenToSeeDoctor] = useState(article?.when_to_see_doctor ?? '');
  const [emergency, setEmergency] = useState(article?.emergency_contact_info ?? '');
  const [reference, setReference] = useState(article?.reference ?? '');
  const [busy, setBusy] = useState(false);

  const isEdit = !!article;

  const onSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      if (isEdit) {
        const patch: Record<string, string> = {};
        if (symptoms !== (article.symptoms ?? '')) patch.symptoms = symptoms;
        if ((causes || null) !== (article.causes ?? null)) patch.causes = causes;
        if ((prevention || null) !== (article.prevention_tips ?? null)) patch.prevention_tips = prevention;
        if ((homeCare || null) !== (article.home_care_guidance ?? null)) patch.home_care_guidance = homeCare;
        if ((whenToSeeDoctor || null) !== (article.when_to_see_doctor ?? null)) patch.when_to_see_doctor = whenToSeeDoctor;
        if ((emergency || null) !== (article.emergency_contact_info ?? null)) patch.emergency_contact_info = emergency;
        if ((reference || null) !== (article.reference ?? null)) patch.reference = reference;
        if (Object.keys(patch).length === 0) {
          onClose();
          return;
        }
        await adminUpdateKnowledge(article.id, patch);
      } else {
        await adminCreateKnowledge({
          disease_name: diseaseName,
          symptoms,
          causes: causes || undefined,
          prevention_tips: prevention || undefined,
          home_care_guidance: homeCare || undefined,
          when_to_see_doctor: whenToSeeDoctor || undefined,
          emergency_contact_info: emergency || undefined,
          reference: reference || undefined,
        });
      }
      onSaved();
    } catch (e) {
      onError(getApiErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50, padding: 16 }}>
      <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} style={{ width: '100%', maxWidth: 720, maxHeight: '90vh', overflowY: 'auto' }}>
        <GlassCard className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 style={{ color: '#fff', fontSize: '18px', fontWeight: 700 }}>{isEdit ? `Edit: ${article.disease_name}` : 'New knowledge article'}</h3>
            <button onClick={onClose} style={{ color: 'rgba(255,255,255,0.5)', cursor: 'pointer', background: 'none', border: 'none' }}><X size={18} /></button>
          </div>
          <form onSubmit={onSave} className="space-y-3">
            <Field label="Disease name" value={diseaseName} onChange={setDiseaseName} disabled={isEdit} required minLength={2} maxLength={80} />
            <TextArea label="Symptoms" value={symptoms} onChange={setSymptoms} required rows={2} />
            <TextArea label="Causes" value={causes} onChange={setCauses} rows={2} />
            <TextArea label="Prevention tips" value={prevention} onChange={setPrevention} rows={2} />
            <TextArea label="Home care guidance" value={homeCare} onChange={setHomeCare} rows={2} />
            <TextArea label="When to see a doctor" value={whenToSeeDoctor} onChange={setWhenToSeeDoctor} rows={2} />
            <TextArea label="Emergency contact info" value={emergency} onChange={setEmergency} rows={2} />
            <Field label="Reference / source" value={reference} onChange={setReference} />
            <div className="flex justify-end gap-2 pt-2">
              <button type="button" onClick={onClose} style={{ padding: '8px 14px', borderRadius: '8px', background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)', color: 'rgba(255,255,255,0.7)', fontSize: '13px', fontWeight: 600, cursor: 'pointer' }}>Cancel</button>
              <button type="submit" disabled={busy} style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 14px', borderRadius: '8px', background: 'rgba(45,212,191,0.15)', border: '1px solid rgba(45,212,191,0.3)', color: '#5EEAD4', fontSize: '13px', fontWeight: 600, cursor: busy ? 'wait' : 'pointer', opacity: busy ? 0.5 : 1 }}>
                {busy ? <RefreshCw size={14} className="animate-spin" /> : <Save size={14} />} {isEdit ? 'Save changes' : 'Create'}
              </button>
            </div>
          </form>
        </GlassCard>
      </motion.div>
    </div>
  );
}

// ───────────────────────────────────────────────────────────────────────
// DataStatusTab — Gap 5: district coverage report
// ───────────────────────────────────────────────────────────────────────
function DataStatusTab() {
  const [data, setData] = useState<AdminDataStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [filter, setFilter] = useState('');
  const [banglaMap, setBanglaMap] = useState<Map<string, string> | null>(null);
  const [showBangla, setShowBangla] = useState(true);

  const load = useCallback(async () => {
    setLoading(true); setErr(null);
    try {
      setData(await adminDataStatus());
    } catch (e) {
      setErr(getApiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Load the EN -> BN name table once on mount; failures are silent (toggle hides it).
  useEffect(() => {
    loadDistrictBanglaMap()
      .then(setBanglaMap)
      .catch(() => setBanglaMap(new Map()));
  }, []);

  const visible = useMemo(() => {
    if (!data) return [];
    if (!filter) return data.items;
    const q = filter.toLowerCase();
    return data.items.filter((i) => {
      if (i.district.toLowerCase().includes(q)) return true;
      const bn = lookupBangla(banglaMap, i.district);
      if (bn && bn.toLowerCase().includes(q)) return true;
      return false;
    });
  }, [data, filter, banglaMap]);

  return (
    <GlassCard className="p-6">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
            District data coverage
          </h2>
          <p className="text-white/40 text-sm mt-0.5">
            Which districts are fully populated across hospitals, environment, and weekly history.
          </p>
        </div>
        <button
          onClick={load}
          disabled={loading}
          style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 14px', borderRadius: '8px', background: 'rgba(59,130,246,0.15)', border: '1px solid rgba(59,130,246,0.3)', color: '#93C5FD', fontSize: '13px', fontWeight: 600, cursor: 'pointer', opacity: loading ? 0.5 : 1 }}
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
        </button>
      </div>

      {err && <ErrorBanner msg={err} />}

      {data && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-5">
          <Stat label="Total districts" value={data.total_districts} color="#38BDF8" />
          <Stat label="Fully covered" value={data.fully_covered} color="#2DD4BF" />
          <Stat label="Missing coverage" value={data.missing_coverage} color="#F43F5E" />
        </div>
      )}

      <div className="mb-3 flex items-end gap-3">
        <div className="flex-1">
          <Field label="Filter districts" value={filter} onChange={setFilter} placeholder="Type a district name (English or Bangla)" />
        </div>
        <button
          onClick={() => setShowBangla((v) => !v)}
          title="Toggle Bangla name display"
          style={{
            display: 'flex', alignItems: 'center', gap: '6px',
            padding: '9px 14px', borderRadius: '8px',
            background: showBangla ? 'rgba(45,212,191,0.15)' : 'rgba(255,255,255,0.04)',
            border: showBangla ? '1px solid rgba(45,212,191,0.3)' : '1px solid rgba(255,255,255,0.1)',
            color: showBangla ? '#5EEAD4' : 'rgba(255,255,255,0.5)',
            fontSize: '12px', fontWeight: 600, cursor: 'pointer',
            whiteSpace: 'nowrap',
          }}
        >
          {showBangla ? 'অাট / Hide বাংলা' : 'Show বাংলা'}
        </button>
      </div>

      {loading ? <CenteredSpinner /> : !data ? null : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                {['District', 'Hospitals', 'Aggregate', 'Environment', 'Weekly rows', 'Status'].map((h) => (
                  <th key={h} style={{ padding: '10px 12px', textAlign: 'left', color: 'rgba(255,255,255,0.4)', fontWeight: 600, fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.6px' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {visible.map((i) => (
                <tr key={i.district} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                  <td style={{ padding: '10px 12px', color: '#fff' }}>
                    <div>{i.district}</div>
                    {showBangla && (() => {
                      const bn = lookupBangla(banglaMap, i.district);
                      return bn ? (
                        <div style={{ color: 'rgba(255,255,255,0.45)', fontSize: '11px', marginTop: 2, fontFamily: '"Noto Sans Bengali", "Hind Siliguri", sans-serif' }}>
                          {bn}
                        </div>
                      ) : null;
                    })()}
                  </td>
                  <td style={{ padding: '10px 12px', color: 'rgba(255,255,255,0.7)' }}>{i.hospitals}</td>
                  <td style={{ padding: '10px 12px' }}>{i.has_aggregate ? <Check color="#2DD4BF" /> : <Cross color="#F43F5E" />}</td>
                  <td style={{ padding: '10px 12px' }}>{i.has_environment ? <Check color="#2DD4BF" /> : <Cross color="#F43F5E" />}</td>
                  <td style={{ padding: '10px 12px', color: i.weekly_history_rows >= 8 ? 'rgba(45,212,191,0.9)' : 'rgba(255,255,255,0.6)' }}>{i.weekly_history_rows} {i.weekly_history_rows >= 8 ? '✓' : ''}</td>
                  <td style={{ padding: '10px 12px' }}>
                    {i.is_fully_covered
                      ? <span style={{ color: '#2DD4BF', fontSize: '11px', fontWeight: 700, padding: '3px 8px', borderRadius: '6px', background: 'rgba(45,212,191,0.12)', border: '1px solid rgba(45,212,191,0.3)' }}>COVERED</span>
                      : <span style={{ color: '#FBBF24', fontSize: '11px', fontWeight: 700, padding: '3px 8px', borderRadius: '6px', background: 'rgba(251,191,36,0.12)', border: '1px solid rgba(251,191,36,0.3)' }}>GAPS</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </GlassCard>
  );
}

// ───────────────────────────────────────────────────────────────────────
// ChatHistoryTab — Gap 6: cross-user chat conversations
// ───────────────────────────────────────────────────────────────────────
function ChatHistoryTab() {
  const [items, setItems] = useState<AdminChatHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [filterUser, setFilterUser] = useState('');
  const [selected, setSelected] = useState<AdminChatHistoryDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setErr(null);
    try {
      const data = await adminListChatHistory({ user_email: filterUser || undefined, limit: 50 });
      setItems(data.items);
    } catch (e) {
      setErr(getApiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [filterUser]);

  useEffect(() => { load(); }, [load]);

  const openConvo = async (id: string) => {
    setDetailLoading(true); setSelected(null);
    try {
      setSelected(await adminGetChatConversation(id));
    } catch (e) {
      setErr(getApiErrorMessage(e));
    } finally {
      setDetailLoading(false);
    }
  };

  return (
    <GlassCard className="p-6">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
            Chat history (all users)
          </h2>
          <p className="text-white/40 text-sm mt-0.5">
            Moderation feed -- inspect any conversation the chatbot has had.
          </p>
        </div>
        <button
          onClick={load}
          disabled={loading}
          style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 14px', borderRadius: '8px', background: 'rgba(59,130,246,0.15)', border: '1px solid rgba(59,130,246,0.3)', color: '#93C5FD', fontSize: '13px', fontWeight: 600, cursor: 'pointer', opacity: loading ? 0.5 : 1 }}
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
        </button>
      </div>

      <div className="mb-3">
        <Field label="Filter by user email" value={filterUser} onChange={setFilterUser} placeholder="someone@" />
      </div>

      {err && <ErrorBanner msg={err} />}

      {loading ? <CenteredSpinner /> : items.length === 0 ? <EmptyState text="No conversations match this filter." /> : (
        <div className="space-y-2">
          {items.map((c) => (
            <button
              key={c.conversation_id}
              onClick={() => openConvo(c.conversation_id)}
              style={{ display: 'block', width: '100%', textAlign: 'left', padding: '12px 14px', borderRadius: '10px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)', cursor: 'pointer' }}
            >
              <div className="flex items-center justify-between mb-1">
                <div style={{ color: '#fff', fontSize: '13px', fontWeight: 600 }}>{c.user_email ?? '(unknown user)'}</div>
                <div style={{ color: 'rgba(255,255,255,0.4)', fontSize: '11px' }}>
                  {c.last_active ? new Date(c.last_active).toLocaleString() : '—'} · {c.message_count} msgs
                </div>
              </div>
              {c.first_user_message && (
                <div style={{ color: 'rgba(255,255,255,0.55)', fontSize: '12px' }}>
                  <span style={{ color: 'rgba(255,255,255,0.35)' }}>first:</span> {c.first_user_message.slice(0, 180)}
                </div>
              )}
            </button>
          ))}
        </div>
      )}

      {(selected || detailLoading) && (
        <ConvoModal
          detail={selected}
          loading={detailLoading}
          onClose={() => setSelected(null)}
        />
      )}
    </GlassCard>
  );
}

function ConvoModal({ detail, loading, onClose }: {
  detail: AdminChatHistoryDetail | null;
  loading: boolean;
  onClose: () => void;
}) {
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50, padding: 16 }}>
      <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} style={{ width: '100%', maxWidth: 720, maxHeight: '90vh', overflowY: 'auto' }}>
        <GlassCard className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 style={{ color: '#fff', fontSize: '18px', fontWeight: 700 }}>Conversation</h3>
            <button onClick={onClose} style={{ color: 'rgba(255,255,255,0.5)', cursor: 'pointer', background: 'none', border: 'none' }}><X size={18} /></button>
          </div>
          {loading && <CenteredSpinner />}
          {detail && (
            <>
              <div style={{ color: 'rgba(255,255,255,0.5)', fontSize: '12px', marginBottom: 12 }}>
                {detail.user_email} · {detail.user_role ?? 'unknown role'} · {detail.messages.length} messages
              </div>
              <div className="space-y-3">
                {detail.messages.map((m) => (
                  <div key={m.id} style={{ padding: '10px 12px', borderRadius: '8px', background: m.role === 'user' ? 'rgba(56,189,248,0.08)' : 'rgba(45,212,191,0.08)', border: m.role === 'user' ? '1px solid rgba(56,189,248,0.2)' : '1px solid rgba(45,212,191,0.2)' }}>
                    <div style={{ color: 'rgba(255,255,255,0.4)', fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.6px', marginBottom: 4 }}>
                      {m.role} {m.detected_intent && `· ${m.detected_intent}`} {m.referenced_disease && `· ${m.referenced_disease}`}
                    </div>
                    <div style={{ color: '#fff', fontSize: '13.5px', whiteSpace: 'pre-wrap' }}>{m.content}</div>
                  </div>
                ))}
              </div>
            </>
          )}
        </GlassCard>
      </motion.div>
    </div>
  );
}

// ─── shared little UI helpers ────────────────────────────────────────────
function Field({ label, value, onChange, type = 'text', required, placeholder, disabled, minLength, maxLength }: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  required?: boolean;
  placeholder?: string;
  disabled?: boolean;
  minLength?: number;
  maxLength?: number;
}) {
  return (
    <label style={{ display: 'block' }}>
      <span style={{ display: 'block', color: 'rgba(255,255,255,0.5)', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.6px', marginBottom: 4 }}>{label}</span>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        required={required}
        placeholder={placeholder}
        disabled={disabled}
        minLength={minLength}
        maxLength={maxLength}
        style={{
          width: '100%', padding: '9px 12px', borderRadius: '8px',
          background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
          color: '#fff', fontSize: '13.5px', outline: 'none',
          opacity: disabled ? 0.5 : 1,
        }}
      />
    </label>
  );
}

function SelectField({ label, value, onChange, options }: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: Array<{ value: string; label: string }>;
}) {
  return (
    <label style={{ display: 'block' }}>
      <span style={{ display: 'block', color: 'rgba(255,255,255,0.5)', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.6px', marginBottom: 4 }}>{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={{
          width: '100%', padding: '9px 12px', borderRadius: '8px',
          background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
          color: '#fff', fontSize: '13.5px', outline: 'none',
        }}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value} style={{ background: '#0d1117', color: '#fff' }}>{o.label}</option>
        ))}
      </select>
    </label>
  );
}

function TextArea({ label, value, onChange, required, rows = 3 }: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  required?: boolean;
  rows?: number;
}) {
  return (
    <label style={{ display: 'block' }}>
      <span style={{ display: 'block', color: 'rgba(255,255,255,0.5)', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.6px', marginBottom: 4 }}>{label}</span>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        required={required}
        rows={rows}
        style={{
          width: '100%', padding: '9px 12px', borderRadius: '8px',
          background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
          color: '#fff', fontSize: '13px', outline: 'none', fontFamily: 'inherit',
          resize: 'vertical',
        }}
      />
    </label>
  );
}

function Stat({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div style={{ padding: '14px 18px', borderRadius: '10px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
      <div style={{ color, fontSize: '28px', fontWeight: 800, fontFamily: 'JetBrains Mono, monospace' }}>{value}</div>
      <div style={{ color: 'rgba(255,255,255,0.5)', fontSize: '12px' }}>{label}</div>
    </div>
  );
}

function CenteredSpinner() {
  return (
    <div className="flex justify-center py-12">
      <div style={{ width: 32, height: 32, border: '2px solid #3b82f6', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return <div style={{ textAlign: 'center', padding: '32px 0', color: 'rgba(255,255,255,0.4)' }}>{text}</div>;
}

function ErrorBanner({ msg }: { msg: string }) {
  return (
    <div style={{ marginBottom: 12, padding: '10px 14px', borderRadius: '8px', background: 'rgba(244,63,94,0.08)', border: '1px solid rgba(244,63,94,0.2)', color: '#FCA5A5', fontSize: '13px' }}>{msg}</div>
  );
}

function Check({ color }: { color: string }) { return <span style={{ color, fontSize: 14 }}>✓</span>; }
function Cross({ color }: { color: string }) { return <span style={{ color, fontSize: 14 }}>✗</span>; }
