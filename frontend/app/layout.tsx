import type { Metadata, Viewport } from 'next';
import { Providers } from '@/components/layout/Providers';
import './globals.css';
import 'leaflet/dist/leaflet.css';

export const metadata: Metadata = {
  title: 'FloodShield AI — Flood & Disease Early Warning Platform',
  description:
    'AI-powered flood and disease outbreak early warning platform for Bangladesh. Predicts floods and post-flood disease outbreaks 7–14 days in advance using 6 trained ML models and real Sentinel-1 satellite data.',
  keywords: [
    'flood prediction',
    'disease outbreak',
    'early warning',
    'Bangladesh',
    'AI',
    'machine learning',
    'disaster management',
  ],
  authors: [{ name: 'FloodShield AI Team' }],
  openGraph: {
    title: 'FloodShield AI',
    description:
      'Life-saving AI for flood and disease early warning in Bangladesh',
    type: 'website',
    locale: 'en_US',
  },
  robots: 'index, follow',
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 5,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <meta charSet="utf-8" />
        <meta name="theme-color" content="#060B14" />
        <meta name="description" content={metadata.description as string} />
      </head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
