'use client';

/**
 * HospitalIssueModal -- the "Report an issue" flow on a hospital's
 * detail card.  Distinct from the Edit modal (which is for ops
 * users with write access): this is for *anyone* who can see the
 * directory, to flag "the phone number is wrong", "the facility is
 * closed", etc.
 *
 * On success the modal shows the resulting issue ID and a
 * confirmation, and the parent (detail modal) re-fetches the
 * per-hospital issue list so a "Recent reports" panel can surface
 * the freshly-raised ticket.
 */
import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Loader2, X, AlertCircle, CheckCircle2, Flag, ChevronDown,
} from 'lucide-react';
import { useMutation } from '@tanstack/react-query';
import {
  createHospitalIssue, HOSPITAL_ISSUE_CATEGORIES, type HospitalIssueCategory,
  type HospitalIssue,
} from '@/lib/api';
import { getApiErrorMessage } from '@/lib/api';

interface HospitalIssueModalProps {
  hospitalId: string;
  hospitalName: string;
  open: boolean;
  onClose: () => void;
  onCreated: (issue: HospitalIssue) => void;
}

export default function HospitalIssueModal({
  hospitalId, hospitalName, open, onClose, onCreated,
}: HospitalIssueModalProps) {
  const [category, setCategory] = useState<HospitalIssueCategory>('phone_wrong');
  const [description, setDescription] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<HospitalIssue | null>(null);

  const mutation = useMutation({
    mutationFn: () => createHospitalIssue(hospitalId, {
      category,
      description: description.trim(),
    }),
    onSuccess: (issue) => {
      setCreated(issue);
      onCreated(issue);
    },
    onError: (e) => setError(getApiErrorMessage(e)),
  });

  const reset = () => {
    setCategory('phone_wrong');
    setDescription('');
    setError(null);
    setCreated(null);
  };

  const close = () => {
    reset();
    onClose();
  };

  const submit = () => {
    setError(null);
    if (description.trim().length < 4) {
      setError('Add a short description (4+ characters) so an admin can act on it.');
      return;
    }
    mutation.mutate();
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[60] flex items-center justify-center p-4"
          style={{ background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(6px)' }}
          onClick={close}
        >
          <motion.div
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 20, opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-md rounded-2xl border p-6"
            style={{
              background: 'linear-gradient(180deg, rgba(15,23,42,0.96), rgba(7,12,24,0.96))',
              borderColor: 'rgba(255,255,255,0.08)',
            }}
          >
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-lg font-bold text-white flex items-center gap-2">
                <Flag size={16} className="text-amber-300" /> Report an issue
              </h3>
              <button
                onClick={close}
                className="w-8 h-8 rounded-lg flex items-center justify-center text-white/60 hover:text-white hover:bg-white/5"
                aria-label="Close"
              >
                <X size={16} />
              </button>
            </div>
            <p className="text-white/50 text-xs mb-4">
              {hospitalName} · Reports go to the admin inbox.
            </p>

            {!created && !mutation.isPending && (
              <>
                <label className="block mb-3">
                  <span className="text-[10px] uppercase tracking-wider text-white/50">What&apos;s wrong?</span>
                  <div className="relative mt-0.5">
                    <select
                      value={category}
                      onChange={(e) => setCategory(e.target.value as HospitalIssueCategory)}
                      className="w-full appearance-none rounded-lg px-2 py-2 pr-8 text-sm text-white outline-none border"
                      style={{ background: 'rgba(255,255,255,0.04)', borderColor: 'rgba(255,255,255,0.08)' }}
                    >
                      {HOSPITAL_ISSUE_CATEGORIES.map((c) => (
                        <option key={c.value} value={c.value} style={{ background: '#060B14' }}>
                          {c.label}
                        </option>
                      ))}
                    </select>
                    <ChevronDown size={14} className="absolute right-2 top-1/2 -translate-y-1/2 text-white/40 pointer-events-none" />
                  </div>
                </label>

                <label className="block">
                  <span className="text-[10px] uppercase tracking-wider text-white/50">Describe what you saw</span>
                  <textarea
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder='e.g. "Phone rings but no one picks up" or "Closed when I went on 12 March"'
                    rows={4}
                    maxLength={1000}
                    className="mt-0.5 w-full rounded-lg px-2 py-1.5 text-sm text-white outline-none border resize-y"
                    style={{ background: 'rgba(255,255,255,0.04)', borderColor: 'rgba(255,255,255,0.08)' }}
                  />
                  <span className="text-[10px] text-white/40">{description.length}/1000</span>
                </label>

                {error && (
                  <p className="mt-2 text-rose-300 text-sm flex items-center gap-1">
                    <AlertCircle size={12} /> {error}
                  </p>
                )}

                <div className="mt-4 flex items-center justify-end gap-2">
                  <button
                    onClick={close}
                    className="px-3 py-2 rounded-lg text-sm text-white/70 hover:text-white hover:bg-white/5"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={submit}
                    disabled={mutation.isPending}
                    className="px-4 py-2 rounded-lg text-sm font-semibold text-white disabled:opacity-40 inline-flex items-center gap-2"
                    style={{ background: 'linear-gradient(135deg, #F59E0B, #F43F5E)' }}
                  >
                    {mutation.isPending ? <Loader2 size={12} className="animate-spin" /> : <Flag size={12} />}
                    Send report
                  </button>
                </div>
              </>
            )}

            {mutation.isPending && (
              <div className="py-8 flex flex-col items-center gap-3 text-white/70">
                <Loader2 size={28} className="animate-spin text-amber-300" />
                <p className="text-sm">Sending to admin inbox…</p>
              </div>
            )}

            {created && !mutation.isPending && (
              <div>
                <div className="flex items-center gap-2 text-emerald-300 mb-3">
                  <CheckCircle2 size={16} /> Report sent
                </div>
                <p className="text-white/70 text-sm">
                  Thanks — an admin will review <code className="text-white/90">{created.id.slice(0, 8)}</code> and update the
                  hospital record if needed. You can close this dialog.
                </p>
                <div className="mt-4 flex items-center justify-end">
                  <button
                    onClick={close}
                    className="px-4 py-2 rounded-lg text-sm font-semibold text-white"
                    style={{ background: 'linear-gradient(135deg, #38BDF8, #2DD4BF)' }}
                  >
                    Done
                  </button>
                </div>
              </div>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
