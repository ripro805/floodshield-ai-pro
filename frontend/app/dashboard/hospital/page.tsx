'use client';

import { useState, useEffect } from 'react';
import {
  Building2, Plus, ArrowUpRight, ArrowDownLeft, AlertCircle,
  CheckCircle2, Clock, ShieldAlert, Package, Activity, RefreshCw, Filter, Search
} from 'lucide-react';
import { useAuth } from '@/lib/auth';
import {
  getHospitalInventory, postHospitalStockTransaction,
  patchHospitalProfile, getHospitalForecastPrep,
  HospitalInventoryItem, HospitalStockTransaction, listHospitals
} from '@/lib/api';

export default function HospitalOperationsPage() {
  const { user } = useAuth();
  const [hospitalId, setHospitalId] = useState<string>('');
  const [hospitalName, setHospitalName] = useState<string>('Hospital Operations');
  const [inventory, setInventory] = useState<HospitalInventoryItem[]>([]);
  const [forecastPrep, setForecastPrep] = useState<any>(null);
  const [categoryFilter, setCategoryFilter] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);
  const [activeTab, setActiveTab] = useState<'inventory' | 'capacity' | 'forecast'>('inventory');

  // Transaction Modal State
  const [txModalOpen, setTxModalOpen] = useState<boolean>(false);
  const [selectedItem, setSelectedItem] = useState<HospitalInventoryItem | null>(null);
  const [txType, setTxType] = useState<string>('received');
  const [txQty, setTxQty] = useState<number>(50);
  const [txNotes, setTxNotes] = useState<string>('');
  const [txError, setTxError] = useState<string>('');
  const [txSuccess, setTxSuccess] = useState<string>('');
  const [submittingTx, setSubmittingTx] = useState<boolean>(false);

  // Capacity Form State
  const [generalBeds, setGeneralBeds] = useState<number>(100);
  const [occupiedBeds, setOccupiedBeds] = useState<number>(45);
  const [icuBeds, setIcuBeds] = useState<number>(12);
  const [occupiedIcu, setOccupiedIcu] = useState<number>(4);
  const [operatingStatus, setOperatingStatus] = useState<string>('normal');
  const [updatingCapacity, setUpdatingCapacity] = useState<boolean>(false);
  const [capacityFeedback, setCapacityFeedback] = useState<string>('');

  useEffect(() => {
    async function initHospital() {
      setLoading(true);
      try {
        const hospList = await listHospitals({ limit: 10 });
        if (hospList && hospList.length > 0) {
          const defaultHosp = hospList[0];
          setHospitalId(defaultHosp.id);
          setHospitalName(defaultHosp.name);
          setGeneralBeds(defaultHosp.total_beds || defaultHosp.beds || 100);
          setOccupiedBeds(defaultHosp.beds_occupied || 40);
          setIcuBeds(defaultHosp.icu_beds_total || 10);
          setOccupiedIcu(defaultHosp.icu_beds_occupied || 3);
          setOperatingStatus(defaultHosp.operating_status || 'normal');

          await loadData(defaultHosp.id);
        }
      } catch (err) {
        console.error('Error fetching hospital context:', err);
      } finally {
        setLoading(false);
      }
    }
    initHospital();
  }, []);

  async function loadData(id: string) {
    try {
      const invRes: any = await getHospitalInventory(id);
      const items = invRes?.items || invRes || [];
      setInventory(items);

      const prep = await getHospitalForecastPrep(id);
      setForecastPrep(prep);
    } catch (e) {
      console.warn('Error loading inventory/prep:', e);
    }
  }

  const filteredInventory = inventory.filter((item) => {
    const matchesCategory = !categoryFilter || item.category === categoryFilter;
    const matchesSearch = !searchQuery || item.item_name.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  const lowStockCount = inventory.filter((i) => i.current_stock < i.min_threshold).length;

  async function handleTransactionSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedItem || !hospitalId) return;
    setSubmittingTx(true);
    setTxError('');
    setTxSuccess('');

    try {
      const res = await postHospitalStockTransaction(hospitalId, selectedItem.id, {
        transaction_type: txType,
        quantity: Number(txQty),
        notes: txNotes,
      });
      setTxSuccess(`Stock updated successfully! New quantity: ${res.new_stock}`);
      await loadData(hospitalId);
      setTimeout(() => {
        setTxModalOpen(false);
        setTxSuccess('');
        setTxNotes('');
      }, 1200);
    } catch (err: any) {
      setTxError(err.response?.data?.detail || 'Stock transaction failed.');
    } finally {
      setSubmittingTx(false);
    }
  }

  async function handleCapacityUpdate(e: React.FormEvent) {
    e.preventDefault();
    if (!hospitalId) return;
    setUpdatingCapacity(true);
    setCapacityFeedback('');

    try {
      await patchHospitalProfile(hospitalId, {
        total_beds: Number(generalBeds),
        beds_occupied: Number(occupiedBeds),
        icu_beds_total: Number(icuBeds),
        icu_beds_occupied: Number(occupiedIcu),
        operating_status: operatingStatus,
      });
      setCapacityFeedback('Capacity and operating status saved successfully!');
      setTimeout(() => setCapacityFeedback(''), 3000);
    } catch (err: any) {
      setCapacityFeedback(err.response?.data?.detail || 'Failed to update capacity.');
    } finally {
      setUpdatingCapacity(false);
    }
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-6 rounded-2xl border border-white/10 bg-slate-900/60 backdrop-blur-xl">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-blue-600 to-teal-500 flex items-center justify-center shadow-lg shadow-blue-500/20">
            <Building2 className="text-white" size={28} />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white tracking-tight">{hospitalName}</h1>
            <p className="text-slate-400 text-sm">Clinical surge preparedness, live bed capacity, and pharmacy inventory control</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <span className={`px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wider border ${
            operatingStatus === 'surge_overflow' ? 'bg-red-500/20 text-red-300 border-red-500/40' :
            operatingStatus === 'high_surge' ? 'bg-amber-500/20 text-amber-300 border-amber-500/40' :
            'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
          }`}>
            {operatingStatus.replace('_', ' ')}
          </span>
          <button
            onClick={() => hospitalId && loadData(hospitalId)}
            className="p-2.5 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 text-slate-300 transition"
            title="Refresh Hospital Data"
          >
            <RefreshCw size={18} />
          </button>
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-5 rounded-2xl border border-white/10 bg-slate-900/40 backdrop-blur">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs uppercase font-medium">General Beds Available</span>
            <Activity size={16} className="text-blue-400" />
          </div>
          <div className="text-3xl font-extrabold text-white">
            {Math.max(0, generalBeds - occupiedBeds)} <span className="text-sm font-normal text-slate-400">/ {generalBeds}</span>
          </div>
          <div className="mt-2 text-xs text-slate-400">
            {((occupiedBeds / (generalBeds || 1)) * 100).toFixed(0)}% Occupancy Rate
          </div>
        </div>

        <div className="p-5 rounded-2xl border border-white/10 bg-slate-900/40 backdrop-blur">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs uppercase font-medium">ICU Beds Available</span>
            <Building2 size={16} className="text-teal-400" />
          </div>
          <div className="text-3xl font-extrabold text-white">
            {Math.max(0, icuBeds - occupiedIcu)} <span className="text-sm font-normal text-slate-400">/ {icuBeds}</span>
          </div>
          <div className="mt-2 text-xs text-slate-400">
            Critical respiratory & triage unit
          </div>
        </div>

        <div className="p-5 rounded-2xl border border-white/10 bg-slate-900/40 backdrop-blur">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs uppercase font-medium">Inventory Shortages</span>
            <AlertCircle size={16} className="text-amber-400" />
          </div>
          <div className="text-3xl font-extrabold text-amber-400">
            {lowStockCount} <span className="text-sm font-normal text-slate-400">items below min</span>
          </div>
          <div className="mt-2 text-xs text-slate-400">
            Automated restock threshold active
          </div>
        </div>

        <div className="p-5 rounded-2xl border border-white/10 bg-slate-900/40 backdrop-blur">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs uppercase font-medium">14-Day Surge Outlook</span>
            <ShieldAlert size={16} className="text-purple-400" />
          </div>
          <div className="text-3xl font-extrabold text-purple-300">
            {forecastPrep?.forecast?.day14_projected_cases ?? '~45'} <span className="text-sm font-normal text-slate-400">cases</span>
          </div>
          <div className="mt-2 text-xs text-slate-400">
            AI trend: {forecastPrep?.forecast?.trend ?? 'Monitoring'}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-white/10 pb-2">
        <button
          onClick={() => setActiveTab('inventory')}
          className={`px-4 py-2 rounded-xl text-sm font-medium transition ${
            activeTab === 'inventory' ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/20' : 'text-slate-400 hover:text-white'
          }`}
        >
          Dynamic Pharmacy Inventory
        </button>
        <button
          onClick={() => setActiveTab('capacity')}
          className={`px-4 py-2 rounded-xl text-sm font-medium transition ${
            activeTab === 'capacity' ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/20' : 'text-slate-400 hover:text-white'
          }`}
        >
          Bed & ICU Capacity Control
        </button>
        <button
          onClick={() => setActiveTab('forecast')}
          className={`px-4 py-2 rounded-xl text-sm font-medium transition ${
            activeTab === 'forecast' ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/20' : 'text-slate-400 hover:text-white'
          }`}
        >
          Surge Forecast & Recommendations
        </button>
      </div>

      {/* TAB 1: INVENTORY */}
      {activeTab === 'inventory' && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row gap-3 justify-between items-center bg-slate-900/40 p-4 rounded-2xl border border-white/10">
            <div className="flex items-center gap-2 w-full sm:w-80 bg-slate-950/60 px-3 py-2 rounded-xl border border-white/10">
              <Search size={16} className="text-slate-400" />
              <input
                type="text"
                placeholder="Search medicines, saline, ORS..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="bg-transparent border-none text-white text-sm outline-none w-full"
              />
            </div>

            <div className="flex items-center gap-2 w-full sm:w-auto">
              <Filter size={16} className="text-slate-400" />
              <select
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                className="bg-slate-950/60 border border-white/10 text-white text-sm rounded-xl px-3 py-2 outline-none"
              >
                <option value="">All Categories</option>
                <option value="medicine">Medicines</option>
                <option value="iv_fluid">IV Fluids</option>
                <option value="consumable">Consumables</option>
                <option value="equipment">Equipment</option>
              </select>
            </div>
          </div>

          <div className="overflow-x-auto rounded-2xl border border-white/10 bg-slate-900/40 backdrop-blur">
            <table className="w-full text-left border-collapse text-sm">
              <thead>
                <tr className="border-b border-white/10 text-slate-400 uppercase text-xs font-semibold">
                  <th className="py-4 px-5">Item Name</th>
                  <th className="py-4 px-5">Category</th>
                  <th className="py-4 px-5">Stock Level</th>
                  <th className="py-4 px-5">Min Threshold</th>
                  <th className="py-4 px-5">Status</th>
                  <th className="py-4 px-5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 text-slate-200">
                {filteredInventory.map((item) => {
                  const isLow = item.current_stock < item.min_threshold;
                  return (
                    <tr key={item.id} className="hover:bg-white/5 transition">
                      <td className="py-4 px-5 font-medium text-white flex items-center gap-3">
                        <Package size={18} className="text-blue-400 shrink-0" />
                        <div>
                          <div>{item.item_name}</div>
                          {item.batch_number && (
                            <div className="text-xs text-slate-500 font-mono">Batch: {item.batch_number}</div>
                          )}
                        </div>
                      </td>
                      <td className="py-4 px-5 capitalize text-slate-400">{item.category.replace('_', ' ')}</td>
                      <td className="py-4 px-5 font-bold text-lg">
                        {item.current_stock} <span className="text-xs font-normal text-slate-400">{item.unit}</span>
                      </td>
                      <td className="py-4 px-5 text-slate-400">{item.min_threshold} {item.unit}</td>
                      <td className="py-4 px-5">
                        {isLow ? (
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-red-500/20 text-red-300 border border-red-500/40">
                            <AlertCircle size={12} /> Critical Shortage
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                            <CheckCircle2 size={12} /> Stock Adequate
                          </span>
                        )}
                      </td>
                      <td className="py-4 px-5 text-right">
                        <button
                          onClick={() => {
                            setSelectedItem(item);
                            setTxQty(20);
                            setTxModalOpen(true);
                          }}
                          className="px-3 py-1.5 rounded-lg border border-white/10 bg-white/5 hover:bg-white/15 text-white text-xs font-medium transition"
                        >
                          Record Stock
                        </button>
                      </td>
                    </tr>
                  );
                })}
                {filteredInventory.length === 0 && (
                  <tr>
                    <td colSpan={6} className="text-center py-8 text-slate-500">
                      No inventory items match your search or filter.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 2: CAPACITY */}
      {activeTab === 'capacity' && (
        <form onSubmit={handleCapacityUpdate} className="p-6 rounded-2xl border border-white/10 bg-slate-900/40 backdrop-blur space-y-6">
          <div className="border-b border-white/10 pb-4">
            <h2 className="text-lg font-bold text-white">Hospital Bed & Operational Status Management</h2>
            <p className="text-xs text-slate-400">Updates live bed availability published to emergency coordination portals and citizens.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-xs uppercase font-medium text-slate-400 mb-2">Total General Beds</label>
              <input
                type="number"
                min="0"
                value={generalBeds}
                onChange={(e) => setGeneralBeds(Number(e.target.value))}
                className="w-full bg-slate-950/60 border border-white/10 rounded-xl px-4 py-2.5 text-white outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs uppercase font-medium text-slate-400 mb-2">Occupied General Beds</label>
              <input
                type="number"
                min="0"
                max={generalBeds}
                value={occupiedBeds}
                onChange={(e) => setOccupiedBeds(Number(e.target.value))}
                className="w-full bg-slate-950/60 border border-white/10 rounded-xl px-4 py-2.5 text-white outline-none focus:border-blue-500"
              />
            </div>

            <div>
              <label className="block text-xs uppercase font-medium text-slate-400 mb-2">Total ICU Beds</label>
              <input
                type="number"
                min="0"
                value={icuBeds}
                onChange={(e) => setIcuBeds(Number(e.target.value))}
                className="w-full bg-slate-950/60 border border-white/10 rounded-xl px-4 py-2.5 text-white outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs uppercase font-medium text-slate-400 mb-2">Occupied ICU Beds</label>
              <input
                type="number"
                min="0"
                max={icuBeds}
                value={occupiedIcu}
                onChange={(e) => setOccupiedIcu(Number(e.target.value))}
                className="w-full bg-slate-950/60 border border-white/10 rounded-xl px-4 py-2.5 text-white outline-none focus:border-blue-500"
              />
            </div>

            <div className="md:col-span-2">
              <label className="block text-xs uppercase font-medium text-slate-400 mb-2">Current Operating Status</label>
              <select
                value={operatingStatus}
                onChange={(e) => setOperatingStatus(e.target.value)}
                className="w-full bg-slate-950/60 border border-white/10 rounded-xl px-4 py-2.5 text-white outline-none focus:border-blue-500"
              >
                <option value="normal">Normal Operations</option>
                <option value="high_surge">High Surge Intake</option>
                <option value="critical_divert">Critical Divert / Emergency Only</option>
                <option value="surge_overflow">Surge Overflow (Temporary Capacity)</option>
              </select>
            </div>
          </div>

          {capacityFeedback && (
            <div className="p-3 rounded-xl bg-blue-500/20 border border-blue-500/40 text-blue-200 text-sm">
              {capacityFeedback}
            </div>
          )}

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={updatingCapacity}
              className="px-6 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold text-sm transition shadow-lg shadow-blue-500/20 disabled:opacity-50"
            >
              {updatingCapacity ? 'Saving...' : 'Update Facility Capacity'}
            </button>
          </div>
        </form>
      )}

      {/* TAB 3: FORECAST & PREPARATION */}
      {activeTab === 'forecast' && (
        <div className="p-6 rounded-2xl border border-white/10 bg-slate-900/40 backdrop-blur space-y-6">
          <div className="border-b border-white/10 pb-4">
            <h2 className="text-lg font-bold text-white">LSTM Early-Warning Surge Preparation</h2>
            <p className="text-xs text-slate-400">Integrated Model 3 time-series forecast connected to clinical resource consumption models.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="p-5 rounded-2xl border border-white/10 bg-slate-950/40 space-y-3">
              <h3 className="text-sm font-semibold text-slate-300">14-Day Demand Projections</h3>
              <div className="flex justify-between items-center text-sm py-2 border-b border-white/5">
                <span className="text-slate-400">7-Day Projected Caseload</span>
                <span className="font-bold text-white">{forecastPrep?.forecast?.day7_projected_cases ?? 35} patients</span>
              </div>
              <div className="flex justify-between items-center text-sm py-2 border-b border-white/5">
                <span className="text-slate-400">14-Day Projected Caseload</span>
                <span className="font-bold text-white">{forecastPrep?.forecast?.day14_projected_cases ?? 50} patients</span>
              </div>
              <div className="flex justify-between items-center text-sm py-2 border-b border-white/5">
                <span className="text-slate-400">Estimated ORS Requirement</span>
                <span className="font-bold text-teal-400">{forecastPrep?.supplies_adequacy?.projected_ors_demand_14d ?? 175} packets</span>
              </div>
              <div className="flex justify-between items-center text-sm py-2">
                <span className="text-slate-400">Estimated IV Saline Requirement</span>
                <span className="font-bold text-blue-400">{forecastPrep?.supplies_adequacy?.projected_saline_demand_14d ?? 90} bags</span>
              </div>
            </div>

            <div className="p-5 rounded-2xl border border-white/10 bg-slate-950/40 space-y-3">
              <h3 className="text-sm font-semibold text-slate-300">Actionable Preparation Advice</h3>
              <ul className="space-y-2 text-xs text-slate-300">
                {(forecastPrep?.preparation_recommendations || [
                  'Pre-position 200 additional units of ORS sachets in emergency triage.',
                  'Notify on-call nursing staff for potential diarrhea cluster intake.',
                  'Verify water purification stock for outpatient distribution.'
                ]).map((rec: string, idx: number) => (
                  <li key={idx} className="flex items-start gap-2 bg-white/5 p-2.5 rounded-xl border border-white/5">
                    <CheckCircle2 size={16} className="text-blue-400 shrink-0 mt-0.5" />
                    <span>{rec}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {forecastPrep?.warnings && forecastPrep.warnings.length > 0 && (
            <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs space-y-1">
              <div className="font-bold flex items-center gap-1.5">
                <AlertCircle size={14} /> Critical Surge Warnings
              </div>
              {forecastPrep.warnings.map((w: string, idx: number) => (
                <div key={idx}>• {w}</div>
              ))}
            </div>
          )}

          <div className="text-[11px] text-slate-500">
            * Disclaimer: Forecasts are early-warning probability estimates derived from climate and historical epidemiological features. They represent decision support guidance, not clinical guarantees.
          </div>
        </div>
      )}

      {/* TRANSACTION MODAL */}
      {txModalOpen && selectedItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="w-full max-w-md p-6 rounded-2xl border border-white/10 bg-slate-900 shadow-2xl space-y-5">
            <div>
              <h3 className="text-lg font-bold text-white">Record Stock Transaction</h3>
              <p className="text-xs text-slate-400">{selectedItem.item_name} (Current: {selectedItem.current_stock} {selectedItem.unit})</p>
            </div>

            <form onSubmit={handleTransactionSubmit} className="space-y-4">
              <div>
                <label className="block text-xs uppercase font-medium text-slate-400 mb-1.5">Action Type</label>
                <select
                  value={txType}
                  onChange={(e) => setTxType(e.target.value)}
                  className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2 text-white text-sm outline-none"
                >
                  <option value="received">Receive Inbound Stock (+)</option>
                  <option value="consumed">Dispense to Patients / Wards (-)</option>
                  <option value="distributed">Transfer to Field / Shelter (-)</option>
                  <option value="damaged">Damaged / Expired Removal (-)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs uppercase font-medium text-slate-400 mb-1.5">Quantity ({selectedItem.unit})</label>
                <input
                  type="number"
                  min="1"
                  value={txQty}
                  onChange={(e) => setTxQty(Number(e.target.value))}
                  required
                  className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2 text-white text-sm outline-none"
                />
              </div>

              <div>
                <label className="block text-xs uppercase font-medium text-slate-400 mb-1.5">Notes / Justification</label>
                <input
                  type="text"
                  placeholder="e.g. DGHS shipment, cholera ward distribution"
                  value={txNotes}
                  onChange={(e) => setTxNotes(e.target.value)}
                  className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2 text-white text-sm outline-none"
                />
              </div>

              {txError && (
                <div className="p-2.5 rounded-lg bg-red-500/20 border border-red-500/40 text-red-300 text-xs">
                  {txError}
                </div>
              )}
              {txSuccess && (
                <div className="p-2.5 rounded-lg bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 text-xs">
                  {txSuccess}
                </div>
              )}

              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setTxModalOpen(false)}
                  className="px-4 py-2 rounded-xl border border-white/10 text-slate-300 text-xs hover:bg-white/5"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingTx}
                  className="px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-lg shadow-blue-500/20 disabled:opacity-50"
                >
                  {submittingTx ? 'Recording...' : 'Commit Transaction'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
