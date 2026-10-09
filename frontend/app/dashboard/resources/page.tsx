'use client';

import { useState, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import { motion } from 'framer-motion';
import GlassCard from '@/components/cards/GlassCard';
import RecommendationCard from '@/components/cards/RecommendationCard';
import HospitalStockCard from '@/components/cards/HospitalStockCard';
import AuthGuard from '@/components/layout/AuthGuard';
import { useRecommendation } from '@/hooks';
import { BANGLADESH_DISTRICTS } from '@/lib/types';
import { AlertCircle, Building2, Loader2, Search, Sparkles, Hospital } from 'lucide-react';
import { getApiErrorMessage } from '@/lib/api';
import HospitalInventoryManager from '@/components/resources/HospitalInventoryManager';
import HospitalDirectoryView from './directory/HospitalDirectoryView';
import { useAuth } from '@/lib/auth';

const cardVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: (i: number) => ({ opacity: 1, y: 0, transition: { delay: i * 0.09, duration: 0.4 } }),
};

type Tab = 'recommend' | 'inventory' | 'directory';

export default function ResourcesPage() {
  const { user } = useAuth();
  const searchParams = useSearchParams();
  const [tab, setTab] = useState<Tab>(
    (searchParams?.get('tab') as Tab) || 'recommend'
  );
  const [district, setDistrict] = useState(
    searchParams?.get('district') || 'Dhaka'
  );

  // Propagate chatbot deep-link (already in initial state) but also
  // react to in-page changes.
  useEffect(() => {
    const t = searchParams?.get('tab');
    if (t === 'directory' || t === 'inventory' || t === 'recommend') {
      setTab(t);
    }
  }, [searchParams]);
  const [riskLevel, setRiskLevel] = useState<'Low' | 'Medium' | 'High' | 'Critical'>('High');

  const recommendMutation = useRecommendation();

  const handleSearch = () => {
    recommendMutation.mutate({ district, risk_level: riskLevel });
  };

  // The inventory manager has its own district picker, so we hide the
  // existing recommend tab for admin / operational users; they can also
  // still see the AI recommendation card.
  const tabs: Array<{ id: Tab; label: string; icon: typeof Sparkles }> = [
    { id: 'recommend', label: 'AI Recommendations', icon: Sparkles },
    { id: 'inventory', label: 'Hospital Inventory', icon: Hospital },
    { id: 'directory', label: 'Directory', icon: Building2 },
  ];

  // Inventory editing is operational-only; citizens can view but not edit.
  // The component itself enforces per-district write rules.
  const canEditInventory = user
    ? ['admin', 'government', 'health_worker', 'hospital', 'ngo'].includes(user.role)
    : false;

  return (
    <AuthGuard allowedRoles={['health_worker', 'hospital', 'ngo', 'government', 'admin', 'citizen']}>
      <div className="max-w-6xl mx-auto space-y-6">
        <motion.div custom={0} variants={cardVariants} initial="hidden" animate="visible">
          <h1 className="text-3xl font-black text-white" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
            Hospital Resources
          </h1>
          <p className="text-white/50 mt-1">
            AI-powered resource recommendations by district and risk level, plus a live hospital-stock editor.
          </p>
        </motion.div>

        {/* Tab bar */}
        <div className="flex flex-wrap gap-2 border-b border-white/10 pb-1">
          {tabs.map((t) => {
            const Icon = t.icon;
            const active = tab === t.id;
            return (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                style={{
                  display: 'flex', alignItems: 'center', gap: '8px',
                  padding: '10px 18px', borderRadius: '10px 10px 0 0',
                  background: active ? 'rgba(56,189,248,0.12)' : 'transparent',
                  color: active ? '#7DD3FC' : 'rgba(255,255,255,0.55)',
                  fontSize: '14px', fontWeight: 600, cursor: 'pointer',
                  borderBottom: active ? '2px solid #38BDF8' : '2px solid transparent',
                }}
              >
                <Icon size={15} /> {t.label}
                {t.id === 'inventory' && !canEditInventory && (
                  <span className="text-[10px] text-amber-300/80 font-normal">(view only)</span>
                )}
              </button>
            );
          })}
        </div>

        {tab === 'recommend' && (
          <>
            {/* Controls */}
            <motion.div custom={1} variants={cardVariants} initial="hidden" animate="visible">
              <GlassCard className="p-6">
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-white/60 uppercase tracking-wider mb-1.5" htmlFor="resources-district">
                      District
                    </label>
                    <select
                      id="resources-district"
                      value={district}
                      onChange={(e) => setDistrict(e.target.value)}
                      className="w-full px-3 py-2.5 rounded-xl text-sm text-white border focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
                      style={{ background: 'rgba(255,255,255,0.05)', borderColor: 'rgba(255,255,255,0.1)' }}
                    >
                      {BANGLADESH_DISTRICTS.map((d) => (
                        <option key={d} value={d} style={{ background: '#060B14' }}>{d}</option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-white/60 uppercase tracking-wider mb-1.5" htmlFor="resources-risk">
                      Risk Level
                    </label>
                    <select
                      id="resources-risk"
                      value={riskLevel}
                      onChange={(e) => setRiskLevel(e.target.value as typeof riskLevel)}
                      className="w-full px-3 py-2.5 rounded-xl text-sm text-white border focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
                      style={{ background: 'rgba(255,255,255,0.05)', borderColor: 'rgba(255,255,255,0.1)' }}
                    >
                      {['Low', 'Medium', 'High', 'Critical'].map((r) => (
                        <option key={r} value={r} style={{ background: '#060B14' }}>{r}</option>
                      ))}
                    </select>
                  </div>

                  <div className="flex items-end">
                    <button
                      onClick={handleSearch}
                      disabled={recommendMutation.isPending}
                      className="w-full py-2.5 rounded-xl font-semibold text-sm text-white flex items-center justify-center gap-2 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-300 disabled:opacity-60"
                      style={{ background: 'linear-gradient(135deg, #38BDF8, #2DD4BF)' }}
                    >
                      {recommendMutation.isPending ? <Loader2 size={15} className="animate-spin" /> : <Search size={15} />}
                      {recommendMutation.isPending ? 'Loading…' : 'Get Recommendations'}
                    </button>
                  </div>
                </div>
              </GlassCard>
            </motion.div>

            {/* Error */}
            {recommendMutation.isError && (
              <motion.div custom={2} variants={cardVariants} initial="hidden" animate="visible">
                <GlassCard className="p-4 flex items-center gap-3 border-red-400/20">
                  <AlertCircle size={16} className="text-red-400 shrink-0" />
                  <span className="text-red-300 text-sm">{getApiErrorMessage(recommendMutation.error)}</span>
                </GlassCard>
              </motion.div>
            )}

            {/* Results */}
            {recommendMutation.data && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <motion.div custom={2} variants={cardVariants} initial="hidden" animate="visible">
                  <RecommendationCard data={recommendMutation.data} />
                </motion.div>
                <motion.div custom={3} variants={cardVariants} initial="hidden" animate="visible">
                  <HospitalStockCard data={recommendMutation.data} />
                </motion.div>
              </div>
            )}

            {/* Empty state */}
            {!recommendMutation.data && !recommendMutation.isPending && !recommendMutation.isError && (
              <motion.div custom={2} variants={cardVariants} initial="hidden" animate="visible">
                <GlassCard className="p-12 flex flex-col items-center gap-4 text-center">
                  <Building2 size={40} className="text-white/20" />
                  <div>
                    <p className="text-white/50 font-semibold">Select a district and risk level</p>
                    <p className="text-white/30 text-sm mt-1">
                      The AI will recommend hospital resources, bed allocations, and emergency actions.
                    </p>
                  </div>
                </GlassCard>
              </motion.div>
            )}
          </>
        )}

        {tab === 'inventory' && <HospitalInventoryManager />}

        {tab === 'directory' && (
          <motion.div
            key={`directory-${searchParams?.get('district') ?? 'national'}`}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
          >
            <HospitalDirectoryView
              initialDistrict={searchParams?.get('district') ?? undefined}
            />
          </motion.div>
        )}
      </div>
    </AuthGuard>
  );
}
