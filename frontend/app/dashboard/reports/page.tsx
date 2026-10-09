'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import GlassCard from '@/components/cards/GlassCard';
import ForecastChart from '@/components/charts/ForecastChart';
import { useForecast, usePredictionHistory, useWeeklyHistory } from '@/hooks';
import { BANGLADESH_DISTRICTS, type WeeklyObservation } from '@/lib/types';
import { BarChart2, Download, Loader2, AlertCircle, Filter } from 'lucide-react';
import { getApiErrorMessage } from '@/lib/api';

export default function ReportsPage() {
  const [selectedDistrict, setSelectedDistrict] = useState('Feni');
  const [reportDistrict, setReportDistrict] = useState('');
  const [reportModel, setReportModel] = useState('');
  const [reportRisk, setReportRisk] = useState('');
  const [reportFromDate, setReportFromDate] = useState('');
  const historyQuery = useWeeklyHistory(selectedDistrict);
  const weeks = historyQuery.data?.weeks ?? [];
  const historyReady = historyQuery.data?.source === 'database' && weeks.length === 8;
  const forecastMutation = useForecast();
  const predictionHistoryQuery = usePredictionHistory({
    district: reportDistrict || undefined,
    model_name: reportModel || undefined,
    risk_level: reportRisk || undefined,
  });
  const visibleHistory = (predictionHistoryQuery.data ?? []).filter((item) =>
    !reportFromDate || item.created_at.slice(0, 10) >= reportFromDate
  );

  const handleRunForecast = () => {
    if (!historyReady) return;
    forecastMutation.mutate({ district: selectedDistrict, recent_weeks: weeks });
  };

  const exportCSV = () => {
    const rows: string[] = [
      'Report Type,District,7-Day Forecast (cases),14-Day Forecast (cases),Generated',
    ];

    if (forecastMutation.data) {
      const { district, forecast_next_7_days_cases, forecast_next_14_days_cases } = forecastMutation.data;
      rows.push(`District Forecast,${district},${forecast_next_7_days_cases.toFixed(0)},${forecast_next_14_days_cases.toFixed(0)},${new Date().toISOString()}`);
    }

    const csv = rows.join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `floodshield-report-${selectedDistrict}-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const exportPDF = () => {
    // Build a printable HTML page using window.print()
    const fd = forecastMutation.data;
    const html = `
      <!DOCTYPE html>
      <html>
      <head>
        <title>FloodShield AI — Forecast Report</title>
        <style>
          body { font-family: Arial, sans-serif; color: #1a1a1a; padding: 32px; }
          h1 { color: #1d4ed8; }
          h2 { color: #334155; margin-top: 24px; }
          table { border-collapse: collapse; width: 100%; margin-top: 12px; }
          th, td { border: 1px solid #cbd5e1; padding: 8px 12px; text-align: left; font-size: 13px; }
          th { background: #f1f5f9; font-weight: 700; }
          .stat-row { display: flex; gap: 48px; margin: 16px 0; }
          .stat-box { text-align: center; }
          .stat-val { font-size: 36px; font-weight: 900; font-family: monospace; }
          .stat-label { font-size: 12px; color: #64748b; margin-top: 4px; }
          .footer { margin-top: 40px; font-size: 11px; color: #94a3b8; border-top: 1px solid #e2e8f0; padding-top: 12px; }
        </style>
      </head>
      <body>
        <h1>🌊 FloodShield AI — Disease Forecast Report</h1>
        <p>Generated: ${new Date().toLocaleString('en-GB')}</p>
        ${
          fd
            ? `
          <h2>District Forecast: ${fd.district}</h2>
          <div class="stat-row">
            <div class="stat-box">
              <div class="stat-val" style="color:#0d9488">+${Math.round(fd.forecast_next_7_days_cases)}</div>
              <div class="stat-label">Expected cases — next 7 days</div>
            </div>
            <div class="stat-box">
              <div class="stat-val" style="color:#d97706">+${Math.round(fd.forecast_next_14_days_cases)}</div>
              <div class="stat-label">Expected cases — next 14 days</div>
            </div>
          </div>
          `
            : ''
        }
        <div class="footer">FloodShield AI — Confidential Report. Do not distribute without authorization.</div>
      </body>
      </html>
    `;

    const win = window.open('', '_blank', 'width=900,height=700');
    if (!win) { alert('Please allow popups to export PDF'); return; }
    win.document.write(html);
    win.document.close();
    win.focus();
    setTimeout(() => { win.print(); }, 500);
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-3xl font-black text-white" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
          Reports
        </h1>
        <p className="text-white/50 mt-1">7 and 14-day disease case forecasts by district</p>
      </motion.div>

      {/* District forecast selector */}
      <GlassCard className="p-6">
        <h2 className="text-sm font-semibold uppercase tracking-widest text-white/60 mb-4">District Forecast</h2>
        <div className="flex flex-wrap gap-4 items-end mb-4">
          <div>
            <label className="block text-xs text-white/50 mb-1.5" htmlFor="report-district">District</label>
            <select
              id="report-district"
              value={selectedDistrict}
              onChange={(e) => setSelectedDistrict(e.target.value)}
              className="px-3 py-2.5 rounded-xl text-sm text-white border focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
              style={{ background: 'rgba(255,255,255,0.05)', borderColor: 'rgba(255,255,255,0.1)' }}
            >
              {BANGLADESH_DISTRICTS.map((d) => (
                <option key={d} value={d} style={{ background: '#060B14' }}>{d}</option>
              ))}
            </select>
          </div>
          <button
            onClick={handleRunForecast}
            disabled={forecastMutation.isPending || historyQuery.isPending || !historyReady}
            className="px-5 py-2.5 rounded-xl font-semibold text-sm text-white flex items-center gap-2 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-300 disabled:opacity-60"
            style={{ background: 'linear-gradient(135deg, #38BDF8, #2DD4BF)' }}
          >
            {forecastMutation.isPending ? <Loader2 size={15} className="animate-spin" /> : <BarChart2 size={15} />}
            Run Forecast
          </button>
          {forecastMutation.data && (
            <>
              <button
                onClick={exportCSV}
                className="px-4 py-2.5 rounded-xl text-sm text-white/60 border border-white/10 hover:text-white hover:border-white/20 flex items-center gap-2 transition"
              >
                <Download size={14} /> Export CSV
              </button>
              <button
                onClick={exportPDF}
                className="px-4 py-2.5 rounded-xl text-sm text-white/60 border border-white/10 hover:text-white hover:border-white/20 flex items-center gap-2 transition"
              >
                <Download size={14} /> Export PDF
              </button>
            </>
          )}
        </div>

        {forecastMutation.isError && (
          <div className="flex items-center gap-2 text-amber-400 text-sm mb-4">
            <AlertCircle size={14} />
            {getApiErrorMessage(forecastMutation.error)}
          </div>
        )}

        {forecastMutation.data && (
          <div className="flex gap-6 mb-4">
            <div className="text-center">
              <div className="text-3xl font-black font-mono text-teal-400">
                +{Math.round(forecastMutation.data.forecast_next_7_days_cases)}
              </div>
              <div className="text-xs text-white/40 mt-1">cases (next 7 days)</div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-black font-mono text-amber-400">
                +{Math.round(forecastMutation.data.forecast_next_14_days_cases)}
              </div>
              <div className="text-xs text-white/40 mt-1">cases (next 14 days)</div>
            </div>
          </div>
        )}

        <ForecastChart weeks={weeks} forecast={forecastMutation.data ?? undefined} />
      </GlassCard>

      <GlassCard className="p-6">
        <div className="flex items-center gap-2 mb-4">
          <Filter size={16} className="text-teal-400" />
          <h2 className="text-sm font-semibold uppercase tracking-widest text-white/60">Prediction Reports</h2>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
          <select value={reportDistrict} onChange={(event) => setReportDistrict(event.target.value)} aria-label="Filter reports by district" className="px-3 py-2.5 rounded-xl text-sm text-white border border-white/10 bg-white/5">
            <option value="" style={{ background: '#060B14' }}>All districts</option>
            {BANGLADESH_DISTRICTS.map((district) => <option key={district} value={district} style={{ background: '#060B14' }}>{district}</option>)}
          </select>
          <select value={reportModel} onChange={(event) => setReportModel(event.target.value)} aria-label="Filter reports by model" className="px-3 py-2.5 rounded-xl text-sm text-white border border-white/10 bg-white/5">
            <option value="" style={{ background: '#060B14' }}>All prediction types</option>
            <option value="flood" style={{ background: '#060B14' }}>Flood</option>
            <option value="disease" style={{ background: '#060B14' }}>Disease</option>
            <option value="risk" style={{ background: '#060B14' }}>Composite risk</option>
            <option value="forecast" style={{ background: '#060B14' }}>Forecast</option>
          </select>
          <select value={reportRisk} onChange={(event) => setReportRisk(event.target.value)} aria-label="Filter reports by risk" className="px-3 py-2.5 rounded-xl text-sm text-white border border-white/10 bg-white/5">
            <option value="" style={{ background: '#060B14' }}>All risk levels</option>
            {['Low', 'Medium', 'High', 'Critical'].map((risk) => <option key={risk} value={risk} style={{ background: '#060B14' }}>{risk}</option>)}
          </select>
          <input type="date" value={reportFromDate} onChange={(event) => setReportFromDate(event.target.value)} aria-label="Filter reports from date" className="px-3 py-2.5 rounded-xl text-sm text-white border border-white/10 bg-white/5" />
        </div>
        {predictionHistoryQuery.isLoading ? <p className="text-xs text-white/40">Loading prediction history…</p> : visibleHistory.length === 0 ? <p className="text-xs text-white/40">No predictions match these filters yet.</p> : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="text-white/40 uppercase tracking-wider"><tr><th className="pb-2">Date</th><th className="pb-2">Type</th><th className="pb-2">District</th><th className="pb-2">Risk</th><th className="pb-2">Probability</th></tr></thead>
              <tbody>{visibleHistory.map((item) => <tr key={item.id} className="border-t border-white/06 text-white/65"><td className="py-2 pr-3">{new Date(item.created_at).toLocaleDateString()}</td><td className="py-2 pr-3 capitalize">{item.model_name}</td><td className="py-2 pr-3">{item.district ?? '—'}</td><td className="py-2 pr-3">{item.risk_level ?? '—'}</td><td className="py-2">{item.probability == null ? '—' : `${(item.probability * 100).toFixed(1)}%`}</td></tr>)}</tbody>
            </table>
          </div>
        )}
      </GlassCard>

    </div>
  );
}
