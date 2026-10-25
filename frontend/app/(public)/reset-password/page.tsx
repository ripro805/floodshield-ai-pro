'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { useRouter } from 'next/navigation';
import { z } from 'zod';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Eye, EyeOff, Loader2, ArrowLeft } from 'lucide-react';
import { motion } from 'framer-motion';
import { getApiErrorMessage, postResetPassword } from '@/lib/api';

const schema = z.object({
  password: z.string().min(8, 'Password must be at least 8 characters'),
  confirmPassword: z.string().min(1, 'Please confirm your password'),
}).refine((data) => data.password === data.confirmPassword, {
  message: 'Passwords do not match',
  path: ['confirmPassword'],
});

type FormData = z.infer<typeof schema>;

export default function ResetPasswordPage() {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmation, setShowConfirmation] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<FormData>({ resolver: zodResolver(schema) });

  useEffect(() => {
    setToken(new URLSearchParams(window.location.search).get('token'));
  }, []);

  const onSubmit = async ({ password }: FormData) => {
    if (!token) {
      setApiError('This password reset link is missing or invalid.');
      return;
    }
    setApiError(null);
    try {
      await postResetPassword(token, password);
      router.replace('/login?reset=success');
    } catch (error) {
      setApiError(getApiErrorMessage(error));
    }
  };

  const inputClass = 'w-full px-4 py-3 pr-12 rounded-xl text-white placeholder:text-white/30 text-sm border focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 transition';
  const inputStyle = { background: 'rgba(255,255,255,0.05)' };

  return (
    <main className="min-h-screen flex items-center justify-center px-6 py-20">
      <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} className="w-full max-w-md">
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
            <p className="text-white/40 text-xs">National Early Warning System</p>
          </div>
        </Link>
        <Link href="/login" className="inline-flex items-center gap-2 text-white/50 hover:text-white text-sm mb-6 transition"><ArrowLeft size={15} /> Back to sign in</Link>
        <h1 className="text-3xl font-black text-white mb-2" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>Set a new password</h1>
        <p className="text-white/50 mb-8">Choose a strong password with at least 8 characters.</p>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <div>
            <label className="block text-xs font-semibold text-white/60 uppercase tracking-wider mb-1.5" htmlFor="reset-password">New password</label>
            <div className="relative">
              <input id="reset-password" type={showPassword ? 'text' : 'password'} autoComplete="new-password" {...register('password')} placeholder="Min. 8 characters" className={inputClass} style={{ ...inputStyle, borderColor: errors.password ? '#F43F5E' : 'rgba(255,255,255,0.1)' }} />
              <button type="button" onClick={() => setShowPassword((value) => !value)} className="absolute right-3 top-1/2 -translate-y-1/2 text-white/40 hover:text-white/70 rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400" aria-label={showPassword ? 'Hide password' : 'Show password'}>{showPassword ? <EyeOff size={16} /> : <Eye size={16} />}</button>
            </div>
            {errors.password && <p className="text-red-400 text-xs mt-1">{errors.password.message}</p>}
          </div>
          <div>
            <label className="block text-xs font-semibold text-white/60 uppercase tracking-wider mb-1.5" htmlFor="reset-confirm-password">Confirm new password</label>
            <div className="relative">
              <input id="reset-confirm-password" type={showConfirmation ? 'text' : 'password'} autoComplete="new-password" {...register('confirmPassword')} placeholder="Repeat your password" className={inputClass} style={{ ...inputStyle, borderColor: errors.confirmPassword ? '#F43F5E' : 'rgba(255,255,255,0.1)' }} />
              <button type="button" onClick={() => setShowConfirmation((value) => !value)} className="absolute right-3 top-1/2 -translate-y-1/2 text-white/40 hover:text-white/70 rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400" aria-label={showConfirmation ? 'Hide password confirmation' : 'Show password confirmation'}>{showConfirmation ? <EyeOff size={16} /> : <Eye size={16} />}</button>
            </div>
            {errors.confirmPassword && <p className="text-red-400 text-xs mt-1">{errors.confirmPassword.message}</p>}
          </div>
          {apiError && <div className="rounded-xl px-4 py-3 text-sm text-red-400 border border-red-400/20 bg-red-400/08">{apiError}</div>}
          <button type="submit" disabled={isSubmitting || !token} className="w-full py-3 rounded-xl font-bold text-white flex items-center justify-center gap-2 transition disabled:opacity-60" style={{ background: 'linear-gradient(135deg, #38BDF8, #2DD4BF)', boxShadow: '0 0 20px rgba(56,189,248,0.3)' }}>
            {isSubmitting && <Loader2 size={18} className="animate-spin" />}
            {isSubmitting ? 'Updating password…' : 'Reset password'}
          </button>
        </form>
      </motion.div>
    </main>
  );
}
