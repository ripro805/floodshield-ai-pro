'use client';

import AuthGuard from '@/components/layout/AuthGuard';
import Navbar from '@/components/layout/Navbar';
import Sidebar from '@/components/layout/Sidebar';
import ChatbotWidget from '@/components/chat/ChatbotWidget';
import { LanguageProvider } from '@/lib/i18n';

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <LanguageProvider>
      <AuthGuard>
      <Navbar />
      <Sidebar />
      <div
        className="min-h-screen pt-14 transition-all duration-300"
        style={{ paddingLeft: 220 }}
        id="dashboard-content"
      >
        <main className="p-6">{children}</main>
      </div>
        <ChatbotWidget />
      </AuthGuard>
    </LanguageProvider>
  );
}
