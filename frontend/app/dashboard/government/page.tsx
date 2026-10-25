'use client';

import { useState, useEffect } from 'react';
import {
  Landmark, Bell, FileSpreadsheet, CheckCircle2, XCircle, AlertCircle,
  Truck, ShieldAlert, Users, Building2, Send, Download, RefreshCw
} from 'lucide-react';
import { useAuth } from '@/lib/auth';
import {
  getGovernmentCommandOverview, listResourceRequests, reviewResourceRequest,
  createResourceAllocation, listOfficialAlerts, draftOfficialAlert,
  publishOfficialAlert, cancelOfficialAlert, getReportDownloadUrl,
  CommandOverviewData, ResourceRequestItem, OfficialAlertItem
} from '@/lib/api';

export default function GovernmentCommandPage() {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<'overview' | 'requests' | 'alerts' | 'exports'>('overview');

  const [overview, setOverview] = useState<CommandOverviewData | null>(null);
  const [requests, setRequests] = useState<ResourceRequestItem[]>([]);
  const [alerts, setAlerts] = useState<OfficialAlertItem[]>([]);
  const [loading, setLoading] = useState(true);

  // Review Modal State
  const [selectedReq, setSelectedReq] = useState<ResourceRequestItem | null>(null);
  const [reviewModalOpen, setReviewModalOpen] = useState(false);
  const [reviewStatus, setReviewStatus] = useState('approved');
  const [reviewNotes, setReviewNotes] = useState('');
  const [reviewing, setReviewing] = useState(false);

  // Dispatch Allocation Modal State
  const [allocModalOpen, setAllocModalOpen] = useState(false);
  const [allocSource, setAllocSource] = useState('Central Medical Depot - Chattogram');
  const [allocDest, setAllocDest] = useState('');
  const [allocTracking, setAllocTracking] = useState('TRK-FENI-001');
  const [allocating, setAllocating] = useState(false);

  // Draft Alert Form
  const [titleBn, setTitleBn] = useState('');
  const [titleEn, setTitleEn] = useState('');
  const [msgBn, setMsgBn] = useState('');
  const [msgEn, setMsgEn] = useState('');
  const [severity, setSeverity] = useState('warning');
  const [targetDistricts, setTargetDistricts] = useState('Feni, Sylhet');
  const [draftingAlert, setDraftingAlert] = useState(false);

  useEffect(() => {
    loadAll();
  }, []);

  async function loadAll() {
    setLoading(true);
    try {
      const ov = await getGovernmentCommandOverview();
      setOverview(ov);

      const reqs = await listResourceRequests();
      setRequests(reqs || []);

      const alts = await listOfficialAlerts();
      setAlerts(alts || []);
    } catch (err) {
      console.warn('Error loading command center:', err);
    } finally {
      setLoading(false);
    }
  }

  async function handleReviewSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedReq) return;
    setReviewing(true);
    try {
      await reviewResourceRequest(selectedReq.id, {
        status: reviewStatus,
        review_notes: reviewNotes,
        allocated_items: selectedReq.requested_items,
      });
      setReviewModalOpen(false);
      await loadAll();
    } catch (err) {
      console.error(err);
    } finally {
      setReviewing(false);
    }
  }

  async function handleDispatchAllocation(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedReq) return;
    setAllocating(true);
    try {
      await createResourceAllocation({
        request_id: selectedReq.id,
        source_depot_or_facility: allocSource,
        destination_facility: allocDest || `${selectedReq.organization_name} (${selectedReq.district})`,
        allocated_items: selectedReq.requested_items,
        tracking_number: allocTracking,
      });
      setAllocModalOpen(false);
      await loadAll();
    } catch (err) {
      console.error(err);
    } finally {
      setAllocating(false);
    }
  }

  async function handleDraftAlert(e: React.FormEvent) {
    e.preventDefault();
    setDraftingAlert(true);
    try {
      await draftOfficialAlert({
        title_bn: titleBn,
        title_en: titleEn,
        message_bn: msgBn,
        message_en: msgEn,
        severity,
        target_districts: targetDistricts,
        channel: 'in_app',
      });
      setTitleBn('');
      setTitleEn('');
      setMsgBn('');
      setMsgEn('');
      await loadAll();
    } catch (err) {
      console.error(err);
    } finally {
      setDraftingAlert(false);
    }
  }

  async function handlePublishAlert(id: string) {
    try {
      await publishOfficialAlert(id);
      await loadAll();
    } catch (err) {
      console.error(err);
    }
  }

  async function handleCancelAlert(id: string) {
    try {
      await cancelOfficialAlert(id);
      await loadAll();
    } catch (err) {
      console.error(err);
    }
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-6 rounded-2xl border border-white/10 bg-slate-900/60 backdrop-blur-xl">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-purple-600 to-indigo-500 flex items-center justify-center shadow-lg shadow-purple-500/20">
            <Landmark className="text-white" size={28} />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white tracking-tight">National Emergency Command Center</h1>
            <p className="text-slate-400 text-sm">Cross-agency resource allocation, bilingual emergency alerts, and national situational metrics</p>
          </div>
        </div>

        <button
          onClick={loadAll}
          className="p-2.5 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 text-slate-300 transition"
          title="Refresh Command Metrics"
        >
          <RefreshCw size={18} />
        </button>
      </div>

      {/* Overview Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-5 rounded-2xl border border-white/10 bg-slate-900/40 backdrop-blur">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs uppercase font-medium">National Bed Capacity</span>
            <Building2 size={16} className="text-blue-400" />
          </div>
          <div className="text-3xl font-extrabold text-white">
            {overview?.hospital_capacity.available_general_beds ?? 0}
            <span className="text-sm font-normal text-slate-400"> / {overview?.hospital_capacity.total_general_beds ?? 0} beds</span>
          </div>
          <div className="mt-2 text-xs text-slate-400">
            ICU Available: {overview?.hospital_capacity.available_icu_beds ?? 0}
          </div>
        </div>

        <div className="p-5 rounded-2xl border border-white/10 bg-slate-900/40 backdrop-blur">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs uppercase font-medium">NGO Campaigns & Teams</span>
            <Truck size={16} className="text-amber-400" />
          </div>
          <div className="text-3xl font-extrabold text-amber-400">
            {overview?.ngo_operations.active_campaigns ?? 0}
          </div>
          <div className="mt-2 text-xs text-slate-400">
            Active Dispatches: {overview?.ngo_operations.active_relief_tasks ?? 0}
          </div>
        </div>

        <div className="p-5 rounded-2xl border border-white/10 bg-slate-900/40 backdrop-blur">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs uppercase font-medium">Pending Requisitions</span>
            <AlertCircle size={16} className="text-purple-400" />
          </div>
          <div className="text-3xl font-extrabold text-purple-400">
            {overview?.coordination.pending_resource_requests ?? 0}
          </div>
          <div className="mt-2 text-xs text-slate-400">
            Awaiting authorized approval
          </div>
        </div>

        <div className="p-5 rounded-2xl border border-white/10 bg-slate-900/40 backdrop-blur">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs uppercase font-medium">Active Official Alerts</span>
            <Bell size={16} className="text-red-400" />
          </div>
          <div className="text-3xl font-extrabold text-red-400">
            {overview?.coordination.active_official_alerts ?? 0}
          </div>
          <div className="mt-2 text-xs text-slate-400">
            Unverified Reports: {overview?.coordination.unverified_citizen_reports ?? 0}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-white/10 pb-2">
        <button
          onClick={() => setActiveTab('overview')}
          className={`px-4 py-2 rounded-xl text-sm font-medium transition ${
            activeTab === 'overview' ? 'bg-purple-600 text-white shadow-lg shadow-purple-500/20' : 'text-slate-400 hover:text-white'
          }`}
        >
          National Overview
        </button>
        <button
          onClick={() => setActiveTab('requests')}
          className={`px-4 py-2 rounded-xl text-sm font-medium transition ${
            activeTab === 'requests' ? 'bg-purple-600 text-white shadow-lg shadow-purple-500/20' : 'text-slate-400 hover:text-white'
          }`}
        >
          Resource Requests ({requests.filter(r => r.status === 'pending').length})
        </button>
        <button
          onClick={() => setActiveTab('alerts')}
          className={`px-4 py-2 rounded-xl text-sm font-medium transition ${
            activeTab === 'alerts' ? 'bg-purple-600 text-white shadow-lg shadow-purple-500/20' : 'text-slate-400 hover:text-white'
          }`}
        >
          Bilingual Emergency Alerts
        </button>
        <button
          onClick={() => setActiveTab('exports')}
          className={`px-4 py-2 rounded-xl text-sm font-medium transition ${
            activeTab === 'exports' ? 'bg-purple-600 text-white shadow-lg shadow-purple-500/20' : 'text-slate-400 hover:text-white'
          }`}
        >
          Automated Reports & CSV Exports
        </button>
      </div>

      {/* TAB 1: OVERVIEW */}
      {activeTab === 'overview' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="p-6 rounded-2xl border border-white/10 bg-slate-900/40 backdrop-blur space-y-4">
            <h2 className="text-lg font-bold text-white">Emergency Response Capacity</h2>
            <div className="space-y-3">
              <div className="flex justify-between items-center text-sm py-2 border-b border-white/5">
                <span className="text-slate-400">Total Registered Health Facilities</span>
                <span className="font-bold text-white">{overview?.hospital_capacity.total_facilities ?? 0}</span>
              </div>
              <div className="flex justify-between items-center text-sm py-2 border-b border-white/5">
                <span className="text-slate-400">Facilities Facing Stock Shortages</span>
                <span className="font-bold text-red-400">{overview?.hospital_capacity.critical_stock_shortages ?? 0}</span>
              </div>
              <div className="flex justify-between items-center text-sm py-2 border-b border-white/5">
                <span className="text-slate-400">Field Investigations Completed</span>
                <span className="font-bold text-teal-400">{overview?.coordination.field_investigations_logged ?? 0}</span>
              </div>
              <div className="flex justify-between items-center text-sm py-2">
                <span className="text-slate-400">Last Telemetry Timestamp</span>
                <span className="font-mono text-xs text-slate-300">{overview?.timestamp ?? 'Live'}</span>
              </div>
            </div>
          </div>

          <div className="p-6 rounded-2xl border border-white/10 bg-slate-900/40 backdrop-blur space-y-4">
            <h2 className="text-lg font-bold text-white">Urgent Action Items</h2>
            <div className="space-y-3">
              <div className="p-4 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-between">
                <div>
                  <div className="font-bold text-white text-sm">Review Pending Resource Requisitions</div>
                  <div className="text-xs text-slate-400">{overview?.coordination.pending_resource_requests ?? 0} hospital and NGO requests awaiting decision</div>
                </div>
                <button
                  onClick={() => setActiveTab('requests')}
                  className="px-3 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-white text-xs font-medium"
                >
                  Review
                </button>
              </div>

              <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 flex items-center justify-between">
                <div>
                  <div className="font-bold text-white text-sm">Broadcast Emergency Public Alert</div>
                  <div className="text-xs text-slate-400">Publish high-priority bilingual advisories to impacted districts</div>
                </div>
                <button
                  onClick={() => setActiveTab('alerts')}
                  className="px-3 py-1.5 rounded-lg bg-red-600 hover:bg-red-500 text-white text-xs font-medium"
                >
                  Compose
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: REQUESTS */}
      {activeTab === 'requests' && (
        <div className="overflow-x-auto rounded-2xl border border-white/10 bg-slate-900/40 backdrop-blur">
          <table className="w-full text-left border-collapse text-sm">
            <thead>
              <tr className="border-b border-white/10 text-slate-400 uppercase text-xs font-semibold">
                <th className="py-4 px-5">Organization & District</th>
                <th className="py-4 px-5">Type</th>
                <th className="py-4 px-5">Urgency</th>
                <th className="py-4 px-5">Justification</th>
                <th className="py-4 px-5">Status</th>
                <th className="py-4 px-5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 text-slate-200">
              {requests.map((r) => (
                <tr key={r.id} className="hover:bg-white/5 transition">
                  <td className="py-4 px-5 font-medium text-white">
                    <div>{r.organization_name}</div>
                    <div className="text-xs text-slate-400">{r.district} • {r.requester_role}</div>
                  </td>
                  <td className="py-4 px-5 capitalize text-slate-300">{r.request_type.replace('_', ' ')}</td>
                  <td className="py-4 px-5">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium uppercase ${
                      r.urgency === 'critical_emergency' ? 'bg-red-500/20 text-red-300 border border-red-500/40' :
                      'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                    }`}>
                      {r.urgency.replace('_', ' ')}
                    </span>
                  </td>
                  <td className="py-4 px-5 text-xs text-slate-300 max-w-xs truncate">{r.justification}</td>
                  <td className="py-4 px-5 capitalize text-xs">
                    <span className={`px-2 py-0.5 rounded-full ${
                      r.status === 'approved' ? 'bg-emerald-500/20 text-emerald-300' :
                      r.status === 'rejected' ? 'bg-red-500/20 text-red-300' : 'bg-purple-500/20 text-purple-300'
                    }`}>
                      {r.status}
                    </span>
                  </td>
                  <td className="py-4 px-5 text-right space-x-2">
                    {r.status === 'pending' && (
                      <button
                        onClick={() => {
                          setSelectedReq(r);
                          setReviewModalOpen(true);
                        }}
                        className="px-3 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-white text-xs font-medium"
                      >
                        Review
                      </button>
                    )}
                    {r.status === 'approved' && (
                      <button
                        onClick={() => {
                          setSelectedReq(r);
                          setAllocDest(`${r.organization_name} (${r.district})`);
                          setAllocModalOpen(true);
                        }}
                        className="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium"
                      >
                        Dispatch Allocation
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {requests.length === 0 && (
                <tr>
                  <td colSpan={6} className="text-center py-8 text-slate-500">
                    No resource requisitions currently pending.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* TAB 3: BILINGUAL ALERTS */}
      {activeTab === 'alerts' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-4">
            <h2 className="text-lg font-bold text-white">Published & Draft Advisories</h2>
            <div className="space-y-4">
              {alerts.map((a) => (
                <div key={a.id} className="p-5 rounded-2xl border border-white/10 bg-slate-900/40 backdrop-blur space-y-3">
                  <div className="flex justify-between items-start">
                    <div>
                      <h3 className="font-bold text-white text-base">{a.title_en}</h3>
                      <h4 className="text-sm text-teal-300 font-medium font-bengali">{a.title_bn}</h4>
                    </div>
                    <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold uppercase ${
                      a.status === 'published' ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40' :
                      'bg-slate-500/20 text-slate-300 border border-slate-500/40'
                    }`}>
                      {a.status}
                    </span>
                  </div>

                  <p className="text-xs text-slate-300">{a.message_en}</p>
                  <p className="text-xs text-slate-400 font-bengali">{a.message_bn}</p>

                  <div className="flex items-center justify-between text-xs text-slate-400 pt-2 border-t border-white/5">
                    <span>Target: <strong className="text-white">{a.target_districts}</strong></span>
                    <div className="flex items-center gap-2">
                      {a.status === 'draft' && (
                        <button
                          onClick={() => handlePublishAlert(a.id)}
                          className="px-3 py-1 rounded-lg bg-red-600 hover:bg-red-500 text-white text-xs font-medium"
                        >
                          Publish Alert
                        </button>
                      )}
                      {a.status === 'published' && (
                        <button
                          onClick={() => handleCancelAlert(a.id)}
                          className="px-3 py-1 rounded-lg border border-white/10 hover:bg-white/5 text-slate-300 text-xs font-medium"
                        >
                          Withdraw
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <form onSubmit={handleDraftAlert} className="p-5 rounded-2xl border border-white/10 bg-slate-900/50 backdrop-blur space-y-4 h-fit">
            <h3 className="text-base font-bold text-white">Draft Bilingual Emergency Alert</h3>
            <div>
              <label className="block text-xs uppercase font-medium text-slate-400 mb-1">Title (English)</label>
              <input
                type="text"
                required
                placeholder="e.g. Flash Flood Alert: Muhuri Embankment"
                value={titleEn}
                onChange={(e) => setTitleEn(e.target.value)}
                className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2 text-white text-sm outline-none"
              />
            </div>
            <div>
              <label className="block text-xs uppercase font-medium text-slate-400 mb-1">Title (Bengali - বাংলা)</label>
              <input
                type="text"
                required
                placeholder="যেমন: জরুরি বন্যা সতর্কতা: মুহুরী বাঁধ"
                value={titleBn}
                onChange={(e) => setTitleBn(e.target.value)}
                className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2 text-white text-sm outline-none"
              />
            </div>
            <div>
              <label className="block text-xs uppercase font-medium text-slate-400 mb-1">Message (English)</label>
              <textarea
                required
                rows={2}
                placeholder="Residents in low-lying unions are advised to relocate to designated shelters."
                value={msgEn}
                onChange={(e) => setMsgEn(e.target.value)}
                className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2 text-white text-sm outline-none resize-none"
              />
            </div>
            <div>
              <label className="block text-xs uppercase font-medium text-slate-400 mb-1">Message (Bengali - বাংলা)</label>
              <textarea
                required
                rows={2}
                placeholder="নিম্নাঞ্চলের বাসিন্দাদের নিকটস্থ আশ্রয়কেন্দ্রে সরে যেতে অনুরোধ করা হচ্ছে।"
                value={msgBn}
                onChange={(e) => setMsgBn(e.target.value)}
                className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2 text-white text-sm outline-none resize-none"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs uppercase font-medium text-slate-400 mb-1">Severity</label>
                <select
                  value={severity}
                  onChange={(e) => setSeverity(e.target.value)}
                  className="w-full bg-slate-950 border border-white/10 rounded-xl px-2 py-2 text-white text-xs outline-none"
                >
                  <option value="advisory">Advisory</option>
                  <option value="warning">Warning</option>
                  <option value="critical">Critical</option>
                  <option value="evacuation">Evacuation</option>
                </select>
              </div>
              <div>
                <label className="block text-xs uppercase font-medium text-slate-400 mb-1">Target</label>
                <input
                  type="text"
                  value={targetDistricts}
                  onChange={(e) => setTargetDistricts(e.target.value)}
                  className="w-full bg-slate-950 border border-white/10 rounded-xl px-2 py-2 text-white text-xs outline-none"
                />
              </div>
            </div>
            <button
              type="submit"
              disabled={draftingAlert}
              className="w-full py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-semibold text-sm transition shadow-lg shadow-purple-500/20 disabled:opacity-50"
            >
              {draftingAlert ? 'Drafting...' : 'Save Draft Alert'}
            </button>
          </form>
        </div>
      )}

      {/* TAB 4: EXPORTS */}
      {activeTab === 'exports' && (
        <div className="p-6 rounded-2xl border border-white/10 bg-slate-900/40 backdrop-blur space-y-6">
          <div className="border-b border-white/10 pb-4">
            <h2 className="text-lg font-bold text-white">Automated Operational Reports & CSV Data Exports</h2>
            <p className="text-xs text-slate-400">Export verified backend operational datasets for disaster audits and external reporting.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-5 rounded-2xl border border-white/10 bg-slate-950/40 flex items-center justify-between">
              <div>
                <div className="font-bold text-white text-sm">Environmental & Climate Risk Log</div>
                <div className="text-xs text-slate-400">Daily rainfall, water quality, and river level observations</div>
              </div>
              <a
                href={getReportDownloadUrl('daily-risk')}
                download
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold"
              >
                <Download size={14} /> Export CSV
              </a>
            </div>

            <div className="p-5 rounded-2xl border border-white/10 bg-slate-950/40 flex items-center justify-between">
              <div>
                <div className="font-bold text-white text-sm">Hospital Inventory Shortage Audit</div>
                <div className="text-xs text-slate-400">Dynamic facility inventory below minimum reserve thresholds</div>
              </div>
              <a
                href={getReportDownloadUrl('hospital-shortages')}
                download
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-teal-600 hover:bg-teal-500 text-white text-xs font-semibold"
              >
                <Download size={14} /> Export CSV
              </a>
            </div>

            <div className="p-5 rounded-2xl border border-white/10 bg-slate-950/40 flex items-center justify-between">
              <div>
                <div className="font-bold text-white text-sm">NGO Field Relief Distribution Log</div>
                <div className="text-xs text-slate-400">Campaign drops, beneficiary household counts, and reach metrics</div>
              </div>
              <a
                href={getReportDownloadUrl('ngo-distribution')}
                download
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-500 text-white text-xs font-semibold"
              >
                <Download size={14} /> Export CSV
              </a>
            </div>

            <div className="p-5 rounded-2xl border border-white/10 bg-slate-950/40 flex items-center justify-between">
              <div>
                <div className="font-bold text-white text-sm">Government Requisition Summary</div>
                <div className="text-xs text-slate-400">Inter-agency support requests, review decisions, and allocations</div>
              </div>
              <a
                href={getReportDownloadUrl('resource-requests')}
                download
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold"
              >
                <Download size={14} /> Export CSV
              </a>
            </div>
          </div>
        </div>
      )}

      {/* REVIEW MODAL */}
      {reviewModalOpen && selectedReq && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="w-full max-w-md p-6 rounded-2xl border border-white/10 bg-slate-900 shadow-2xl space-y-5">
            <div>
              <h3 className="text-lg font-bold text-white">Review Resource Request</h3>
              <p className="text-xs text-slate-400">{selectedReq.organization_name} • {selectedReq.district}</p>
            </div>

            <form onSubmit={handleReviewSubmit} className="space-y-4">
              <div>
                <label className="block text-xs uppercase font-medium text-slate-400 mb-1">Decision</label>
                <select
                  value={reviewStatus}
                  onChange={(e) => setReviewStatus(e.target.value)}
                  className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2 text-white text-sm outline-none"
                >
                  <option value="approved">Approve Requisition</option>
                  <option value="partially_fulfilled">Partially Fulfill</option>
                  <option value="rejected">Reject Request</option>
                </select>
              </div>

              <div>
                <label className="block text-xs uppercase font-medium text-slate-400 mb-1">Official Review Notes</label>
                <textarea
                  rows={2}
                  value={reviewNotes}
                  onChange={(e) => setReviewNotes(e.target.value)}
                  placeholder="e.g. Approved for immediate dispatch from Chittagong Central Medical Depot."
                  className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2 text-white text-sm outline-none resize-none"
                />
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setReviewModalOpen(false)}
                  className="px-4 py-2 rounded-xl border border-white/10 text-slate-300 text-xs hover:bg-white/5"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={reviewing}
                  className="px-5 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold shadow-lg shadow-purple-500/20 disabled:opacity-50"
                >
                  {reviewing ? 'Saving...' : 'Confirm Decision'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* DISPATCH ALLOCATION MODAL */}
      {allocModalOpen && selectedReq && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="w-full max-w-md p-6 rounded-2xl border border-white/10 bg-slate-900 shadow-2xl space-y-5">
            <div>
              <h3 className="text-lg font-bold text-white">Dispatch Resource Allocation</h3>
              <p className="text-xs text-slate-400">Requisition ID: {selectedReq.id}</p>
            </div>

            <form onSubmit={handleDispatchAllocation} className="space-y-4">
              <div>
                <label className="block text-xs uppercase font-medium text-slate-400 mb-1">Source Depot / Warehouse</label>
                <input
                  type="text"
                  required
                  value={allocSource}
                  onChange={(e) => setAllocSource(e.target.value)}
                  className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2 text-white text-sm outline-none"
                />
              </div>

              <div>
                <label className="block text-xs uppercase font-medium text-slate-400 mb-1">Destination Facility</label>
                <input
                  type="text"
                  required
                  value={allocDest}
                  onChange={(e) => setAllocDest(e.target.value)}
                  className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2 text-white text-sm outline-none"
                />
              </div>

              <div>
                <label className="block text-xs uppercase font-medium text-slate-400 mb-1">Tracking Number</label>
                <input
                  type="text"
                  value={allocTracking}
                  onChange={(e) => setAllocTracking(e.target.value)}
                  className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2 text-white text-sm outline-none"
                />
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setAllocModalOpen(false)}
                  className="px-4 py-2 rounded-xl border border-white/10 text-slate-300 text-xs hover:bg-white/5"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={allocating}
                  className="px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-lg shadow-blue-500/20 disabled:opacity-50"
                >
                  {allocating ? 'Dispatching...' : 'Confirm Dispatch'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
