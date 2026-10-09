/**
 * Shared theme + helpers for the Hospital Directory components.
 *
 * Imported by both HospitalDirectoryView (the new Directory tab) and
 * DistrictNearestHospitals (the District Detail card).  Keeping the
 * theme + the centroid helper here avoids a circular import and
 * lets the District Detail page drop in just the card.
 */
import { BANGLADESH_DISTRICTS } from '@/lib/types';
import type { CapacityStatus } from '@/lib/types';

/** Loose per-district centroids (lat, lng).  Same numbers the
 * seeder uses, so a District view's "nearest hospital" suggestion
 * matches the seeder's bbox placement.  Used as a fallback origin
 * when the user hasn't shared their location. */
export const DISTRICT_CENTROIDS: Record<string, { lat: number; lng: number }> = {
  Bagerhat: { lat: 22.65, lng: 89.7 },
  Bandarban: { lat: 22.20, lng: 92.35 },
  Barguna: { lat: 22.10, lng: 90.20 },
  Barishal: { lat: 22.75, lng: 90.50 },
  Bhola: { lat: 22.45, lng: 90.75 },
  Bogura: { lat: 24.95, lng: 89.30 },
  Brahmanbaria: { lat: 23.95, lng: 91.10 },
  Chandpur: { lat: 23.35, lng: 90.80 },
  Chapainawabganj: { lat: 24.75, lng: 88.30 },
  Chattogram: { lat: 22.45, lng: 91.95 },
  Chuadanga: { lat: 23.65, lng: 88.95 },
  "Cox's Bazar": { lat: 21.45, lng: 92.05 },
  Cumilla: { lat: 23.65, lng: 91.00 },
  Dhaka: { lat: 23.80, lng: 90.40 },
  Dinajpur: { lat: 25.60, lng: 88.65 },
  Faridpur: { lat: 23.45, lng: 89.75 },
  Feni: { lat: 23.05, lng: 91.40 },
  Gaibandha: { lat: 25.40, lng: 89.55 },
  Gazipur: { lat: 24.10, lng: 90.40 },
  Gopalganj: { lat: 23.15, lng: 89.90 },
  Habiganj: { lat: 24.40, lng: 91.40 },
  Jamalpur: { lat: 24.90, lng: 89.90 },
  Jashore: { lat: 23.15, lng: 89.20 },
  Jhalokati: { lat: 22.65, lng: 90.20 },
  Jhenaidah: { lat: 23.55, lng: 89.10 },
  Joypurhat: { lat: 25.10, lng: 89.05 },
  Khagrachhari: { lat: 23.30, lng: 92.05 },
  Khulna: { lat: 22.80, lng: 89.55 },
  Kishoreganj: { lat: 24.45, lng: 90.90 },
  Kurigram: { lat: 26.00, lng: 89.85 },
  Kushtia: { lat: 23.90, lng: 89.10 },
  Lakshmipur: { lat: 22.85, lng: 90.80 },
  Lalmonirhat: { lat: 26.05, lng: 89.30 },
  Madaripur: { lat: 23.20, lng: 90.15 },
  Magura: { lat: 23.50, lng: 89.50 },
  Manikganj: { lat: 23.85, lng: 90.00 },
  Meherpur: { lat: 23.85, lng: 88.80 },
  Moulvibazar: { lat: 24.45, lng: 91.85 },
  Munshiganj: { lat: 23.55, lng: 90.55 },
  Mymensingh: { lat: 24.75, lng: 90.45 },
  Naogaon: { lat: 24.90, lng: 88.75 },
  Narail: { lat: 23.15, lng: 89.60 },
  Narayanganj: { lat: 23.65, lng: 90.55 },
  Narsingdi: { lat: 24.00, lng: 90.85 },
  Natore: { lat: 24.35, lng: 89.15 },
  Netrokona: { lat: 24.80, lng: 90.80 },
  Nilphamari: { lat: 26.05, lng: 89.05 },
  Noakhali: { lat: 22.55, lng: 91.15 },
  Pabna: { lat: 24.00, lng: 89.50 },
  Panchagarh: { lat: 26.30, lng: 88.70 },
  Patuakhali: { lat: 22.25, lng: 90.35 },
  Pirojpur: { lat: 22.70, lng: 90.05 },
  Rajbari: { lat: 23.65, lng: 89.60 },
  Rajshahi: { lat: 24.45, lng: 88.70 },
  Rangamati: { lat: 22.95, lng: 92.15 },
  Rangpur: { lat: 25.60, lng: 89.30 },
  Satkhira: { lat: 22.35, lng: 89.10 },
  Shariatpur: { lat: 23.30, lng: 90.30 },
  Sherpur: { lat: 25.10, lng: 90.15 },
  Sirajganj: { lat: 24.40, lng: 89.75 },
  Sunamganj: { lat: 25.05, lng: 91.30 },
  Sylhet: { lat: 25.00, lng: 91.85 },
  Tangail: { lat: 24.45, lng: 89.90 },
  Thakurgaon: { lat: 26.05, lng: 88.50 },
};

export const CAPACITY_COLORS: Record<CapacityStatus, { bg: string; text: string }> = {
  Available: { bg: 'rgba(45,212,191,0.18)', text: '#5EEAD4' },
  Limited: { bg: 'rgba(251,191,36,0.18)', text: '#FCD34D' },
  Full: { bg: 'rgba(244,63,94,0.18)', text: '#FDA4AF' },
  Unknown: { bg: 'rgba(148,163,184,0.18)', text: '#CBD5E1' },
};

export { BANGLADESH_DISTRICTS };
