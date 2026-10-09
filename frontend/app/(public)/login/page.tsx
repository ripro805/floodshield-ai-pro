'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { postLogin } from '@/lib/api';
import { saveToken } from '@/lib/auth';
import { getApiErrorMessage } from '@/lib/api';
import { Shield, Eye, EyeOff, Loader2 } from 'lucide-react';
import { motion } from 'framer-motion';

const schema = z.object({
  email: z.string().email('Please enter a valid email'),
  password: z.string().min(1, 'Password is required'),
});

type FormData = z.infer<typeof schema>;

export default function LoginPage() {
  const router = useRouter();
  const [showPwd, setShowPwd] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema) });

  const onSubmit = async (data: FormData) => {
    setApiError(null);
    try {
      const token = await postLogin(data);
      saveToken(token.access_token);
      router.push('/dashboard');
    } catch (err) {
      setApiError(getApiErrorMessage(err));
    }
  };

  return (
    <div className="min-h-screen flex">
      {/* Left — form */}
      <div className="flex-1 flex items-center justify-center px-6 py-20">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="w-full max-w-md"
        >
          {/* Logo */}
          <div className="flex items-center gap-3 mb-8">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-teal-400 flex items-center justify-center">
              <Shield size={20} className="text-white" />
            </div>
            <div>
              <span className="font-black text-xl text-white" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
                FloodShield<span className="text-blue-400"> AI</span>
              </span>
              <p className="text-white/40 text-xs">Early warning platform</p>
            </div>
          </div>

          <h1 className="text-3xl font-black text-white mb-2" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
            Sign in
          </h1>
          <p className="text-white/50 mb-8">Welcome back. Enter your credentials to access the dashboard.</p>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
            {/* Email */}
            <div>
              <label className="block text-xs font-semibold text-white/60 uppercase tracking-wider mb-1.5" htmlFor="login-email">
                Email
              </label>
              <input
                id="login-email"
                type="email"
                autoComplete="email"
                {...register('email')}
                placeholder="you@example.com"
                className="w-full px-4 py-3 rounded-xl text-white placeholder:text-white/30 text-sm border focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 transition"
                style={{ background: 'rgba(255,255,255,0.05)', borderColor: errors.email ? '#F43F5E' : 'rgba(255,255,255,0.1)' }}
              />
              {errors.email && <p className="text-red-400 text-xs mt-1">{errors.email.message}</p>}
            </div>

            {/* Password */}
            <div>
              <label className="block text-xs font-semibold text-white/60 uppercase tracking-wider mb-1.5" htmlFor="login-password">
                Password
              </label>
              <div className="relative">
                <input
                  id="login-password"
                  type={showPwd ? 'text' : 'password'}
                  autoComplete="current-password"
                  {...register('password')}
                  placeholder="••••••••"
                  className="w-full px-4 py-3 pr-12 rounded-xl text-white placeholder:text-white/30 text-sm border focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 transition"
                  style={{ background: 'rgba(255,255,255,0.05)', borderColor: errors.password ? '#F43F5E' : 'rgba(255,255,255,0.1)' }}
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

            {/* API error */}
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
              {isSubmitting ? 'Signing in…' : 'Sign In'}
            </button>
          </form>

          <div className="text-center mt-5">
            <Link href="/forgot-password" className="text-blue-400 hover:text-blue-300 text-sm font-semibold transition focus:outline-none focus-visible:underline">
              Forgot your password?
            </Link>
          </div>

          <p className="text-center text-white/40 text-sm mt-6">
            No account?{' '}
            <Link href="/signup" className="text-blue-400 hover:text-blue-300 font-semibold transition focus:outline-none focus-visible:underline">
              Create one free
            </Link>
          </p>
        </motion.div>
      </div>

      {/* Right — decorative panel */}
      <div
        className="hidden lg:flex flex-1 flex-col items-center justify-center px-12 relative overflow-hidden"
        style={{ background: 'rgba(56,189,248,0.04)', borderLeft: '1px solid rgba(56,189,248,0.12)' }}
      >
        <div className="absolute inset-0 opacity-20"
          style={{ background: 'radial-gradient(circle at 60% 40%, rgba(56,189,248,0.3) 0%, transparent 70%)' }}
        />
        <div className="relative z-10 text-center max-w-xs">
          <div className="text-6xl mb-6">🛰️</div>
          <h2 className="text-2xl font-black text-white mb-3" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
            Real satellite data. Real predictions.
          </h2>
          <p className="text-white/50 text-sm leading-relaxed">
            Sentinel-1 SAR imagery, 6 trained ML models, and live weather integration —
            all at your fingertips for Bangladesh&apos;s 64 districts.
          </p>
        </div>
      </div>
    </div>
  );
}
