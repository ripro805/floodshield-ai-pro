'use client';

import { useState, useEffect } from 'react';
import {
  ClipboardList, CheckCircle2, Clock, AlertTriangle, MapPin,
  Send, Save, Activity, ShieldAlert, Users, Package, RefreshCw
} from 'lucide-react';
import { useAuth } from '@/lib/auth';
import {
  listFieldTasks, updateFieldTaskStatus, listFieldVisitLogs,
  createFieldVisitLog, FieldTask, FieldVisitLog
} from '@/lib/api';

export default function FieldOperationsPage() {
  const { user } = useAuth();
  const [tasks, setTasks] = useState<FieldTask[]>([]);
  const [visitLogs, setVisitLogs] = useState<FieldVisitLog[]>([]);
  const [activeTab, setActiveTab] = useState<'tasks' | 'log_visit' | 'history'>('tasks');
  const [loading, setLoading] = useState<boolean>(true);

  // Visit Form State
  const [locationName, setLocationName] = useState('');
  const [district, setDistrict] = useState('Feni');
  const [upazila, setUpazila] = useState('Parshuram');
  const [households, setHouseholds] = useState<number>(15);
  const [casesCount, setCasesCount] = useState<number>(3);
  const [diseases, setDiseases] = useState('Acute Watery Diarrhoea, Cholera');
  const [orsDistributed, setOrsDistributed] = useState<number>(30);
  const [waterTabsDistributed, setWaterTabsDistributed] = useState<number>(60);
  const [referrals, setReferrals] = useState<number>(1);
  const [urgentShortage, setUrgentShortage] = useState('');
  const [notes, setNotes] = useState('');

  const [submittingLog, setSubmittingLog] = useState(false);
  const [logSuccess, setLogSuccess] = useState('');
  const [draftSaved, setDraftSaved] = useState(false);

  useEffect(() => {
    // Restore cached draft from localStorage if present
    const cached = localStorage.getItem('field_visit_draft');
    if (cached) {
      try {
        const d = JSON.parse(cached);
        setLocationName(d.locationName || '');
        setDistrict(d.district || 'Feni');
        setUpazila(d.upazila || 'Parshuram');
        setHouseholds(d.households || 15);
        setCasesCount(d.casesCount || 3);
        setDiseases(d.diseases || '');
        setOrsDistributed(d.orsDistributed || 30);
        setWaterTabsDistributed(d.waterTabsDistributed || 60);
        setReferrals(d.referrals || 1);
        setUrgentShortage(d.urgentShortage || '');
        setNotes(d.notes || '');
      } catch (e) {
        console.warn('Failed to parse cached draft');
      }
    }
    loadData();
  }, []);

  async function loadData() {
    setLoading(true);
    try {
      const taskRes = await listFieldTasks();
      setTasks(taskRes || []);

      const logsRes = await listFieldVisitLogs();
      setVisitLogs(logsRes || []);
    } catch (e) {
      console.warn('Error loading field operations:', e);
    } finally {
      setLoading(false);
    }
  }

  function handleSaveDraft() {
    const draft = {
      locationName, district, upazila, households,
      casesCount, diseases, orsDistributed, waterTabsDistributed,
      referrals, urgentShortage, notes
    };
    localStorage.setItem('field_visit_draft', JSON.stringify(draft));
    setDraftSaved(true);
    setTimeout(() => setDraftSaved(false), 2500);
  }

  async function handleSubmitVisit(e: React.FormEvent) {
    e.preventDefault();
    setSubmittingLog(true);
    setLogSuccess('');

    try {
      await createFieldVisitLog({
        district,
        upazila,
        location_name: locationName,
        households_visited: Number(households),
        suspected_cases_count: Number(casesCount),
        suspected_diseases: diseases,
        ors_packets_distributed: Number(orsDistributed),
        water_purification_tablets_distributed: Number(waterTabsDistributed),
        referrals_count: Number(referrals),
        urgent_shortage_reported: urgentShortage || undefined,
        notes: notes || undefined,
      });

      // Clear draft on successful sync
      localStorage.removeItem('field_visit_draft');
      setLogSuccess('Field visit log uploaded and synced with emergency registry!');
      setLocationName('');
      setNotes('');
      setUrgentShortage('');
      await loadData();
      setTimeout(() => setLogSuccess(''), 3000);
    } catch (err: any) {
      console.error('Error recording field visit:', err);
    } finally {
      setSubmittingLog(false);
    }
  }

  async function handleUpdateTask(taskId: string, newStatus: string) {
    try {
      await updateFieldTaskStatus(taskId, newStatus, 'Status updated via Health Worker Portal');
      await loadData();
    } catch (err) {
      console.error(err);
    }
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-6 rounded-2xl border border-white/10 bg-slate-900/60 backdrop-blur-xl">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-teal-500 to-emerald-500 flex items-center justify-center shadow-lg shadow-teal-500/20">
            <ClipboardList className="text-white" size={28} />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white tracking-tight">Health Worker Field Operations</h1>
            <p className="text-slate-400 text-sm">Community cluster investigation, door-to-door triage, and offline-safe field logging</p>
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

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-white/10 pb-2">
        <button
          onClick={() => setActiveTab('tasks')}
          className={`px-4 py-2 rounded-xl text-sm font-medium transition ${
            activeTab === 'tasks' ? 'bg-teal-600 text-white shadow-lg shadow-teal-500/20' : 'text-slate-400 hover:text-white'
          }`}
        >
          Assigned Tasks ({tasks.filter(t => t.status !== 'completed').length})
        </button>
        <button
          onClick={() => setActiveTab('log_visit')}
          className={`px-4 py-2 rounded-xl text-sm font-medium transition ${
            activeTab === 'log_visit' ? 'bg-teal-600 text-white shadow-lg shadow-teal-500/20' : 'text-slate-400 hover:text-white'
          }`}
        >
          Record Field Visit (Offline-Safe)
        </button>
        <button
          onClick={() => setActiveTab('history')}
          className={`px-4 py-2 rounded-xl text-sm font-medium transition ${
            activeTab === 'history' ? 'bg-teal-600 text-white shadow-lg shadow-teal-500/20' : 'text-slate-400 hover:text-white'
          }`}
        >
          My Field Log History
        </button>
      </div>

      {/* TAB 1: ASSIGNED TASKS */}
      {activeTab === 'tasks' && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {tasks.map((t) => (
              <div key={t.id} className="p-5 rounded-2xl border border-white/10 bg-slate-900/40 backdrop-blur space-y-3">
                <div className="flex justify-between items-start">
                  <div>
                    <h3 className="font-bold text-white text-base">{t.title}</h3>
                    <div className="text-xs text-slate-400 flex items-center gap-1.5 mt-0.5">
                      <MapPin size={12} /> {t.district} • {t.upazila || 'General Zone'}
                    </div>
                  </div>
                  <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold uppercase ${
                    t.priority === 'critical' ? 'bg-red-500/20 text-red-300 border border-red-500/40' :
                    t.priority === 'high' ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40' :
                    'bg-blue-500/20 text-blue-300 border border-blue-500/40'
                  }`}>
                    {t.priority}
                  </span>
                </div>

                {t.description && <p className="text-xs text-slate-300">{t.description}</p>}

                <div className="flex items-center justify-between text-xs text-slate-400 pt-2 border-t border-white/5">
                  <span className="capitalize">Status: <strong className="text-white">{t.status.replace('_', ' ')}</strong></span>
                  <div className="flex items-center gap-2">
                    {t.status === 'assigned' && (
                      <button
                        onClick={() => handleUpdateTask(t.id, 'accepted')}
                        className="px-2.5 py-1 rounded-lg bg-teal-600 hover:bg-teal-500 text-white text-xs font-medium"
                      >
                        Accept Task
                      </button>
                    )}
                    {t.status === 'accepted' && (
                      <button
                        onClick={() => handleUpdateTask(t.id, 'in_progress')}
                        className="px-2.5 py-1 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium"
                      >
                        Deploy to Field
                      </button>
                    )}
                    {t.status === 'in_progress' && (
                      <button
                        onClick={() => handleUpdateTask(t.id, 'completed')}
                        className="px-2.5 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium"
                      >
                        Mark Complete
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
            {tasks.length === 0 && (
              <div className="col-span-2 text-center py-12 text-slate-500 bg-slate-900/20 rounded-2xl border border-white/5">
                No active field tasks assigned to your account right now.
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 2: LOG VISIT */}
      {activeTab === 'log_visit' && (
        <form onSubmit={handleSubmitVisit} className="p-6 rounded-2xl border border-white/10 bg-slate-900/40 backdrop-blur space-y-6">
          <div className="flex justify-between items-center border-b border-white/10 pb-4">
            <div>
              <h2 className="text-lg font-bold text-white">Record Community Field Visit & Household Interventions</h2>
              <p className="text-xs text-slate-400">Captures suspected disease clusters and medical supply drops. Draft is locally saved.</p>
            </div>
            <button
              type="button"
              onClick={handleSaveDraft}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 text-slate-300 text-xs font-medium"
            >
              <Save size={14} /> {draftSaved ? 'Draft Saved!' : 'Save Draft'}
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div>
              <label className="block text-xs uppercase font-medium text-slate-400 mb-1.5">Specific Location / Shelter Name</label>
              <input
                type="text"
                required
                placeholder="e.g. Ward 4 High School Shelter"
                value={locationName}
                onChange={(e) => setLocationName(e.target.value)}
                className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2 text-white text-sm outline-none"
              />
            </div>

            <div>
              <label className="block text-xs uppercase font-medium text-slate-400 mb-1.5">District</label>
              <input
                type="text"
                required
                value={district}
                onChange={(e) => setDistrict(e.target.value)}
                className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2 text-white text-sm outline-none"
              />
            </div>

            <div>
              <label className="block text-xs uppercase font-medium text-slate-400 mb-1.5">Upazila / Union</label>
              <input
                type="text"
                required
                value={upazila}
                onChange={(e) => setUpazila(e.target.value)}
                className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2 text-white text-sm outline-none"
              />
            </div>

            <div>
              <label className="block text-xs uppercase font-medium text-slate-400 mb-1.5">Households Visited</label>
              <input
                type="number"
                min="1"
                value={households}
                onChange={(e) => setHouseholds(Number(e.target.value))}
                className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2 text-white text-sm outline-none"
              />
            </div>

            <div>
              <label className="block text-xs uppercase font-medium text-slate-400 mb-1.5">Suspected Case Clusters</label>
              <input
                type="number"
                min="0"
                value={casesCount}
                onChange={(e) => setCasesCount(Number(e.target.value))}
                className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2 text-white text-sm outline-none"
              />
            </div>

            <div>
              <label className="block text-xs uppercase font-medium text-slate-400 mb-1.5">Suspected Diseases</label>
              <input
                type="text"
                value={diseases}
                onChange={(e) => setDiseases(e.target.value)}
                className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2 text-white text-sm outline-none"
              />
            </div>

            <div>
              <label className="block text-xs uppercase font-medium text-slate-400 mb-1.5">ORS Packets Distributed</label>
              <input
                type="number"
                min="0"
                value={orsDistributed}
                onChange={(e) => setOrsDistributed(Number(e.target.value))}
                className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2 text-white text-sm outline-none"
              />
            </div>

            <div>
              <label className="block text-xs uppercase font-medium text-slate-400 mb-1.5">Water Purification Tablets Distributed</label>
              <input
                type="number"
                min="0"
                value={waterTabsDistributed}
                onChange={(e) => setWaterTabsDistributed(Number(e.target.value))}
                className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2 text-white text-sm outline-none"
              />
            </div>

            <div>
              <label className="block text-xs uppercase font-medium text-slate-400 mb-1.5">Hospital Referrals Issued</label>
              <input
                type="number"
                min="0"
                value={referrals}
                onChange={(e) => setReferrals(Number(e.target.value))}
                className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2 text-white text-sm outline-none"
              />
            </div>

            <div className="md:col-span-3">
              <label className="block text-xs uppercase font-medium text-slate-400 mb-1.5">Urgent Shortages or Bottlenecks</label>
              <input
                type="text"
                placeholder="e.g. Sub-center out of IV Saline bags; boat required to cross floodwater"
                value={urgentShortage}
                onChange={(e) => setUrgentShortage(e.target.value)}
                className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2 text-white text-sm outline-none"
              />
            </div>
          </div>

          {logSuccess && (
            <div className="p-3 rounded-xl bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 text-sm">
              {logSuccess}
            </div>
          )}

          <div className="flex justify-end gap-3">
            <button
              type="submit"
              disabled={submittingLog}
              className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-teal-600 hover:bg-teal-500 text-white font-semibold text-sm transition shadow-lg shadow-teal-500/20 disabled:opacity-50"
            >
              <Send size={16} /> {submittingLog ? 'Uploading...' : 'Submit Field Log'}
            </button>
          </div>
        </form>
      )}

      {/* TAB 3: HISTORY */}
      {activeTab === 'history' && (
        <div className="overflow-x-auto rounded-2xl border border-white/10 bg-slate-900/40 backdrop-blur">
          <table className="w-full text-left border-collapse text-sm">
            <thead>
              <tr className="border-b border-white/10 text-slate-400 uppercase text-xs font-semibold">
                <th className="py-4 px-5">Location</th>
                <th className="py-4 px-5">Households</th>
                <th className="py-4 px-5">Suspected Cases</th>
                <th className="py-4 px-5">Supplies Given</th>
                <th className="py-4 px-5">Urgent Shortage</th>
                <th className="py-4 px-5">Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 text-slate-200">
              {visitLogs.map((log) => (
                <tr key={log.id} className="hover:bg-white/5 transition">
                  <td className="py-4 px-5 font-medium text-white">{log.location_name} ({log.district})</td>
                  <td className="py-4 px-5">{log.households_visited}</td>
                  <td className="py-4 px-5 font-bold text-amber-400">{log.suspected_cases_count} ({log.suspected_diseases || 'General'})</td>
                  <td className="py-4 px-5 text-xs text-slate-300">{log.ors_packets_distributed} ORS • {log.water_purification_tablets_distributed} WASH Tabs</td>
                  <td className="py-4 px-5 text-xs text-red-300">{log.urgent_shortage_reported || 'None'}</td>
                  <td className="py-4 px-5 text-xs text-slate-400">{log.created_at?.split('T')[0] || 'Recent'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
