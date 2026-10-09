/**
 * Small helpers for the Hospital Directory components.
 *
 * Kept separate from the theme file so the React components don't
 * import non-component code unless they need it.
 */
import { DISTRICT_CENTROIDS, CAPACITY_COLORS } from './hospitalTheme';
import type { CapacityStatus } from '@/lib/types';

/** Fallback origin for a district (used when the user hasn't shared
 *  their location).  Returns the canonical centroid. */
export function districtCentroid(district: string): { lat: number; lng: number } | null {
  return DISTRICT_CENTROIDS[district] ?? null;
}

export function statusColor(status: CapacityStatus): string {
  return CAPACITY_COLORS[status]?.text ?? '#CBD5E1';
}
