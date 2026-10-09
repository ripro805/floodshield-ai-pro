'use client';

/**
 * HospitalEditModal -- the ops-side editor for a single hospital
 * record.  Mirrors the three field groups the backend enforces:
 *
 *   1. Inventory  -- beds, doctors, nurses, ORS/IV/AB stock,
 *                    occupancy_percent.  Any ops role.
 *   2. Ops metadata -- phone, address, upazila, beds_occupied.
 *                    Any ops role.
 *   3. Admin metadata -- name, hospital_type, lat, lng.  Admin only.
 *                    Hidden for non-admins (the backend would 422
 *                    anyway, but the UI doesn't even let you type).
 *
 * The modal sends ONLY the fields the user actually changed (using
 * Pydantic's `exclude_unset=True` on the server), so a "Save"
 * click that didn't touch anything is a 422 + a friendly error.
 *
 * On success we invalidate the directory queries so the updated row
 * is visible in the list and the new rollup (which factors
 * beds_occupied into occupancy) propagates to the district summary.
 */
import { useEffect, useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Loader2, X, AlertCircle, CheckCircle2, Save, MapPin,
  Phone, FileText, Activity, Shield, Stethoscope,
} from 'lucide-react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  patchHospital, type HospitalPatchPayload,
} from '@/lib/api';
import { getApiErrorMessage } from '@/lib/api';
import type { HospitalOperational } from '@/lib/types';
import { useAuth } from '@/lib/auth';

interface HospitalEditModalProps {
  hospital: HospitalOperational;
  open: boolean;
  onClose: () => void;
}

interface FormState {
  // Inventory
  beds: string;
  doctors: string;
  nurses: string;
  ors_stock: string;
  iv_saline_stock: string;
  antibiotics_stock: string;
  occupancy_percent: string;
  // Ops metadata
  phone: string;
  address: string;
  upazila: string;
  beds_occupied: string;
  // Admin metadata
  name: string;
  hospital_type: string;
  latitude: string;
  longitude: string;
}

function toForm(h: HospitalOperational): FormState {
  return {
    beds: String(h.beds_total ?? 0),
    doctors: String(h.doctors ?? 0),
    nurses: String(h.nurses ?? 0),
    ors_stock: String(h.ors_stock ?? 0),
    iv_saline_stock: String(h.iv_saline_stock ?? 0),
    antibiotics_stock: String(h.antibiotics_stock ?? 0),
    occupancy_percent: String(h.occupancy_percent ?? 0),
    phone: h.phone ?? '',
    address: h.address ?? '',
    upazila: h.upazila ?? '',
    beds_occupied: h.beds_occupied == null ? '' : String(h.beds_occupied),
    name: h.name ?? '',
    hospital_type: h.hospital_type ?? '',
    latitude: h.latitude == null ? '' : String(h.latitude),
    longitude: h.longitude == null ? '' : String(h.longitude),
  };
}

export default function HospitalEditModal({ hospital, open, onClose }: HospitalEditModalProps) {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const queryClient = useQueryClient();

  const [form, setForm] = useState<FormState>(() => toForm(hospital));
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Re-seed the form when a different hospital is opened.
  useEffect(() => {
    if (open) {
      setForm(toForm(hospital));
      setError(null);
      setSuccess(false);
    }
  }, [hospital, open]);

  const mutation = useMutation({
    mutationFn: (payload: HospitalPatchPayload) => patchHospital(hospital.id, payload),
    onSuccess: (updated) => {
      setSuccess(true);
      // Refresh every directory query so the change is visible in
      // the list, the single-detail card, the district summary, and
      // the map.
      queryClient.invalidateQueries({ queryKey: ['districts-summary'] });
      queryClient.invalidateQueries({ queryKey: ['hospitals'] });
      queryClient.setQueryData(['hospital', updated.id], updated);
    },
    onError: (e) => setError(getApiErrorMessage(e)),
  });

  // Build the patch payload: only fields the user actually changed
  // (compared to the values the modal was opened with).
  const computePayload = (): HospitalPatchPayload => {
    const orig = toForm(hospital);
    const out: HospitalPatchPayload = {};
    const map: Array<[keyof FormState, keyof HospitalPatchPayload, (s: string) => unknown]> = [
      ['beds', 'beds', (s) => parseInt(s, 10)],
      ['doctors', 'doctors', (s) => parseInt(s, 10)],
      ['nurses', 'nurses', (s) => parseInt(s, 10)],
      ['ors_stock', 'ors_stock', (s) => parseInt(s, 10)],
      ['iv_saline_stock', 'iv_saline_stock', (s) => parseInt(s, 10)],
      ['antibiotics_stock', 'antibiotics_stock', (s) => parseInt(s, 10)],
      ['occupancy_percent', 'occupancy_percent', (s) => parseFloat(s)],
      // Ops metadata -- empty string means "clear"
      ['phone', 'phone', (s) => (s.trim() === '' ? null : s.trim())],
      ['address', 'address', (s) => (s.trim() === '' ? null : s.trim())],
      ['upazila', 'upazila', (s) => (s.trim() === '' ? null : s.trim())],
      ['beds_occupied', 'beds_occupied', (s) => (s.trim() === '' ? null : parseInt(s, 10))],
      // Admin metadata
      ['name', 'name', (s) => s.trim()],
      ['hospital_type', 'hospital_type', (s) => (s.trim() === '' ? null : s.trim())],
      ['latitude', 'latitude', (s) => (s.trim() === '' ? null : parseFloat(s))],
      ['longitude', 'longitude', (s) => (s.trim() === '' ? null : parseFloat(s))],
    ];
    for (const [formKey, payloadKey, parse] of map) {
      const next = form[formKey];
      if (next !== orig[formKey]) {
        // @ts-expect-error -- runtime-assigned key
        out[payloadKey] = parse(next);
      }
    }
    return out;
  };

  const dirty = useMemo(() => Object.keys(computePayload()).length > 0, [form, hospital]);

  const submit = () => {
    setError(null);
    setSuccess(false);
    const payload = computePayload();
    if (Object.keys(payload).length === 0) {
      setError('No changes to save.');
      return;
    }
    mutation.mutate(payload);
  };

  const set = (k: keyof FormState) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(6px)' }}
          onClick={onClose}
        >
          <motion.div
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 20, opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-2xl max-h-[90vh] overflow-auto rounded-2xl border p-6"
            style={{
              background: 'linear-gradient(180deg, rgba(15,23,42,0.96), rgba(7,12,24,0.96))',
              borderColor: 'rgba(255,255,255,0.08)',
            }}
          >
            {/* Header */}
            <div className="flex items-center justify-between mb-2">
              <div>
                <h3 className="text-lg font-bold text-white flex items-center gap-2">
                  <Save size={16} className="text-blue-300" /> Edit hospital
                </h3>
                <p className="text-white/50 text-xs mt-0.5">{hospital.name} · {hospital.district}</p>
              </div>
              <button
                onClick={onClose}
                className="w-8 h-8 rounded-lg flex items-center justify-center text-white/60 hover:text-white hover:bg-white/5"
                aria-label="Close"
              >
                <X size={16} />
              </button>
            </div>
            <p className="text-white/40 text-[11px] mb-4">
              {isAdmin
                ? 'Admin: every field below is editable. Structural changes (name, type, coordinates) are recorded against your account.'
                : 'Operational fields are editable. Name, type, and coordinates require an admin.'}
            </p>

            {/* Inventory group */}
            <Group icon={Activity} title="Inventory" subtitle="Capacity and stock counts">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                <NumField label="Beds"     value={form.beds}            onChange={set('beds')} />
                <NumField label="Doctors"  value={form.doctors}         onChange={set('doctors')} />
                <NumField label="Nurses"   value={form.nurses}          onChange={set('nurses')} />
                <NumField label="Beds occupied (live)" value={form.beds_occupied} onChange={set('beds_occupied')} hint="Empty = unknown" />
                <NumField label="ORS stock"     value={form.ors_stock}          onChange={set('ors_stock')} />
                <NumField label="IV saline"     value={form.iv_saline_stock}    onChange={set('iv_saline_stock')} />
                <NumField label="Antibiotics"   value={form.antibiotics_stock}  onChange={set('antibiotics_stock')} />
                <NumField label="Occupancy %"   value={form.occupancy_percent}  onChange={set('occupancy_percent')} step="0.1" min="0" max="100" />
              </div>
            </Group>

            {/* Ops metadata group */}
            <Group icon={Phone} title="Contact & address" subtitle="Phone, upazila, and address line">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <TextField label="Phone" value={form.phone} onChange={set('phone')} placeholder="+880-..." />
                <TextField label="Upazila" value={form.upazila} onChange={set('upazila')} placeholder="Sadar" />
              </div>
              <TextField
                label="Address"
                value={form.address}
                onChange={set('address')}
                placeholder="Street, area, district"
              />
            </Group>

            {/* Admin metadata group (admin only) */}
            {isAdmin && (
              <Group icon={Shield} title="Admin metadata" subtitle="Name, type, and coordinates — admin only">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  <TextField label="Name" value={form.name} onChange={set('name')} />
                  <TextField label="Type" value={form.hospital_type} onChange={set('hospital_type')} placeholder="District Hospital / Upazila Health Complex / ..." />
                  <NumField label="Latitude"  value={form.latitude}  onChange={set('latitude')}  step="0.0001" min="-90" max="90" />
                  <NumField label="Longitude" value={form.longitude} onChange={set('longitude')} step="0.0001" min="-180" max="180" />
                </div>
              </Group>
            )}

            {error && (
              <p className="mt-3 text-rose-300 text-sm flex items-center gap-1">
                <AlertCircle size={12} /> {error}
              </p>
            )}
            {success && (
              <p className="mt-3 text-emerald-300 text-sm flex items-center gap-1">
                <CheckCircle2 size={12} /> Saved. Directory refreshed.
              </p>
            )}

            <div className="mt-5 flex items-center justify-end gap-2">
              <button
                onClick={onClose}
                className="px-3 py-2 rounded-lg text-sm text-white/70 hover:text-white hover:bg-white/5"
              >
                Cancel
              </button>
              <button
                onClick={submit}
                disabled={!dirty || mutation.isPending}
                className="px-4 py-2 rounded-lg text-sm font-semibold text-white disabled:opacity-40 inline-flex items-center gap-2"
                style={{ background: 'linear-gradient(135deg, #38BDF8, #2DD4BF)' }}
              >
                {mutation.isPending ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />}
                Save changes
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

// ─── Sub-components ─────────────────────────────────────────────────

function Group({
  icon: Icon, title, subtitle, children,
}: { icon: any; title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div className="mt-3">
      <div className="flex items-center gap-2 mb-1.5">
        <Icon size={13} className="text-blue-300" />
        <h4 className="text-sm font-semibold text-white">{title}</h4>
        {subtitle && <span className="text-[10px] text-white/40">— {subtitle}</span>}
      </div>
      {children}
    </div>
  );
}

function TextField({
  label, value, onChange, placeholder,
}: { label: string; value: string; onChange: (e: any) => void; placeholder?: string }) {
  return (
    <label className="block">
      <span className="text-[10px] uppercase tracking-wider text-white/50">{label}</span>
      <input
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        className="mt-0.5 w-full rounded-lg px-2 py-1.5 text-sm text-white outline-none border"
        style={{ background: 'rgba(255,255,255,0.04)', borderColor: 'rgba(255,255,255,0.08)' }}
      />
    </label>
  );
}

function NumField({
  label, value, onChange, step, min, max, hint,
}: { label: string; value: string; onChange: (e: any) => void; step?: string; min?: string; max?: string; hint?: string }) {
  return (
    <label className="block">
      <span className="text-[10px] uppercase tracking-wider text-white/50">{label}</span>
      <input
        value={value}
        onChange={onChange}
        type="number"
        step={step}
        min={min}
        max={max}
        className="mt-0.5 w-full rounded-lg px-2 py-1.5 text-sm text-white outline-none border font-mono"
        style={{ background: 'rgba(255,255,255,0.04)', borderColor: 'rgba(255,255,255,0.08)' }}
      />
      {hint && <span className="text-[10px] text-white/40">{hint}</span>}
    </label>
  );
}
