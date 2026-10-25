'use client';

import { useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { useRouter } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { postSignup } from '@/lib/api';
import { saveToken } from '@/lib/auth';
import { getApiErrorMessage } from '@/lib/api';
import { Eye, EyeOff, Loader2 } from 'lucide-react';
import { motion } from 'framer-motion';
import { BANGLADESH_DISTRICTS } from '@/lib/types';
import type { UserRole } from '@/lib/types';

const ROLES: { value: UserRole; label: string }[] = [
  { value: 'citizen', label: 'Citizen' },
  { value: 'health_worker', label: 'Health Worker' },
  { value: 'hospital', label: 'Hospital' },
  { value: 'ngo', label: 'NGO' },
  { value: 'government', label: 'Government' },
  { value: 'admin', label: 'Admin' },
];

const schema = z.object({
  full_name: z.string().min(2, 'Name must be at least 2 characters'),
  email: z.string().email('Please enter a valid email'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
  role: z.enum(['citizen', 'health_worker', 'hospital', 'ngo', 'government', 'admin']),
  district: z.string().optional(),
});

type FormData = z.infer<typeof schema>;

const inputStyle = {
  background: 'rgba(255,255,255,0.05)',
  borderColor: 'rgba(255,255,255,0.1)',
};

export default function SignupPage() {
  const router = useRouter();
  const [showPwd, setShowPwd] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { role: 'citizen' },
  });

  const onSubmit = async (data: FormData) => {
    setApiError(null);
    try {
      const token = await postSignup({
        ...data,
        district: data.district || null,
      });
      saveToken(token.access_token);
      router.push('/dashboard');
    } catch (err) {
      setApiError(getApiErrorMessage(err));
    }
  };

  const labelClass = 'block text-xs font-semibold text-white/60 uppercase tracking-wider mb-1.5';
  const inputClass =
    'w-full px-4 py-3 rounded-xl text-white placeholder:text-white/30 text-sm border focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 transition';

  return (
    <div className="min-h-screen flex">
      {/* Left — decorative */}
      <div
        className="hidden lg:flex flex-1 flex-col items-center justify-center px-12 relative overflow-hidden"
        style={{ background: 'rgba(45,212,191,0.04)', borderRight: '1px solid rgba(45,212,191,0.12)' }}
      >
        <div className="absolute inset-0 opacity-20"
          style={{ background: 'radial-gradient(circle at 40% 60%, rgba(45,212,191,0.25) 0%, transparent 70%)' }}
        />
        <div className="relative z-10 text-center max-w-xs">
          <div className="text-6xl mb-6">🌊</div>
          <h2 className="text-2xl font-black text-white mb-3" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
            Join the early warning network
          </h2>
          <p className="text-white/50 text-sm leading-relaxed">
            From citizens to government agencies — FloodShield AI gives everyone
            the data they need, at the level of detail they can act on.
          </p>
        </div>
      </div>

      {/* Right — form */}
      <div className="flex-1 flex items-center justify-center px-6 py-20">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="w-full max-w-md"
        >
          {/* Official Brand Logo */}
          <Link href="/" className="inline-flex items-center gap-3 mb-8 group">
            <div
              className="relative w-12 h-12 rounded-2xl overflow-hidden flex items-center justify-center p-1 border border-cyan-400/20 group-hover:border-cyan-400/50 transition-all duration-300"
              style={{ background: 'rgba(255, 255, 255, 0.04)', boxShadow: '0 0 20px rgba(56, 189, 248, 0.25)' }}
            >
              <Image
                src="/logo.png"
                alt="FloodShield AI Logo"
                width={40}
                height={40}
                className="object-contain transition-transform duration-300 group-hover:scale-110"
                priority
              />
            </div>
            <div>
              <span className="font-black text-xl text-white tracking-tight" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
                FloodShield<span className="text-blue-400"> AI</span> Pro
              </span>
              <p className="text-white/40 text-xs">Create your authorized account</p>
            </div>
          </Link>

          <h1 className="text-3xl font-black text-white mb-2" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
            Create account
          </h1>
          <p className="text-white/50 mb-8">Start predicting floods and disease outbreaks today.</p>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
            {/* Full name */}
            <div>
              <label className={labelClass} htmlFor="signup-name">Full Name</label>
              <input
                id="signup-name"
                type="text"
                autoComplete="name"
                {...register('full_name')}
                placeholder="Dr. Rahim Uddin"
                className={inputClass}
                style={{ ...inputStyle, borderColor: errors.full_name ? '#F43F5E' : 'rgba(255,255,255,0.1)' }}
              />
              {errors.full_name && <p className="text-red-400 text-xs mt-1">{errors.full_name.message}</p>}
            </div>

            {/* Email */}
            <div>
              <label className={labelClass} htmlFor="signup-email">Email</label>
              <input
                id="signup-email"
                type="email"
                autoComplete="email"
                {...register('email')}
                placeholder="you@example.com"
                className={inputClass}
                style={{ ...inputStyle, borderColor: errors.email ? '#F43F5E' : 'rgba(255,255,255,0.1)' }}
              />
              {errors.email && <p className="text-red-400 text-xs mt-1">{errors.email.message}</p>}
            </div>

            {/* Password */}
            <div>
              <label className={labelClass} htmlFor="signup-password">Password</label>
              <div className="relative">
                <input
                  id="signup-password"
                  type={showPwd ? 'text' : 'password'}
                  autoComplete="new-password"
                  {...register('password')}
                  placeholder="Min. 8 characters"
                  className={`${inputClass} pr-12`}
                  style={{ ...inputStyle, borderColor: errors.password ? '#F43F5E' : 'rgba(255,255,255,0.1)' }}
                />
                <button
                  type="button"
                  onClick={() => setShowPwd((s) => !s)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-white/40 hover:text-white/70 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 rounded"
                  aria-label={showPwd ? 'Hide password' : 'Show password'}
                >
                  {showPwd ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
              {errors.password && <p className="text-red-400 text-xs mt-1">{errors.password.message}</p>}
            </div>

            {/* Role */}
            <div>
              <label className={labelClass} htmlFor="signup-role">Account Type</label>
              <select
                id="signup-role"
                {...register('role')}
                className={inputClass}
                style={{ ...inputStyle, borderColor: 'rgba(255,255,255,0.1)' }}
              >
                {ROLES.map((r) => (
                  <option key={r.value} value={r.value} style={{ background: '#060B14' }}>
                    {r.label}
                  </option>
                ))}
              </select>
            </div>

            {/* District (optional) */}
            <div>
              <label className={labelClass} htmlFor="signup-district">
                District <span className="text-white/30 normal-case font-normal">(optional)</span>
              </label>
              <select
                id="signup-district"
                {...register('district')}
                className={inputClass}
                style={{ ...inputStyle, borderColor: 'rgba(255,255,255,0.1)' }}
              >
                <option value="" style={{ background: '#060B14' }}>— Select your district —</option>
                {BANGLADESH_DISTRICTS.map((d) => (
                  <option key={d} value={d} style={{ background: '#060B14' }}>{d}</option>
                ))}
              </select>
            </div>

            {apiError && (
              <div className="rounded-xl px-4 py-3 text-sm text-red-400 border border-red-400/20 bg-red-400/08">
                {apiError}
              </div>
            )}

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full py-3 rounded-xl font-bold text-white flex items-center justify-center gap-2 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-300 disabled:opacity-60"
              style={{ background: 'linear-gradient(135deg, #38BDF8, #2DD4BF)', boxShadow: '0 0 20px rgba(56,189,248,0.3)' }}
            >
              {isSubmitting ? <Loader2 size={18} className="animate-spin" /> : null}
              {isSubmitting ? 'Creating account…' : 'Create Account'}
            </button>
          </form>

          <p className="text-center text-white/40 text-sm mt-6">
            Already have an account?{' '}
            <Link href="/login" className="text-blue-400 hover:text-blue-300 font-semibold transition focus:outline-none focus-visible:underline">
              Sign in
            </Link>
          </p>
        </motion.div>
      </div>
    </div>
  );
}
