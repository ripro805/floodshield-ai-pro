import type { Metadata } from 'next';
import Link from 'next/link';
import Image from 'next/image';
import dynamic from 'next/dynamic';
import { motion } from 'framer-motion';
import { Shield, Satellite, Activity, Map, ArrowRight, Zap } from 'lucide-react';

export const metadata: Metadata = {
  title: 'FloodShield AI — Flood & Disease Early Warning for Bangladesh',
  description:
    'AI-powered flood and disease outbreak early warning platform for Bangladesh. Predicts floods and outbreaks 7–14 days in advance using 6 ML models and real Sentinel-1 satellite data.',
};

const BangladeshGlobe = dynamic(() => import('@/components/three/BangladeshGlobe'), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full flex items-center justify-center">
      <div className="w-16 h-16 rounded-full border-2 border-blue-500/30 border-t-blue-400 animate-spin" />
    </div>
  ),
});

const FEATURES = [
  {
    icon: Activity,
    color: '#2DD4BF',
    title: 'Flood Prediction',
    desc: 'ML Model 1 — binary flood probability from river level, rainfall, humidity, and elevation. Updated live with OpenWeatherMap data.',
  },
  {
    icon: Shield,
    color: '#FBBF24',
    title: 'Disease Outbreak',
    desc: 'Models 2 & 5 — predicts cholera, diarrhea, typhoid, and dengue outbreak risk 7–14 days after a flood event, with composite risk scoring.',
  },
  {
    icon: Satellite,
    color: '#38BDF8',
    title: 'Satellite Coverage',
    desc: 'Model 4 — real Sentinel-1 SAR satellite imagery processed to detect actual flood extent on the ground, independent of weather forecasts.',
  },
  {
    icon: Map,
    color: '#FB923C',
    title: 'District-Level Maps',
    desc: 'Interactive Leaflet map of all 64 Bangladesh districts, color-coded by live risk level with click-through to detailed district assessments.',
  },
];

const STATS = [
  { value: '6', label: 'ML Models' },
  { value: '64', label: 'Districts' },
  { value: '14', label: 'Day Forecast' },
  { value: '100%', label: 'Open Source' },
];

export default function LandingPage() {
  return (
    <main className="min-h-screen" style={{ fontFamily: 'Inter, sans-serif' }}>
      {/* ── Top Header / Navbar on Landing Page ── */}
      <header className="fixed top-0 left-0 right-0 z-40 flex items-center justify-between px-6 lg:px-16 py-3.5 border-b border-white/05 bg-[#060B14]/85 backdrop-blur-xl">
        <Link href="/" className="flex items-center gap-3 group">
          <div
            className="relative w-9 h-9 rounded-xl overflow-hidden flex items-center justify-center p-0.5 border border-cyan-400/20 group-hover:border-cyan-400/60 transition-all duration-300"
            style={{ background: 'rgba(255, 255, 255, 0.04)', boxShadow: '0 0 16px rgba(56, 189, 248, 0.2)' }}
          >
            <Image
              src="/logo.png"
              alt="FloodShield AI Logo"
              width={34}
              height={34}
              className="object-contain transition-transform duration-300 group-hover:scale-110"
              priority
            />
          </div>
          <span className="font-black text-lg tracking-tight text-white" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
            FloodShield<span className="text-cyan-400"> AI</span> Pro
          </span>
        </Link>
        <div className="flex items-center gap-3">
          <Link
            href="/login"
            className="px-4 py-1.5 text-sm font-semibold text-white/70 hover:text-white transition"
          >
            Sign In
          </Link>
          <Link
            href="/dashboard"
            className="px-4 py-1.5 text-sm font-semibold text-white rounded-xl transition"
            style={{
              background: 'linear-gradient(135deg, #38BDF8, #2DD4BF)',
              boxShadow: '0 0 16px rgba(56,189,248,0.3)',
            }}
          >
            Live Platform
          </Link>
        </div>
      </header>

      {/* ── Hero ── */}
      <section className="relative flex flex-col lg:flex-row items-center min-h-screen pt-24 px-6 lg:px-16 gap-8 overflow-hidden">
        {/* Text */}
        <div className="flex-1 max-w-2xl z-10">
          <div
            className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border text-xs font-semibold uppercase tracking-widest mb-6"
            style={{ borderColor: 'rgba(56,189,248,0.4)', color: '#38BDF8', background: 'rgba(56,189,248,0.08)' }}
          >
            <Zap size={12} />
            Life-Safety Early Warning System
          </div>

          <h1
            className="text-5xl lg:text-7xl font-black leading-none tracking-tight text-white mb-6"
            style={{ fontFamily: 'Space Grotesk, sans-serif' }}
          >
            Predict Floods
            <br />
            <span
              style={{
                background: 'linear-gradient(90deg, #38BDF8, #2DD4BF)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
              }}
            >
              Before They Strike
            </span>
          </h1>

          <p className="text-lg text-white/60 leading-relaxed mb-8 max-w-lg">
            FloodShield AI gives government agencies, hospitals, and NGOs a
            7–14 day head start on flood and disease outbreaks across all 64
            districts of Bangladesh.
          </p>

          <div className="flex flex-wrap gap-4">
            <Link
              href="/dashboard"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-xl font-semibold text-white transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-300"
              style={{
                background: 'linear-gradient(135deg, #38BDF8, #2DD4BF)',
                boxShadow: '0 0 24px rgba(56,189,248,0.35)',
              }}
            >
              View Dashboard <ArrowRight size={16} />
            </Link>
            <Link
              href="/signup"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-xl font-semibold text-white/80 border border-white/15 hover:border-white/30 hover:text-white transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
              style={{ background: 'rgba(255,255,255,0.05)' }}
            >
              Create Account
            </Link>
          </div>
        </div>

        {/* 3D Globe */}
        <div className="flex-1 h-[420px] lg:h-[600px] w-full max-w-2xl">
          <BangladeshGlobe />
        </div>
      </section>

      {/* ── Stats strip ── */}
      <section className="py-8 px-6 border-y" style={{ borderColor: 'rgba(255,255,255,0.06)', background: 'rgba(255,255,255,0.02)' }}>
        <div className="max-w-5xl mx-auto grid grid-cols-2 sm:grid-cols-4 gap-6">
          {STATS.map((s) => (
            <div key={s.label} className="text-center">
              <div
                className="text-4xl font-black font-mono"
                style={{
                  fontFamily: 'JetBrains Mono, monospace',
                  background: 'linear-gradient(135deg, #38BDF8, #2DD4BF)',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                }}
              >
                {s.value}
              </div>
              <div className="text-white/50 text-sm mt-1">{s.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ── Features ── */}
      <section className="py-20 px-6 max-w-6xl mx-auto">
        <h2
          className="text-3xl font-black text-white text-center mb-2"
          style={{ fontFamily: 'Space Grotesk, sans-serif' }}
        >
          Six AI Models. One Platform.
        </h2>
        <p className="text-white/50 text-center mb-12">
          Built for government agencies, hospitals, NGOs, health workers, and citizens.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
          {FEATURES.map((f, i) => (
            <div
              key={i}
              className="rounded-2xl p-6 border transition-all duration-300 hover:-translate-y-1"
              style={{
                background: 'rgba(255,255,255,0.04)',
                backdropFilter: 'blur(16px)',
                borderColor: 'rgba(255,255,255,0.09)',
              }}
            >
              <div
                className="w-10 h-10 rounded-xl flex items-center justify-center mb-4"
                style={{ background: `${f.color}18` }}
              >
                <f.icon size={18} style={{ color: f.color }} />
              </div>
              <h3 className="text-white font-bold text-lg mb-2" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
                {f.title}
              </h3>
              <p className="text-white/55 text-sm leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── CTA ── */}
      <section className="py-20 px-6 text-center">
        <div
          className="max-w-2xl mx-auto rounded-3xl p-12 border"
          style={{
            background: 'rgba(56,189,248,0.06)',
            backdropFilter: 'blur(24px)',
            borderColor: 'rgba(56,189,248,0.2)',
            boxShadow: '0 0 48px rgba(56,189,248,0.08)',
          }}
        >
          <h2 className="text-3xl font-black text-white mb-4" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
            Ready to protect lives?
          </h2>
          <p className="text-white/60 mb-8">
            Create a free account — citizen, health worker, hospital, or government agency.
          </p>
          <div className="flex flex-wrap gap-4 justify-center">
            <Link
              href="/signup"
              className="px-8 py-3 rounded-xl font-bold text-white transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-300"
              style={{ background: 'linear-gradient(135deg, #38BDF8, #2DD4BF)', boxShadow: '0 0 24px rgba(56,189,248,0.35)' }}
            >
              Get Started Free
            </Link>
            <Link
              href="/login"
              className="px-8 py-3 rounded-xl font-bold text-white/70 border border-white/15 hover:text-white hover:border-white/30 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
              style={{ background: 'rgba(255,255,255,0.04)' }}
            >
              Sign In
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}
