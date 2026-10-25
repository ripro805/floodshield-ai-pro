'use client';

import { useEffect, useState } from 'react';
import { Shield, KeyRound, Loader2, X, CheckCircle, AlertCircle } from 'lucide-react';
import { getBootstrapStatus, promoteMeToAdmin } from '@/lib/api';
import { getApiErrorMessage } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { setAuthToken } from '@/lib/auth';

export default function PromoteToAdminButton() {
  const { user, refreshUser } = useAuth();
  const [status, setStatus] = useState<{ usable: boolean; admin_count: number } | null>(null);
  const [open, setOpen] = useState(false);
  const [token, setToken] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!user) {
      setStatus(null);
      return;
    }
    // Only non-admins ever see this.
    if (user.role === 'admin') {
      setStatus({ usable: false, admin_count: 0 });
      return;
    }
    getBootstrapStatus()
      .then((s) => setStatus({ usable: s.usable, admin_count: s.admin_count }))
      .catch(() => setStatus({ usable: false, admin_count: 0 }));
  }, [user]);

  if (!user) return null;
  if (user.role === 'admin') return null;
  if (!status) return null;
  if (!status.usable) return null;

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setErr(null);
    try {
      const t = await promoteMeToAdmin(token.trim());
      setAuthToken(t.access_token);
      setOpen(false);
      setToken('');
      await refreshUser();
    } catch (e) {
      setErr(getApiErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        title="One-time bootstrap: this server has no admin yet. Use the deployer's BOOTSTRAP_TOKEN to promote your account to admin."
        style={{
          display: 'flex', alignItems: 'center', gap: '6px',
          padding: '6px 12px', borderRadius: '8px',
          background: 'rgba(244,63,94,0.12)', border: '1px solid rgba(244,63,94,0.35)',
          color: '#FCA5A5', fontSize: '12px', fontWeight: 600, cursor: 'pointer',
        }}
      >
        <Shield size={13} /> Become first admin
      </button>

      {open && (
        <div
          role="dialog"
          style={{
            position: 'fixed', inset: 0, zIndex: 100,
            background: 'rgba(0,0,0,0.65)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            padding: 16,
          }}
          onClick={(e) => { if (e.target === e.currentTarget) setOpen(false); }}
        >
          <div
            style={{
              width: '100%', maxWidth: 460,
              background: '#0d1117',
              border: '1px solid rgba(244,63,94,0.3)',
              borderRadius: 16, padding: 24,
              boxShadow: '0 20px 60px rgba(0,0,0,0.6)',
            }}
          >
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center gap-2">
                <Shield size={20} className="text-red-400" />
                <h3 style={{ color: '#fff', fontSize: 17, fontWeight: 700 }}>
                  Bootstrap the first admin
                </h3>
              </div>
              <button
                onClick={() => setOpen(false)}
                style={{ background: 'transparent', border: 'none', color: 'rgba(255,255,255,0.5)', cursor: 'pointer' }}
                aria-label="Close"
              >
                <X size={18} />
              </button>
            </div>

            <p className="text-white/60 text-sm mb-4 leading-relaxed">
              This server has <strong className="text-white">no admin yet</strong> ({status.admin_count} currently).
              If you&apos;re the deployer, paste the <code className="text-amber-300">BOOTSTRAP_TOKEN</code> from
              the server&apos;s <code className="text-amber-300">.env</code> to promote your account to <code className="text-red-300">admin</code>.
              After the first admin is created, this option disappears forever.
            </p>

            <form onSubmit={onSubmit} className="space-y-3">
              <label className="block">
                <span className="block text-[11px] font-semibold text-white/50 uppercase tracking-wider mb-1.5">
                  Bootstrap token
                </span>
                <div className="relative">
                  <KeyRound size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-white/40" />
                  <input
                    type="password"
                    value={token}
                    onChange={(e) => setToken(e.target.value)}
                    placeholder="Paste BOOTSTRAP_TOKEN here"
                    required
                    autoFocus
                    style={{
                      width: '100%', padding: '10px 12px 10px 36px',
                      borderRadius: 8, background: 'rgba(255,255,255,0.04)',
                      border: '1px solid rgba(255,255,255,0.1)',
                      color: '#fff', fontSize: 14, outline: 'none',
                      fontFamily: 'JetBrains Mono, monospace',
                    }}
                  />
                </div>
              </label>

              {err && (
                <div className="flex items-start gap-2 p-3 rounded-lg"
                  style={{ background: 'rgba(244,63,94,0.08)', border: '1px solid rgba(244,63,94,0.2)' }}>
                  <AlertCircle size={14} className="text-red-400 mt-0.5 shrink-0" />
                  <p className="text-red-200 text-xs">{err}</p>
                </div>
              )}

              <div className="flex items-center justify-end gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  className="px-3 py-2 rounded-lg text-xs font-semibold"
                  style={{ background: 'rgba(255,255,255,0.06)', color: 'rgba(255,255,255,0.7)' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={busy || !token}
                  className="px-4 py-2 rounded-lg text-xs font-semibold flex items-center gap-2 disabled:opacity-50"
                  style={{ background: 'rgba(244,63,94,0.25)', color: '#FCA5A5', border: '1px solid rgba(244,63,94,0.4)' }}
                >
                  {busy ? <Loader2 size={13} className="animate-spin" /> : <CheckCircle size={13} />}
                  Promote me to admin
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
