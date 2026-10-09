'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import type { UserRole } from '@/lib/types';
import { toast } from 'react-hot-toast';

interface AuthGuardProps {
  children: React.ReactNode;
  allowedRoles?: UserRole[];
}

export default function AuthGuard({ children, allowedRoles }: AuthGuardProps) {
  const { user, isLoading, isAuthenticated } = useAuth();
  const router = useRouter();
  // Prevent hydration mismatch: auth state comes from localStorage which
  // doesn't exist on the server. We render nothing until we're client-side.
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!mounted || isLoading) return;

    if (!isAuthenticated) {
      router.replace('/login');
      return;
    }

    if (allowedRoles && user && !allowedRoles.includes(user.role)) {
      toast.error("This section isn't available for your account type.", {
        id: 'role-denied',
        duration: 4000,
      });
      router.replace('/dashboard');
    }
  }, [mounted, isLoading, isAuthenticated, user, allowedRoles, router]);

  // SSR / pre-mount: render nothing to avoid hydration mismatch
  if (!mounted) return null;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="flex flex-col items-center gap-4">
          <div
            className="w-12 h-12 rounded-full border-2 border-blue-500/30 border-t-blue-400 animate-spin"
          />
          <span className="text-white/40 text-sm font-mono">Authenticating...</span>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) return null;
  if (allowedRoles && user && !allowedRoles.includes(user.role)) return null;

  return <>{children}</>;
}
