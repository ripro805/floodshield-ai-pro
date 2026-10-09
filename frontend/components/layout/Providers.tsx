'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactNode, useState } from 'react';
import { Toaster } from 'react-hot-toast';
import dynamic from 'next/dynamic';

// Lazy load particle background to avoid SSR issues
const ParticleBackground = dynamic(() => import('@/components/three/ParticleBackground'), {
  ssr: false,
});

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 1000 * 60 * 5, // 5 minutes
            gcTime: 1000 * 60 * 10, // 10 minutes (formerly cacheTime)
            retry: 1,
            refetchOnWindowFocus: false,
          },
          mutations: {
            retry: 1,
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      <ParticleBackground />
      <div className="relative z-10">
        {children}
      </div>
      <Toaster
        position="bottom-right"
        reverseOrder={false}
        gutter={8}
        toastOptions={{
          duration: 4000,
          style: {
            background: 'rgba(6, 11, 20, 0.92)',
            color: '#fff',
            border: '1px solid rgba(255, 255, 255, 0.12)',
            borderRadius: '12px',
            backdropFilter: 'blur(24px)',
            boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4)',
            fontFamily: 'Inter, system-ui, sans-serif',
            padding: '12px 16px',
            fontSize: '14px',
          },
          success: {
            iconTheme: {
              primary: '#2DD4BF',
              secondary: 'rgba(6, 11, 20, 0.92)',
            },
          },
          error: {
            iconTheme: {
              primary: '#F43F5E',
              secondary: 'rgba(6, 11, 20, 0.92)',
            },
            duration: 5000,
          },
        }}
      />
    </QueryClientProvider>
  );
}
