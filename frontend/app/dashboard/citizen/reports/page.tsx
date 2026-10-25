'use client';

import { useState, useEffect } from 'react';
import {
  AlertTriangle, Send, MapPin, Camera, Clock, CheckCircle2,
  ShieldCheck, XCircle, Bell, RefreshCw
} from 'lucide-react';
import { useAuth } from '@/lib/auth';
import {
  submitCitizenReport, listCitizenMyReports, withdrawCitizenReport,
  getPublicAlerts, CitizenReportItem
} from '@/lib/api';

export default function CitizenReportsPage() {
  const { user } = useAuth();
  const [reports, setReports] = useState<CitizenReportItem[]>([]);
  const [publicAlerts, setPublicAlerts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // Form State
  const [text, setText] = useState('');
  const [label, setLabel] = useState('flood_incident');
  const [severity, setSeverity] = useState('medium');
  const [district, setDistrict] = useState('Feni');
  const [upazila, setUpazila] = useState('Feni Sadar');
  const [imageUrl, setImageUrl] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitFeedback, setSubmitFeedback] = useState<{ msg: string; type: 'success' | 'error' } | null>(null);

  useEffect(() => {
    loadData();
  }, [user]);

  async function loadData() {
    setLoading(true);
    try {
      if (user?.email) {
        const myReports = await listCitizenMyReports(user.email);
        setReports(myReports || []);
      }
      const alerts = await getPublicAlerts();
      setPublicAlerts(alerts || []);
    } catch (err) {
      console.warn('Error loading citizen data:', err);
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setSubmitFeedback(null);

    try {
      const res = await submitCitizenReport({
        text,
        label,
        severity,
        district,
        upazila,
        image_url: imageUrl || undefined,
        reporter_email: user?.email,
      });

      setSubmitFeedback({
        msg: 'Report submitted successfully. Authorities will review and verify your report.',
        type: 'success',
      });
      setText('');
      setImageUrl('');
      await loadData();
      setTimeout(() => setSubmitFeedback(null), 4000);
    } catch (err: any) {
      setSubmitFeedback({
        msg: err.response?.data?.detail || 'Failed to submit report. Please try again.',
        type: 'error',
      });
    } finally {
      setSubmitting(false);
    }
  }

  async function handleWithdraw(id: string) {
    try {
      await withdrawCitizenReport(id);
      await loadData();
    } catch (err) {
      console.error(err);
    }
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-6 rounded-2xl border border-white/10 bg-slate-900/60 backdrop-blur-xl">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-amber-500 to-rose-500 flex items-center justify-center shadow-lg shadow-rose-500/20">
            <AlertTriangle className="text-white" size={28} />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white tracking-tight">Public Incident Reporting & Safety Portal</h1>
            <p className="text-slate-400 text-sm">Submit community flood or water contamination observations and monitor verified statuses</p>
          </div>
        </div>

        <button
          onClick={loadData}
          className="p-2.5 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 text-slate-300 transition"
          title="Refresh Data"
        >
          <RefreshCw size={18} />
        </button>
      </div>

      {/* Public Safety Alerts */}
      {publicAlerts.length > 0 && (
        <div className="p-4 rounded-2xl border border-red-500/30 bg-red-500/10 backdrop-blur flex items-start gap-3">
          <Bell className="text-red-400 shrink-0 mt-0.5" size={20} />
          <div>
            <div className="font-bold text-white text-sm">Active Official Alert: {publicAlerts[0].title_en}</div>
            <div className="text-xs text-red-200 mt-0.5">{publicAlerts[0].message_en}</div>
            <div className="text-xs text-red-300/80 font-bengali mt-0.5">{publicAlerts[0].message_bn}</div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Form Column */}
        <form onSubmit={handleSubmit} className="lg:col-span-2 p-6 rounded-2xl border border-white/10 bg-slate-900/40 backdrop-blur space-y-4 h-fit">
          <h2 className="text-base font-bold text-white">Report New Incident</h2>
          <p className="text-xs text-slate-400">All submissions are unverified by default until reviewed by emergency health workers.</p>

          <div>
            <label className="block text-xs uppercase font-medium text-slate-400 mb-1">Incident Category</label>
            <select
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2 text-white text-sm outline-none"
            >
              <option value="flood_incident">Flood / Rising Water Level</option>
              <option value="water_contamination">Contaminated Drinking Water</option>
              <option value="disease_cluster">Suspected Diarrhea / Fever Cluster</option>
              <option value="supply_shortage">Emergency Medical Shortage</option>
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs uppercase font-medium text-slate-400 mb-1">District</label>
              <input
                type="text"
                required
                value={district}
                onChange={(e) => setDistrict(e.target.value)}
                className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2 text-white text-sm outline-none"
              />
            </div>
            <div>
              <label className="block text-xs uppercase font-medium text-slate-400 mb-1">Upazila / Union</label>
              <input
                type="text"
                required
                value={upazila}
                onChange={(e) => setUpazila(e.target.value)}
                className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2 text-white text-sm outline-none"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs uppercase font-medium text-slate-400 mb-1">Severity Level</label>
            <select
              value={severity}
              onChange={(e) => setSeverity(e.target.value)}
              className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2 text-white text-sm outline-none"
            >
              <option value="low">Low (Noticeable change)</option>
              <option value="medium">Medium (Roads or yards submerged)</option>
              <option value="high">High (Homes inundated / potable water lost)</option>
              <option value="critical">Critical (Immediate rescue required)</option>
            </select>
          </div>

          <div>
            <label className="block text-xs uppercase font-medium text-slate-400 mb-1">Incident Description</label>
            <textarea
              required
              rows={3}
              placeholder="Describe what you observed (e.g. embankment breach, water color change, affected families)..."
              value={text}
              onChange={(e) => setText(e.target.value)}
              className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2 text-white text-sm outline-none resize-none"
            />
          </div>

          <div>
            <label className="block text-xs uppercase font-medium text-slate-400 mb-1">Optional Photo URL</label>
            <input
              type="url"
              placeholder="https://example.com/photo.jpg"
              value={imageUrl}
              onChange={(e) => setImageUrl(e.target.value)}
              className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2 text-white text-sm outline-none"
            />
          </div>

          {submitFeedback && (
            <div className={`p-3 rounded-xl text-xs ${
              submitFeedback.type === 'success' ? 'bg-emerald-500/20 border border-emerald-500/40 text-emerald-300' :
              'bg-red-500/20 border border-red-500/40 text-red-300'
            }`}>
              {submitFeedback.msg}
            </div>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="w-full py-2.5 rounded-xl bg-gradient-to-r from-amber-600 to-rose-600 hover:from-amber-500 hover:to-rose-500 text-white font-semibold text-sm transition shadow-lg shadow-rose-500/20 disabled:opacity-50"
          >
            {submitting ? 'Submitting...' : 'Broadcast Community Report'}
          </button>
        </form>

        {/* Reports Tracker List */}
        <div className="lg:col-span-3 space-y-4">
          <h2 className="text-base font-bold text-white">My Submitted Incident Reports</h2>
          <div className="space-y-3">
            {reports.map((r) => (
              <div key={r.id} className="p-5 rounded-2xl border border-white/10 bg-slate-900/40 backdrop-blur space-y-3">
                <div className="flex justify-between items-start">
                  <div>
                    <h3 className="font-bold text-white text-sm capitalize">{r.label.replace('_', ' ')}</h3>
                    <div className="text-xs text-slate-400 flex items-center gap-1.5 mt-0.5">
                      <MapPin size={12} /> {r.district} • {r.upazila || 'General Zone'}
                    </div>
                  </div>
                  <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold uppercase ${
                    r.status === 'verified' ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40' :
                    r.status === 'withdrawn' ? 'bg-slate-500/20 text-slate-300 border border-slate-500/40' :
                    'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                  }`}>
                    {r.status || 'unverified'}
                  </span>
                </div>

                <p className="text-xs text-slate-300">{r.text}</p>

                <div className="flex items-center justify-between text-xs text-slate-400 pt-2 border-t border-white/5">
                  <span>Severity: <strong className="text-white capitalize">{r.severity}</strong></span>
                  {r.status === 'unverified' && (
                    <button
                      onClick={() => handleWithdraw(r.id)}
                      className="px-2.5 py-1 rounded-lg border border-white/10 hover:bg-white/5 text-slate-400 hover:text-white transition"
                    >
                      Withdraw Report
                    </button>
                  )}
                </div>
              </div>
            ))}
            {reports.length === 0 && (
              <div className="text-center py-12 text-slate-500 bg-slate-900/20 rounded-2xl border border-white/5">
                You have not submitted any incident reports yet.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
