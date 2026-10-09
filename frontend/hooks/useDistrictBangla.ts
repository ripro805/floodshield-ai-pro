'use client';

import { useEffect, useState, useMemo } from 'react';
import { loadDistrictBanglaMap, lookupBangla } from '@/lib/api';

/**
 * Shared hook used by every UI that renders a district name.  Loads the
 * EN -> BN table from /api/locations/bangla on first call, caches it
 * module-wide (see lib/api.ts), and returns:
 *   - banglaMap : the lookup Map (case-insensitive)
 *   - bn(en)    : helper to fetch the Bangla name (or null)
 *   - loading   : true until the first /api/locations/bangla resolves
 *   - error     : any fetch error (silently swallowed; UI just hides
 *                 Bangla subtitles if the lookup failed)
 *
 * Components that already showed the Bangla subtitle (Data Status tab)
 * can adopt this hook too for consistency; behaviour is identical.
 */
export function useDistrictBangla() {
  const [banglaMap, setBanglaMap] = useState<Map<string, string> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    loadDistrictBanglaMap()
      .then((m) => { if (!cancelled) setBanglaMap(m); })
      .catch((e) => { if (!cancelled) { setBanglaMap(new Map()); setError(String(e?.message ?? e)); } });
    return () => { cancelled = true; };
  }, []);

  const bn = useMemo(
    () => (en: string | null | undefined): string | null => {
      if (!en) return null;
      return lookupBangla(banglaMap, en);
    },
    [banglaMap]
  );

  return { banglaMap, bn, loading: banglaMap === null && !error, error };
}
