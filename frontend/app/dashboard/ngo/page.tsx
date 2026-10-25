'use client';

import { useState, useEffect } from 'react';
import {
  HeartHandshake, Plus, Package, Truck, Sparkles, AlertCircle,
  CheckCircle2, Users, MapPin, Calendar, RefreshCw
} from 'lucide-react';
import { useAuth } from '@/lib/auth';
import {
  listNgoCampaigns, createNgoCampaign, patchNgoCampaignStatus,
  listNgoInventory, postNgoStockTransaction, listNgoDistributionTasks,
  createNgoDistributionTask, getNgoAiAllocation,
  ReliefCampaign, NgoInventoryItem, ReliefDistributionTask
} from '@/lib/api';

export default function NgoOperationsPage() {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<'campaigns' | 'inventory' | 'distribution' | 'ai'>('campaigns');

  const [campaigns, setCampaigns] = useState<ReliefCampaign[]>([]);
  const [inventory, setInventory] = useState<NgoInventoryItem[]>([]);
  const [tasks, setTasks] = useState<ReliefDistributionTask[]>([]);
  const [aiAllocation, setAiAllocation] = useState<any>(null);
  const [selectedDistrict, setSelectedDistrict] = useState<string>('Feni');
  const [loading, setLoading] = useState<boolean>(true);

  // New Campaign Form
  const [campTitle, setCampTitle] = useState('');
  const [campDistricts, setCampDistricts] = useState('Feni');
  const [campPopulation, setCampPopulation] = useState(3000);
  const [campStartDate, setCampStartDate] = useState(new Date().toISOString().split('T')[0]);
  const [creatingCamp, setCreatingCamp] = useState(false);

  // New Task Form
  const [taskTitle, setTaskTitle] = useState('');
  const [taskDistrict, setTaskDistrict] = useState('Feni');
  const [taskUpazila, setTaskUpazila] = useState('Feni Sadar');
  const [taskHouseholds, setTaskHouseholds] = useState(100);
  const [creatingTask, setCreatingTask] = useState(false);

  useEffect(() => {
    loadAll();
  }, []);

  async function loadAll() {
    setLoading(true);
    try {
      const campRes: any = await listNgoCampaigns();
      setCampaigns(campRes?.campaigns || campRes || []);

      const invRes: any = await listNgoInventory();
      setInventory(invRes?.items || invRes || []);

      const taskRes: any = await listNgoDistributionTasks();
      setTasks(taskRes?.tasks || taskRes || []);

      const aiRes = await getNgoAiAllocation(selectedDistrict);
      setAiAllocation(aiRes);
    } catch (e) {
      console.warn('Error loading NGO operations data:', e);
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateCampaign(e: React.FormEvent) {
    e.preventDefault();
    setCreatingCamp(true);
    try {
      await createNgoCampaign({
        title: campTitle,
        target_districts: campDistricts,
        target_population: Number(campPopulation),
        start_date: campStartDate,
      });
      setCampTitle('');
      await loadAll();
    } catch (err) {
      console.error(err);
    } finally {
      setCreatingCamp(false);
    }
  }

  async function handleToggleCampaign(id: string, currentStatus: string) {
    const nextStatus = currentStatus === 'active' ? 'paused' : 'active';
    try {
      await patchNgoCampaignStatus(id, nextStatus);
      await loadAll();
    } catch (err) {
      console.error(err);
    }
  }

  async function handleCreateTask(e: React.FormEvent) {
    e.preventDefault();
    setCreatingTask(true);
    try {
      await createNgoDistributionTask({
        title: taskTitle,
        district: taskDistrict,
        upazila: taskUpazila,
        beneficiary_households: Number(taskHouseholds),
        people_reached: Number(taskHouseholds) * 4,
        status: 'in_transit',
      });
      setTaskTitle('');
      await loadAll();
    } catch (err) {
      console.error(err);
    } finally {
      setCreatingTask(false);
    }
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-6 rounded-2xl border border-white/10 bg-slate-900/60 backdrop-blur-xl">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-amber-500 to-orange-500 flex items-center justify-center shadow-lg shadow-orange-500/20">
            <HeartHandshake className="text-white" size={28} />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white tracking-tight">NGO Relief & Field Distribution</h1>
            <p className="text-slate-400 text-sm">Targeted disaster supply dispatch, warehouse stocks, and AI-optimized quotas</p>
          </div>
        </div>

        <button
          onClick={loadAll}
          className="p-2.5 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 text-slate-300 transition"
          title="Refresh Data"
        >
          <RefreshCw size={18} />
        </button>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-white/10 pb-2">
        <button
          onClick={() => setActiveTab('campaigns')}
          className={`px-4 py-2 rounded-xl text-sm font-medium transition ${
            activeTab === 'campaigns' ? 'bg-amber-600 text-white shadow-lg shadow-amber-500/20' : 'text-slate-400 hover:text-white'
          }`}
        >
          Relief Campaigns
        </button>
        <button
          onClick={() => setActiveTab('inventory')}
          className={`px-4 py-2 rounded-xl text-sm font-medium transition ${
            activeTab === 'inventory' ? 'bg-amber-600 text-white shadow-lg shadow-amber-500/20' : 'text-slate-400 hover:text-white'
          }`}
        >
          NGO Warehouse Inventory
        </button>
        <button
          onClick={() => setActiveTab('distribution')}
          className={`px-4 py-2 rounded-xl text-sm font-medium transition ${
            activeTab === 'distribution' ? 'bg-amber-600 text-white shadow-lg shadow-amber-500/20' : 'text-slate-400 hover:text-white'
          }`}
        >
          Distribution Tasks
        </button>
        <button
          onClick={() => setActiveTab('ai')}
          className={`px-4 py-2 rounded-xl text-sm font-medium transition ${
            activeTab === 'ai' ? 'bg-amber-600 text-white shadow-lg shadow-amber-500/20' : 'text-slate-400 hover:text-white'
          }`}
        >
          AI-Assisted Allocation
        </button>
      </div>

      {/* TAB 1: CAMPAIGNS */}
      {activeTab === 'campaigns' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-4">
            <h2 className="text-lg font-bold text-white">Active Relief Operations</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {campaigns.map((c) => (
                <div key={c.id} className="p-5 rounded-2xl border border-white/10 bg-slate-900/40 backdrop-blur space-y-3">
                  <div className="flex justify-between items-start">
                    <div>
                      <h3 className="font-bold text-white text-base">{c.title}</h3>
                      <span className="text-xs text-slate-400 flex items-center gap-1 mt-0.5">
                        <MapPin size={12} /> {c.target_districts}
                      </span>
                    </div>
                    <span className={`px-2 py-0.5 rounded-full text-xs font-semibold uppercase ${
                      c.status === 'active' ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40' :
                      'bg-slate-500/20 text-slate-300 border border-slate-500/40'
                    }`}>
                      {c.status}
                    </span>
                  </div>

                  <div className="flex items-center justify-between text-xs text-slate-300 py-2 border-y border-white/5">
                    <span className="flex items-center gap-1.5"><Users size={14} className="text-amber-400" /> Target Pop: {c.target_population.toLocaleString()}</span>
                    <span className="flex items-center gap-1.5"><Calendar size={14} className="text-slate-400" /> Start: {c.start_date}</span>
                  </div>

                  <div className="flex justify-end pt-1">
                    <button
                      onClick={() => handleToggleCampaign(c.id, c.status)}
                      className="px-3 py-1.5 rounded-lg border border-white/10 text-xs font-medium text-slate-300 hover:bg-white/5 transition"
                    >
                      {c.status === 'active' ? 'Pause Campaign' : 'Resume Campaign'}
                    </button>
                  </div>
                </div>
              ))}
              {campaigns.length === 0 && (
                <div className="col-span-2 text-center py-12 text-slate-500 bg-slate-900/20 rounded-2xl border border-white/5">
                  No active campaigns found. Launch a new campaign using the form.
                </div>
              )}
            </div>
          </div>

          <form onSubmit={handleCreateCampaign} className="p-5 rounded-2xl border border-white/10 bg-slate-900/50 backdrop-blur space-y-4 h-fit">
            <h3 className="text-base font-bold text-white">Launch New Campaign</h3>
            <div>
              <label className="block text-xs uppercase font-medium text-slate-400 mb-1">Campaign Title</label>
              <input
                type="text"
                required
                placeholder="e.g. Sylhet Emergency WASH Drive"
                value={campTitle}
                onChange={(e) => setCampTitle(e.target.value)}
                className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2 text-white text-sm outline-none"
              />
            </div>
            <div>
              <label className="block text-xs uppercase font-medium text-slate-400 mb-1">Target Districts</label>
              <input
                type="text"
                required
                value={campDistricts}
                onChange={(e) => setCampDistricts(e.target.value)}
                className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2 text-white text-sm outline-none"
              />
            </div>
            <div>
              <label className="block text-xs uppercase font-medium text-slate-400 mb-1">Target Beneficiary Population</label>
              <input
                type="number"
                min="100"
                value={campPopulation}
                onChange={(e) => setCampPopulation(Number(e.target.value))}
                className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2 text-white text-sm outline-none"
              />
            </div>
            <div>
              <label className="block text-xs uppercase font-medium text-slate-400 mb-1">Start Date</label>
              <input
                type="date"
                required
                value={campStartDate}
                onChange={(e) => setCampStartDate(e.target.value)}
                className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2 text-white text-sm outline-none"
              />
            </div>
            <button
              type="submit"
              disabled={creatingCamp}
              className="w-full py-2.5 rounded-xl bg-amber-600 hover:bg-amber-500 text-white font-semibold text-sm transition shadow-lg shadow-amber-500/20 disabled:opacity-50"
            >
              {creatingCamp ? 'Creating...' : 'Initialize Campaign'}
            </button>
          </form>
        </div>
      )}

      {/* TAB 2: INVENTORY */}
      {activeTab === 'inventory' && (
        <div className="overflow-x-auto rounded-2xl border border-white/10 bg-slate-900/40 backdrop-blur">
          <table className="w-full text-left border-collapse text-sm">
            <thead>
              <tr className="border-b border-white/10 text-slate-400 uppercase text-xs font-semibold">
                <th className="py-4 px-5">Relief Commodity</th>
                <th className="py-4 px-5">Category</th>
                <th className="py-4 px-5">Warehouse Location</th>
                <th className="py-4 px-5">Current Stock</th>
                <th className="py-4 px-5">Threshold</th>
                <th className="py-4 px-5">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 text-slate-200">
              {inventory.map((item) => (
                <tr key={item.id} className="hover:bg-white/5 transition">
                  <td className="py-4 px-5 font-medium text-white flex items-center gap-2">
                    <Package size={16} className="text-amber-400 shrink-0" />
                    {item.item_name}
                  </td>
                  <td className="py-4 px-5 capitalize text-slate-400">{item.category.replace('_', ' ')}</td>
                  <td className="py-4 px-5 text-slate-400">{item.warehouse_location || 'Central Depot'}</td>
                  <td className="py-4 px-5 font-bold text-lg">{item.current_stock} <span className="text-xs font-normal text-slate-400">{item.unit}</span></td>
                  <td className="py-4 px-5 text-slate-400">{item.min_threshold} {item.unit}</td>
                  <td className="py-4 px-5">
                    {item.current_stock < item.min_threshold ? (
                      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-red-500/20 text-red-300 border border-red-500/40">
                        <AlertCircle size={12} /> Low Stock
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                        <CheckCircle2 size={12} /> Sufficient
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* TAB 3: DISTRIBUTION TASKS */}
      {activeTab === 'distribution' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-4">
            <h2 className="text-lg font-bold text-white">Field Distribution Tracking</h2>
            <div className="space-y-3">
              {tasks.map((t) => (
                <div key={t.id} className="p-4 rounded-xl border border-white/10 bg-slate-900/40 backdrop-blur flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center text-blue-400">
                      <Truck size={20} />
                    </div>
                    <div>
                      <div className="font-bold text-white text-sm">{t.title}</div>
                      <div className="text-xs text-slate-400">{t.district} • {t.upazila || 'All Unions'} • {t.beneficiary_households} Households</div>
                    </div>
                  </div>
                  <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-blue-500/20 text-blue-300 border border-blue-500/40 capitalize">
                    {t.status.replace('_', ' ')}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <form onSubmit={handleCreateTask} className="p-5 rounded-2xl border border-white/10 bg-slate-900/50 backdrop-blur space-y-4 h-fit">
            <h3 className="text-base font-bold text-white">Schedule Field Drop</h3>
            <div>
              <label className="block text-xs uppercase font-medium text-slate-400 mb-1">Task Title</label>
              <input
                type="text"
                required
                placeholder="e.g. Parshuram Ward 2 Water Purification Distribution"
                value={taskTitle}
                onChange={(e) => setTaskTitle(e.target.value)}
                className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2 text-white text-sm outline-none"
              />
            </div>
            <div>
              <label className="block text-xs uppercase font-medium text-slate-400 mb-1">District</label>
              <input
                type="text"
                required
                value={taskDistrict}
                onChange={(e) => setTaskDistrict(e.target.value)}
                className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2 text-white text-sm outline-none"
              />
            </div>
            <div>
              <label className="block text-xs uppercase font-medium text-slate-400 mb-1">Upazila / Union</label>
              <input
                type="text"
                required
                value={taskUpazila}
                onChange={(e) => setTaskUpazila(e.target.value)}
                className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2 text-white text-sm outline-none"
              />
            </div>
            <div>
              <label className="block text-xs uppercase font-medium text-slate-400 mb-1">Target Households</label>
              <input
                type="number"
                min="10"
                value={taskHouseholds}
                onChange={(e) => setTaskHouseholds(Number(e.target.value))}
                className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-2 text-white text-sm outline-none"
              />
            </div>
            <button
              type="submit"
              disabled={creatingTask}
              className="w-full py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold text-sm transition shadow-lg shadow-blue-500/20 disabled:opacity-50"
            >
              {creatingTask ? 'Dispatching...' : 'Dispatch Team'}
            </button>
          </form>
        </div>
      )}

      {/* TAB 4: AI ALLOCATION */}
      {activeTab === 'ai' && (
        <div className="p-6 rounded-2xl border border-white/10 bg-slate-900/40 backdrop-blur space-y-6">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b border-white/10 pb-4">
            <div>
              <div className="flex items-center gap-2">
                <Sparkles size={20} className="text-amber-400" />
                <h2 className="text-lg font-bold text-white">AI-Assisted Relief Allocation (Models 5 & 6)</h2>
              </div>
              <p className="text-xs text-slate-400">Algorithmic supply distribution calculated from disease risk indicators and historical vulnerability.</p>
            </div>

            <select
              value={selectedDistrict}
              onChange={async (e) => {
                setSelectedDistrict(e.target.value);
                const res = await getNgoAiAllocation(e.target.value);
                setAiAllocation(res);
              }}
              className="bg-slate-950 border border-white/10 rounded-xl px-3 py-2 text-white text-sm outline-none"
            >
              <option value="Feni">Feni District</option>
              <option value="Sylhet">Sylhet District</option>
              <option value="Sunamganj">Sunamganj District</option>
              <option value="Kurigram">Kurigram District</option>
            </select>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="p-5 rounded-2xl border border-white/10 bg-slate-950/40 space-y-3">
              <h3 className="text-sm font-semibold text-slate-300">Model 6 Action Recommendations</h3>
              <p className="text-sm text-slate-200 bg-white/5 p-3 rounded-xl border border-white/5">
                {aiAllocation?.model_recommendation ?? 'Priority relief deployment recommended for flood-affected unions.'}
              </p>
              <div className="text-xs text-slate-400 font-medium">Priority Interventions:</div>
              <ul className="space-y-1.5 text-xs text-slate-300">
                {(aiAllocation?.suggested_interventions || [
                  'Pre-position oral rehydration salts in Union Health Sub-Centers',
                  'Deploy mobile water purification units along river embankments'
                ]).map((intv: string, idx: number) => (
                  <li key={idx} className="flex items-center gap-2">
                    <CheckCircle2 size={14} className="text-emerald-400 shrink-0" />
                    <span>{intv}</span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="p-5 rounded-2xl border border-white/10 bg-slate-950/40 space-y-3">
              <h3 className="text-sm font-semibold text-slate-300">Calculated Supply Quotas</h3>
              <div className="space-y-2">
                {(aiAllocation?.ai_suggested_relief_targets?.suggested_supplies || [
                  { item: 'Water Purification Chlorine Tablets', suggested_qty: 10000, unit: 'tablet' },
                  { item: 'Oral Rehydration Solution (ORS) Sachets', suggested_qty: 3000, unit: 'packet' },
                  { item: 'Emergency Dry Food Relief Rations', suggested_qty: 1000, unit: 'pack' },
                ]).map((sup: any, idx: number) => (
                  <div key={idx} className="flex justify-between items-center text-xs py-2 border-b border-white/5">
                    <span className="text-slate-300 font-medium">{sup.item}</span>
                    <span className="font-bold text-amber-400">{sup.suggested_qty.toLocaleString()} {sup.unit}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="text-[11px] text-slate-500">
            * Human-in-the-loop requirement: These figures represent optimization calculations based on epidemiological models. Final relief dispatch requires authorized NGO field director confirmation.
          </div>
        </div>
      )}
    </div>
  );
}
