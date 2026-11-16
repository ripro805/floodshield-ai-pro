import type { Metadata } from 'next';
import DocsClient from './DocsClient';

export const metadata: Metadata = {
  title: 'FloodShield AI Pro — Live Pitch Deck & Technical Documentation',
  description:
    'Live Y Combinator–style pitch deck, enterprise technical architecture, data-flow pipelines, and API documentation for FloodShield AI Pro.',
  openGraph: {
    title: 'FloodShield AI Pro — Pitch Deck & Documentation',
    description: 'Predict Floods. Prevent Disease. Empower Bangladesh with 6 ML models and Sentinel-1 SAR intelligence.',
    type: 'website',
  },
};

export default function DocsPage() {
  return <DocsClient />;
}
