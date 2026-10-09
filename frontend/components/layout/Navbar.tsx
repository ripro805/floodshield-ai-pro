'use client';

import Link from 'next/link';
import { Bell, LogOut, Shield } from 'lucide-react';
import { useAuth } from '@/lib/auth';
import { RISK_COLORS } from '@/lib/types';
import { useLanguage } from '@/lib/i18n';
import PromoteToAdminButton from '@/components/auth/PromoteToAdminButton';
import DemoteToCitizenButton from '@/components/auth/DemoteToCitizenButton';

const roleBadgeStyle: Record<string, string> = {
  admin: 'text-red-400 border-red-400/40',
  government: 'text-purple-400 border-purple-400/40',
  hospital: 'text-blue-400 border-blue-400/40',
  health_worker: 'text-teal-400 border-teal-400/40',
  ngo: 'text-amber-400 border-amber-400/40',
  citizen: 'text-white/50 border-white/20',
};

export default function Navbar() {
  const { user, logout } = useAuth();
  const badgeClass = roleBadgeStyle[user?.role ?? 'citizen'];
  const { language, setLanguage, t } = useLanguage();

  return (
    <nav
      className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-6 py-3 border-b"
      style={{
        background: 'rgba(6,11,20,0.85)',
        backdropFilter: 'blur(24px)',
        WebkitBackdropFilter: 'blur(24px)',
        borderColor: 'rgba(255,255,255,0.08)',
      }}
      aria-label="FloodShield AI navigation"
    >
      {/* Logo */}
      <Link href="/" className="flex items-center gap-2.5 group focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 rounded-lg px-1">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-teal-400 flex items-center justify-center">
          <Shield size={16} className="text-white" />
        </div>
        <div className="leading-none">
          <span className="font-bold text-white tracking-tight text-sm" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
            {t('floodShield')}
          </span>
          <span className="text-blue-400 font-bold text-sm" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
            {' '}AI
          </span>
        </div>
      </Link>

      {/* Right side */}
      <div className="flex items-center gap-4">
        <button onClick={() => setLanguage(language === 'en' ? 'bn' : 'en')} className="text-xs px-2 py-1 rounded border border-white/10 text-white/60 hover:text-white" aria-label="Toggle interface language">
          {language === 'en' ? 'বাংলা' : 'EN'}
        </button>
        {user && (
          <>
            {/* User info */}
            <div className="hidden sm:flex flex-col items-end">
              <span className="text-white text-sm font-medium leading-tight">{user.full_name}</span>
              <span className={`text-xs capitalize border px-2 py-0.5 rounded-full font-mono ${badgeClass}`}>
                {user.role.replace('_', ' ')}
              </span>
            </div>

            {/* One-time admin bootstrap (only shown when usable) */}
            <PromoteToAdminButton />

            {/* Self-demote: only renders for admins */}
            <DemoteToCitizenButton />

            {/* Alerts bell */}
            <Link
              href="/dashboard/alerts"
              className="relative p-2 rounded-lg text-white/60 hover:text-white hover:bg-white/05 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
              aria-label="View alerts"
            >
              <Bell size={18} />
              <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-red-400 animate-pulse" />
            </Link>

            {/* Logout */}
            <button
              onClick={logout}
              className="p-2 rounded-lg text-white/50 hover:text-red-400 hover:bg-red-400/10 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-red-400"
              aria-label={t('logout')}
            >
              <LogOut size={18} />
            </button>
          </>
        )}

        {!user && (
          <Link
            href="/login"
            className="px-4 py-1.5 rounded-lg text-sm font-semibold bg-blue-500 hover:bg-blue-400 text-white transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-300"
          >
            Sign In
          </Link>
        )}
      </div>
    </nav>
  );
}
