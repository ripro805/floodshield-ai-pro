'use client';

/**
 * HospitalImportModal -- admin-only "Import CSV" flow.
 *
 * Renders a file picker (and a small template-link row), then on
 * submit POSTs the chosen file to /admin/hospitals/import.  Shows a
 * three-state UI:
 *   - idle:    file picker + reset toggle + template link
 *   - loading: spinner + "Importing…"
 *   - done:    summary card (deduped rows, districts affected, etc.)
 *              plus a "close" button that triggers a directory
 *              refetch in the parent.
 *
 * The modal is admin-only by route -- the server returns 403 if a
 * non-admin posts.  We also hide the trigger button in the parent
 * unless `user?.role === 'admin'`.
 */
import { useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Upload, Loader2, X, AlertCircle, CheckCircle2, Download, FileText } from 'lucide-react';
import { importHospitalCsv, getHospitalImportTemplate, type HospitalImportSummary } from '@/lib/api';
import { getApiErrorMessage } from '@/lib/api';

interface HospitalImportModalProps {
  open: boolean;
  onClose: () => void;
  onImported: (summary: HospitalImportSummary) => void;
}

export default function HospitalImportModal({ open, onClose, onImported }: HospitalImportModalProps) {
  const [file, setFile] = useState<File | null>(null);
  const [reset, setReset] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<HospitalImportSummary | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const reset2 = () => {
    setFile(null);
    setError(null);
    setSummary(null);
    if (inputRef.current) inputRef.current.value = '';
  };

  const close = () => {
    reset2();
    onClose();
  };

  const submit = async () => {
    if (!file) {
      setError('Pick a .csv file first.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const s = await importHospitalCsv(file, { reset });
      setSummary(s);
      onImported(s);
    } catch (e) {
      setError(getApiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  };

  const downloadTemplate = async () => {
    try {
      const blob = await getHospitalImportTemplate();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'hospital_directory_template.csv';
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(getApiErrorMessage(e));
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(6px)' }}
          onClick={close}
        >
          <motion.div
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 20, opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-lg rounded-2xl border p-6"
            style={{
              background: 'linear-gradient(180deg, rgba(15,23,42,0.96), rgba(7,12,24,0.96))',
              borderColor: 'rgba(255,255,255,0.08)',
            }}
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-white flex items-center gap-2">
                <Upload size={16} className="text-blue-300" /> Import hospital CSV
              </h3>
              <button
                onClick={close}
                className="w-8 h-8 rounded-lg flex items-center justify-center text-white/60 hover:text-white hover:bg-white/5"
                aria-label="Close"
              >
                <X size={16} />
              </button>
            </div>

            {/* ── Idle / form ─────────────────────────────────────── */}
            {!summary && !loading && (
              <>
                <p className="text-white/60 text-sm mb-4">
                  Upload a CSV that matches the{' '}
                  <button
                    onClick={downloadTemplate}
                    className="underline text-blue-300 hover:text-blue-200 inline-flex items-center gap-1"
                  >
                    <Download size={11} /> template
                  </button>
                  .  The server uses the same weighted-mean dedupe as
                  the CLI seeder, so re-uploading the same file is a
                  no-op (idempotent).
                </p>

                <div
                  className="rounded-xl border-2 border-dashed p-6 text-center cursor-pointer hover:border-blue-300/40 transition"
                  style={{
                    borderColor: 'rgba(255,255,255,0.18)',
                    background: 'rgba(255,255,255,0.02)',
                  }}
                  onClick={() => inputRef.current?.click()}
                  onDragOver={(e) => { e.preventDefault(); }}
                  onDrop={(e) => {
                    e.preventDefault();
                    const f = e.dataTransfer.files?.[0];
                    if (f && f.name.toLowerCase().endsWith('.csv')) {
                      setFile(f);
                      setError(null);
                    } else {
                      setError('Drop a .csv file.');
                    }
                  }}
                >
                  <FileText size={28} className="text-white/40 mx-auto mb-2" />
                  {file ? (
                    <p className="text-sm text-white">
                      <span className="font-mono">{file.name}</span>
                      <span className="text-white/40"> · {(file.size / 1024).toFixed(1)} KB</span>
                    </p>
                  ) : (
                    <p className="text-sm text-white/50">
                      Click or drop a <span className="text-white/70">.csv</span> file
                    </p>
                  )}
                  <input
                    ref={inputRef}
                    type="file"
                    accept=".csv,text/csv"
                    className="hidden"
                    onChange={(e) => {
                      const f = e.target.files?.[0] ?? null;
                      if (f && !f.name.toLowerCase().endsWith('.csv')) {
                        setError('Must be a .csv file.');
                        setFile(null);
                        return;
                      }
                      setFile(f);
                      setError(null);
                    }}
                  />
                </div>

                <label className="flex items-center gap-2 mt-4 text-sm text-white/70 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={reset}
                    onChange={(e) => setReset(e.target.checked)}
                    className="accent-rose-500"
                  />
                  Wipe existing hospitals before importing
                  <span className="text-white/40 text-xs">(destructive — coverage backfill is skipped)</span>
                </label>

                {error && (
                  <p className="mt-3 text-rose-300 text-sm flex items-center gap-1">
                    <AlertCircle size={12} /> {error}
                  </p>
                )}

                <div className="mt-5 flex items-center justify-end gap-2">
                  <button
                    onClick={close}
                    className="px-3 py-2 rounded-lg text-sm text-white/70 hover:text-white hover:bg-white/5"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={submit}
                    disabled={!file}
                    className="px-4 py-2 rounded-lg text-sm font-semibold text-white disabled:opacity-40"
                    style={{ background: 'linear-gradient(135deg, #38BDF8, #2DD4BF)' }}
                  >
                    Import
                  </button>
                </div>
              </>
            )}

            {/* ── Loading ─────────────────────────────────────────── */}
            {loading && (
              <div className="py-10 flex flex-col items-center gap-3 text-white/70">
                <Loader2 size={28} className="animate-spin text-blue-300" />
                <p className="text-sm">Importing & rebuilding district rollups…</p>
              </div>
            )}

            {/* ── Done summary ────────────────────────────────────── */}
            {summary && !loading && (
              <div>
                <div className="flex items-center gap-2 text-emerald-300 mb-3">
                  <CheckCircle2 size={16} /> Import complete
                </div>

                <div className="grid grid-cols-2 gap-2 mb-3">
                  <Stat label="Deduped rows" value={summary.deduped_rows} />
                  <Stat label="Districts" value={summary.districts} />
                  <Stat label="Affected" value={summary.hospitals_affected} />
                  <Stat label="Rollups rebuilt" value={summary.rollups_built} />
                  {summary.backfilled > 0 && (
                    <Stat label="Backfilled" value={summary.backfilled} accent="amber" />
                  )}
                </div>

                {summary.skipped.length > 0 && (
                  <details className="mb-3 rounded-lg p-3" style={{ background: 'rgba(251,191,36,0.08)' }}>
                    <summary className="text-amber-200 text-xs font-semibold cursor-pointer">
                      {summary.skipped.length} row(s) skipped — click to inspect
                    </summary>
                    <ul className="mt-2 text-white/70 text-xs space-y-0.5 max-h-40 overflow-auto">
                      {summary.skipped.map((s, i) => (
                        <li key={i} className="font-mono">{s}</li>
                      ))}
                    </ul>
                  </details>
                )}

                <p className="text-white/40 text-xs mb-4">
                  data_source stamped to <code className="text-white/60">{summary.data_source}</code> on every row.
                </p>

                <div className="flex items-center justify-end">
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

function Stat({ label, value, accent }: { label: string; value: number; accent?: 'amber' }) {
  return (
    <div
      className="rounded-lg p-3"
      style={{
        background: accent === 'amber' ? 'rgba(251,191,36,0.06)' : 'rgba(255,255,255,0.04)',
      }}
    >
      <p className="text-[10px] uppercase tracking-wider text-white/40">{label}</p>
      <p className="text-lg font-bold font-mono text-white mt-0.5">{value}</p>
    </div>
  );
}
