'use client';

import { useDistrictBangla } from '@/hooks/useDistrictBangla';
import { Languages } from 'lucide-react';

interface DistrictNameProps {
  en: string | null | undefined;
  /** Show the Bangla subtitle under the English name. Default: true. */
  showBangla?: boolean;
  /** Render size variant. */
  size?: 'sm' | 'md' | 'lg';
  /** Optional className for the wrapping <div>. */
  className?: string;
  /** When true, force-hide the Bangla subtitle even if the lookup is available. */
  hideBanglaIfMissing?: boolean;
  /** Layout: "stack" puts English on top, Bangla under; "inline" puts them side by side. */
  layout?: 'stack' | 'inline';
}

/**
 * Renders a district name with an optional Bangla subtitle.
 *
 *   <DistrictName en="Feni" />   → "Feni" with "ফেনী" under it
 *
 * The Bangla lookup is fetched once and cached (see useDistrictBangla).
 * If the district isn't in the table (e.g. misspelled), only the
 * English name is rendered.
 */
export default function DistrictName({
  en,
  showBangla = true,
  size = 'md',
  className,
  hideBanglaIfMissing = false,
  layout = 'stack',
}: DistrictNameProps) {
  const { bn } = useDistrictBangla();
  const bangla = bn(en);
  const showBn = showBangla && (!hideBanglaIfMissing || bangla !== null);

  const fontSize = size === 'lg' ? 22 : size === 'sm' ? 12 : 15;
  const subFontSize = size === 'lg' ? 14 : size === 'sm' ? 10 : 12;

  if (!en) return <span className={className}>—</span>;

  if (layout === 'inline' && showBn && bangla) {
    return (
      <span className={className} style={{ display: 'inline-flex', alignItems: 'baseline', gap: 6 }}>
        <span style={{ fontWeight: 600, fontSize, color: '#fff' }}>{en}</span>
        <span
          style={{
            fontSize: subFontSize,
            color: 'rgba(255,255,255,0.55)',
            fontFamily: '"Noto Sans Bengali", "Hind Siliguri", sans-serif',
          }}
        >
          ({bangla})
        </span>
      </span>
    );
  }

  return (
    <div className={className} style={{ display: 'inline-block' }}>
      <div style={{ fontWeight: 600, fontSize, color: '#fff', lineHeight: 1.2 }}>{en}</div>
      {showBn && bangla && (
        <div
          style={{
            color: 'rgba(255,255,255,0.55)',
            fontSize: subFontSize,
            marginTop: 2,
            lineHeight: 1.2,
            fontFamily: '"Noto Sans Bengali", "Hind Siliguri", sans-serif',
            display: 'inline-flex',
            alignItems: 'center',
            gap: 4,
          }}
          title="Bangla name"
        >
          <Languages size={size === 'sm' ? 9 : 11} className="opacity-50" />
          <span>{bangla}</span>
        </div>
      )}
    </div>
  );
}
