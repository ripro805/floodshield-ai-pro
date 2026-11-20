'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard, Bell, FileText, Building2, Settings, ChevronLeft, ChevronRight,
  HeartHandshake, ClipboardList, ShieldAlert, AlertCircle, Cpu,
} from 'lucide-react';
import { useState } from 'react';
import { useAuth } from '@/lib/auth';
import type { UserRole } from '@/lib/types';
import { useLanguage } from '@/lib/i18n';

interface NavItem {
  href: string;
  label: string;
  icon: React.ElementType;
  key?: string;
  allowedRoles?: UserRole[];
}

const NAV_ITEMS: NavItem[] = [
  { href: '/dashboard', label: 'District Map', key: 'districtMap', icon: LayoutDashboard },
  { href: '/dashboard/alerts', label: 'Alerts', key: 'alerts', icon: Bell },
  { href: '/dashboard/reports', label: 'Reports', key: 'reports', icon: FileText },
  {
    href: '/dashboard/citizen/reports',
    label: 'Citizen Reports',
    key: 'citizenReports',
    icon: AlertCircle,
  },
  {
    href: '/dashboard/hospital',
    label: 'Hospital Operations',
    key: 'hospitalOps',
    icon: Building2,
    allowedRoles: ['hospital', 'admin'],
  },
  {
    href: '/dashboard/ngo',
    label: 'NGO Relief',
    key: 'ngoRelief',
    icon: HeartHandshake,
    allowedRoles: ['ngo', 'admin'],
  },
  {
    href: '/dashboard/field',
    label: 'Field Operations',
    key: 'fieldOps',
    icon: ClipboardList,
    allowedRoles: ['health_worker', 'admin'],
  },
  {
    href: '/dashboard/government',
    label: 'Emergency Command',
    key: 'emergencyCommand',
    icon: ShieldAlert,
    allowedRoles: ['government', 'admin'],
  },
  {
    href: '/dashboard/resources',
    label: 'Hospital Resources',
    key: 'hospitalResources',
    icon: Building2,
    allowedRoles: ['health_worker', 'hospital', 'ngo', 'government', 'admin'],
  },
  {
    href: '/dashboard/admin/jobs',
    label: 'Automation Jobs',
    key: 'automationJobs',
    icon: Cpu,
  },
  {
    href: '/dashboard/admin',
    label: 'Admin Panel',
    key: 'adminPanel',
    icon: Settings,
    allowedRoles: ['admin'],
  },
];

export default function Sidebar() {
  const { user } = useAuth();
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const { t } = useLanguage();

  const visibleItems = NAV_ITEMS.filter(
    (item) => !item.allowedRoles || (user && item.allowedRoles.includes(user.role))
  );

  return (
    <aside
      className="fixed left-0 top-14 bottom-0 z-40 flex flex-col border-r transition-all duration-300"
      style={{
        width: collapsed ? 64 : 220,
        background: 'rgba(6,11,20,0.8)',
        backdropFilter: 'blur(24px)',
        WebkitBackdropFilter: 'blur(24px)',
        borderColor: 'rgba(255,255,255,0.07)',
      }}
      aria-label="Main navigation"
    >
      {/* Nav items */}
      <nav className="flex-1 overflow-y-auto py-4 px-2">
        {visibleItems.map((item) => {
          const active = pathname === item.href || (item.href !== '/dashboard' && pathname.startsWith(item.href));
          const labelText = t(item.key || item.label.toLowerCase());
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`
                flex items-center gap-3 px-3 py-2.5 mb-1 rounded-xl text-sm font-medium
                transition-all duration-200 group relative
                focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400
                ${active
                  ? 'text-white'
                  : 'text-white/50 hover:text-white hover:bg-white/05'
                }
              `}
              style={active ? {
                background: 'rgba(56,189,248,0.12)',
                boxShadow: '0 0 12px rgba(56,189,248,0.15)',
              } : {}}
              aria-current={active ? 'page' : undefined}
              title={collapsed ? labelText : undefined}
            >
              {/* Active indicator */}
              {active && (
                <span
                  className="absolute left-0 top-2 bottom-2 w-0.5 rounded-full bg-blue-400"
                  style={{ boxShadow: '0 0 8px #38BDF8' }}
                />
              )}
              <item.icon
                size={18}
                className={active ? 'text-blue-400' : 'text-white/40 group-hover:text-white/70 transition'}
              />
              {!collapsed && (
                <span className="truncate">{labelText}</span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Collapse toggle */}
      <button
        onClick={() => setCollapsed((c) => !c)}
        className="mx-2 mb-4 flex items-center justify-center h-9 rounded-xl text-white/30 hover:text-white/60 hover:bg-white/05 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
        aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      >
        {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
      </button>
    </aside>
  );
}
