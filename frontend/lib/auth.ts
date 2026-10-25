import { useQuery } from '@tanstack/react-query';
import { getMe } from './api';
import type { UserOut } from './types';

const TOKEN_KEY = 'floodshield_token';

// ─── Token storage (SSR-safe) ─────────────────────────────────────────────────

export function saveToken(token: string): void {
  if (typeof window !== 'undefined') {
    localStorage.setItem(TOKEN_KEY, token);
  }
}

export function getToken(): string | null {
  if (typeof window !== 'undefined') {
    return localStorage.getItem(TOKEN_KEY);
  }
  return null;
}

/** Persist a new token and invalidate the cached current-user query so the
 *  next useAuth() reads the fresh role. */
export function setAuthToken(token: string): void {
  saveToken(token);
}

export function clearToken(): void {
  if (typeof window !== 'undefined') {
    localStorage.removeItem(TOKEN_KEY);
  }
}

// ─── Current user hook ────────────────────────────────────────────────────────

export function useCurrentUser() {
  return useQuery<UserOut>({
    queryKey: ['currentUser'],
    queryFn: getMe,
    enabled: !!getToken(),
    staleTime: 5 * 60 * 1000,   // 5 min
    retry: false,                // don't retry on 401 — interceptor will redirect
    refetchOnWindowFocus: true,
  });
}

// ─── Auth hook ────────────────────────────────────────────────────────────────

import { useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';

export function useAuth() {
  const queryClient = useQueryClient();
  const { data: user, isLoading } = useCurrentUser();

  const logout = useCallback(() => {
    clearToken();
    queryClient.clear();
    window.location.href = '/login';
  }, [queryClient]);

  const refreshUser = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['currentUser'] });
    return queryClient.refetchQueries({ queryKey: ['currentUser'] });
  }, [queryClient]);

  return {
    user: user ?? null,
    isLoading,
    isAuthenticated: !!user,
    logout,
    refreshUser,
  };
}
