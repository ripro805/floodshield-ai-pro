'use client';

import { useState, useEffect } from 'react';
import {
  Cpu, Play, CheckCircle2, AlertCircle, Clock, Shield,
  RefreshCw, History, Activity, Database, Server, Workflow,
  AlertTriangle, Check, Layers
} from 'lucide-react';
import { useAuth } from '@/lib/auth';
import {
  listAdminJobs, triggerAdminJobRun, listAdminAuditLogs,
  AutomationJobItem, AuditEventItem, getAutomationStatus, AutomationStatus
} from '@/lib/api';

export default function AutomationAdminPage() {
  const { user } = useAuth();
  const [jobs, setJobs] = useState<AutomationJobItem[]>([]);
  const [logs, setLogs] = useState<AuditEventItem[]>([]);
  const [statusData, setStatusData] = useState<AutomationStatus | null>(null);
  const [activeTab, setActiveTab] = useState<'jobs' | 'audit'>('jobs');
  const [runningJob, setRunningJob] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    setLoading(true);
    try {
      const [jobsRes, logsRes, statusRes] = await Promise.all([
        listAdminJobs().catch(() => []),
        listAdminAuditLogs().catch(() => []),
        getAutomationStatus().catch(() => null),
      ]);
      setJobs(jobsRes || []);
      setLogs(logsRes || []);
      setStatusData(statusRes);
    } catch (err) {
      console.warn('Error loading automation data:', err);
    } finally {
      setLoading(false);
    }
  }

  async function handleRunNow(jobName: string) {
    setRunningJob(jobName);
    setFeedback(null);
    try {
      const res = await triggerAdminJobRun(jobName);
      const duration = typeof res.details?.duration_seconds === 'number'
        ? res.details.duration_seconds.toFixed(3)
        : '0.200';
      const engine = (res.details?.engine as string) || (res.details?.accepted ? 'n8n' : 'native');
      const jobStatus = (res.details?.status as string) || 'completed';
      setFeedback(`Job '${jobName}' dispatched via ${engine.toUpperCase()} (${jobStatus}) in ${duration}s!`);
      await loadData();
      setTimeout(() => setFeedback(null), 5000);
    } catch (err: any) {
      setFeedback(err.response?.data?.detail || 'Job execution failed.');
    } finally {
      setRunningJob(null);
    }
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-6 rounded-2xl border border-white/10 bg-slate-900/60 backdrop-blur-xl">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-cyan-600 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/20">
            <Cpu className="text-white" size={28} />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white tracking-tight">Hybrid Automation & System Telemetry</h1>
            <p className="text-slate-400 text-sm">
              Fault-tolerant dual-engine automation: n8n workflow execution with automatic native backend fallback
            </p>
          </div>
        </div>

        <button
          onClick={loadData}
          disabled={loading}
          className="p-2.5 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 text-slate-300 transition flex items-center gap-2 text-xs font-semibold"
          title="Refresh Registry and Health"
        >
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          <span>Refresh</span>
        </button>
      </div>

      {feedback && (
        <div className="p-4 rounded-xl bg-cyan-500/20 border border-cyan-500/40 text-cyan-200 text-sm flex items-center gap-2">
          <CheckCircle2 size={18} className="text-cyan-400 shrink-0" />
          <span>{feedback}</span>
        </div>
      )}

      {/* ── SECTION 8: AUTOMATION MONITORING DASHBOARD ───────────────────────── */}
      {statusData && (
        <div className="space-y-4">
          {/* Top Status Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* 1. Active Engine */}
            <div className="p-5 rounded-2xl border border-white/10 bg-slate-900/40 backdrop-blur space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs uppercase font-mono text-slate-400">Active Engine</span>
                <Workflow size={16} className="text-cyan-400" />
              </div>
              <div className="flex items-center gap-2">
                <span className={`px-2.5 py-1 rounded-lg text-xs font-bold uppercase tracking-wider ${
                  statusData.active_engine === 'n8n'
                    ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40'
                    : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                }`}>
                  {statusData.active_engine === 'n8n' ? 'n8n Cloud Engine' : 'Native Backend Engine'}
                </span>
              </div>
              <p className="text-[11px] text-slate-400">
                {statusData.active_engine === 'n8n'
                  ? 'Eligible tasks routed to n8n webhook workflow'
                  : 'Native Python scheduler actively executing all tasks'}
              </p>
            </div>

            {/* 2. Docker Status */}
            <div className="p-5 rounded-2xl border border-white/10 bg-slate-900/40 backdrop-blur space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs uppercase font-mono text-slate-400">Docker Daemon</span>
                <Server size={16} className="text-blue-400" />
              </div>
              <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full ${statusData.docker.running ? 'bg-emerald-400' : 'bg-amber-400'}`} />
                <span className="text-sm font-semibold text-white">
                  {statusData.docker.running ? 'Active & Responsive' : 'Stopped / Standalone Host'}
                </span>
              </div>
              <p className="text-[11px] text-slate-400 truncate" title={statusData.docker.status}>
                {statusData.docker.status}
              </p>
            </div>

            {/* 3. n8n Connectivity */}
            <div className="p-5 rounded-2xl border border-white/10 bg-slate-900/40 backdrop-blur space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs uppercase font-mono text-slate-400">n8n Workflow Webhook</span>
                <Activity size={16} className="text-teal-400" />
              </div>
              <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full ${statusData.n8n.healthy ? 'bg-emerald-400' : 'bg-amber-400'}`} />
                <span className="text-sm font-semibold text-white">
                  {statusData.n8n.healthy ? 'Healthy (Connected)' : 'Fallback Active'}
                </span>
              </div>
              <p className="text-[11px] text-slate-400 truncate" title={statusData.n8n.reason}>
                {statusData.n8n.reason}
              </p>
            </div>

            {/* 4. Native Automation */}
            <div className="p-5 rounded-2xl border border-white/10 bg-slate-900/40 backdrop-blur space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs uppercase font-mono text-slate-400">Native Automation</span>
                <Shield size={16} className="text-emerald-400" />
              </div>
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-400" />
                <span className="text-sm font-semibold text-emerald-300 uppercase">
                  {statusData.native_status}
                </span>
              </div>
              <p className="text-[11px] text-slate-400">
                Independent native handlers ready 24/7 without external dependencies
              </p>
            </div>
          </div>

          {/* Metrics Strip */}
          <div className="p-5 rounded-2xl border border-white/10 bg-slate-900/40 backdrop-blur grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
            <div>
              <p className="text-[11px] text-slate-500 uppercase font-mono">Total Tasks</p>
              <p className="text-lg font-bold text-white mt-0.5">{statusData.counts.total}</p>
            </div>
            <div>
              <p className="text-[11px] text-slate-500 uppercase font-mono">n8n Executions</p>
              <p className="text-lg font-bold text-cyan-300 mt-0.5">{statusData.counts.n8n}</p>
            </div>
            <div>
              <p className="text-[11px] text-slate-500 uppercase font-mono">Native Executions</p>
              <p className="text-lg font-bold text-emerald-300 mt-0.5">{statusData.counts.native}</p>
            </div>
            <div>
              <p className="text-[11px] text-slate-500 uppercase font-mono">Success / Failed</p>
              <p className="text-lg font-bold text-white mt-0.5">
                <span className="text-emerald-400">{statusData.counts.success}</span>
                <span className="text-slate-500"> / </span>
                <span className="text-red-400">{statusData.counts.failed}</span>
              </p>
            </div>
            <div>
              <p className="text-[11px] text-slate-500 uppercase font-mono">Unknown / Pending</p>
              <p className="text-lg font-bold text-amber-300 mt-0.5">
                {statusData.counts.unknown + statusData.counts.pending}
              </p>
            </div>
            <div>
              <p className="text-[11px] text-slate-500 uppercase font-mono">Last Health Check</p>
              <p className="text-xs font-mono text-slate-300 mt-1">
                {statusData.n8n.last_health_check
                  ? new Date(statusData.n8n.last_health_check).toLocaleTimeString()
                  : 'N/A'}
              </p>
            </div>
          </div>

          {/* Recent Errors Banner if any */}
          {statusData.recent_errors && statusData.recent_errors.length > 0 && (
            <div className="p-4 rounded-xl border border-amber-500/30 bg-amber-500/10 text-amber-200 space-y-1.5 text-xs">
              <div className="flex items-center gap-2 font-semibold">
                <AlertTriangle size={15} className="text-amber-400 shrink-0" />
                <span>Recent Failover / Execution Alerts ({statusData.recent_errors.length})</span>
              </div>
              <ul className="list-disc list-inside space-y-1 text-amber-300/80 pl-2">
                {statusData.recent_errors.map((err, idx) => (
                  <li key={idx} className="truncate">
                    <span className="font-mono text-white/90">[{err.job_name}]</span> {err.error}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-white/10 pb-2">
        <button
          onClick={() => setActiveTab('jobs')}
          className={`px-4 py-2 rounded-xl text-sm font-medium transition ${
            activeTab === 'jobs' ? 'bg-cyan-600 text-white shadow-lg shadow-cyan-500/20' : 'text-slate-400 hover:text-white'
          }`}
        >
          Registered Background Jobs ({jobs.length})
        </button>
        <button
          onClick={() => setActiveTab('audit')}
          className={`px-4 py-2 rounded-xl text-sm font-medium transition ${
            activeTab === 'audit' ? 'bg-cyan-600 text-white shadow-lg shadow-cyan-500/20' : 'text-slate-400 hover:text-white'
          }`}
        >
          System Audit Trail ({logs.length})
        </button>
      </div>

      {/* TAB 1: JOBS */}
      {activeTab === 'jobs' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {jobs.map((job) => {
            const isRunning = runningJob === job.job_name;
            return (
              <div key={job.id} className="p-5 rounded-2xl border border-white/10 bg-slate-900/40 backdrop-blur space-y-4 flex flex-col justify-between">
                <div>
                  <div className="flex justify-between items-start mb-2">
                    <span className="font-mono text-sm font-bold text-white">{job.job_name}</span>
                    <span className={`px-2 py-0.5 rounded-full text-[11px] font-semibold uppercase ${
                      job.status === 'success' ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40' :
                      job.status === 'failed' ? 'bg-red-500/20 text-red-300 border border-red-500/40' :
                      'bg-slate-500/20 text-slate-300 border border-slate-500/40'
                    }`}>
                      {job.status}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400">{job.description || 'Native automation worker'}</p>
                </div>

                <div className="space-y-1.5 text-xs text-slate-300 border-t border-white/5 pt-3">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Interval:</span>
                    <span>{job.interval_seconds}s ({(job.interval_seconds / 60).toFixed(0)} min)</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Last Execution:</span>
                    <span className="font-mono">{job.last_run_at ? new Date(job.last_run_at).toLocaleTimeString() : 'Never'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Duration:</span>
                    <span>{job.last_duration_seconds ? `${job.last_duration_seconds}s` : 'N/A'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Runs / Failures:</span>
                    <span>{job.total_runs} / {job.failure_runs}</span>
                  </div>
                </div>

                {job.last_error && (
                  <div className="p-2 rounded-lg bg-red-500/10 border border-red-500/20 text-red-300 text-[11px]">
                    Error: {job.last_error}
                  </div>
                )}

                <button
                  onClick={() => handleRunNow(job.job_name)}
                  disabled={isRunning}
                  className="w-full flex items-center justify-center gap-2 py-2 rounded-xl bg-cyan-600/30 hover:bg-cyan-600/50 border border-cyan-500/40 text-cyan-200 text-xs font-semibold transition disabled:opacity-50"
                >
                  <Play size={14} /> {isRunning ? 'Dispatching Job...' : 'Run Manually Now'}
                </button>
              </div>
            );
          })}
        </div>
      )}

      {/* TAB 2: AUDIT LOGS */}
      {activeTab === 'audit' && (
        <div className="overflow-x-auto rounded-2xl border border-white/10 bg-slate-900/40 backdrop-blur">
          <table className="w-full text-left border-collapse text-sm">
            <thead>
              <tr className="border-b border-white/10 text-slate-400 uppercase text-xs font-semibold">
                <th className="py-4 px-5">Timestamp</th>
                <th className="py-4 px-5">Actor / Email</th>
                <th className="py-4 px-5">Role</th>
                <th className="py-4 px-5">Action</th>
                <th className="py-4 px-5">Resource</th>
                <th className="py-4 px-5">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 text-slate-200">
              {logs.map((log) => (
                <tr key={log.id} className="hover:bg-white/5 transition">
                  <td className="py-4 px-5 font-mono text-xs text-slate-400">
                    {log.created_at ? new Date(log.created_at).toLocaleString() : '—'}
                  </td>
                  <td className="py-4 px-5 font-medium text-white">{log.user_email}</td>
                  <td className="py-4 px-5 capitalize text-xs">
                    <span className="px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-white/10">
                      {log.user_role}
                    </span>
                  </td>
                  <td className="py-4 px-5 font-mono text-xs text-cyan-400">{log.action}</td>
                  <td className="py-4 px-5 capitalize text-xs text-slate-400">{log.resource_type.replace('_', ' ')}</td>
                  <td className="py-4 px-5 text-xs text-slate-300 max-w-sm truncate">{log.details || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
