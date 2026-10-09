'use client';

import { useState } from 'react';
import { ShieldOff, Loader2, X, CheckCircle, AlertCircle } from 'lucide-react';
import { demoteMeToCitizen } from '@/lib/api';
import { getApiErrorMessage } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { setAuthToken } from '@/lib/auth';

export default function DemoteToCitizenButton() {
  const { user, refreshUser } = useAuth();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  if (!user) return null;
  if (user.role !== 'admin') return null;

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setErr(null);
    try {
      const t = await demoteMeToCitizen();
      setAuthToken(t.access_token);
      setOpen(false);
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
        title="Self-demote: turn your own admin account into a citizen"
        style={{
          display: 'flex', alignItems: 'center', gap: '6px',
          padding: '6px 12px', borderRadius: '8px',
          background: 'rgba(168,85,247,0.12)', border: '1px solid rgba(168,85,247,0.35)',
          color: '#D8B4FE', fontSize: '12px', fontWeight: 600, cursor: 'pointer',
        }}
      >
        <ShieldOff size={13} /> Demote me
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
              border: '1px solid rgba(168,85,247,0.3)',
              borderRadius: 16, padding: 24,
              boxShadow: '0 20px 60px rgba(0,0,0,0.6)',
            }}
          >
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center gap-2">
                <ShieldOff size={20} className="text-purple-300" />
                <h3 style={{ color: '#fff', fontSize: 17, fontWeight: 700 }}>
                  Demote yourself to citizen?
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
              This will switch your account from <code className="text-red-300">admin</code> to{' '}
              <code className="text-blue-300">citizen</code>. You will lose access to the Admin Panel,
              user management, and all admin-only endpoints.
            </p>
            <p className="text-white/50 text-xs mb-4 leading-relaxed">
              The server refuses this action if you are the only admin in the database --
              promote someone else to admin first, or sign up a second admin via{' '}
              <code className="text-amber-300">/auth/promote-me</code> with the deployer's{' '}
              <code className="text-amber-300">BOOTSTRAP_TOKEN</code>.
            </p>

            <form onSubmit={onSubmit} className="space-y-3">
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
                  disabled={busy}
                  className="px-4 py-2 rounded-lg text-xs font-semibold flex items-center gap-2 disabled:opacity-50"
                  style={{ background: 'rgba(168,85,247,0.25)', color: '#E9D5FF', border: '1px solid rgba(168,85,247,0.4)' }}
                >
                  {busy ? <Loader2 size={13} className="animate-spin" /> : <CheckCircle size={13} />}
                  Yes, demote me
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
