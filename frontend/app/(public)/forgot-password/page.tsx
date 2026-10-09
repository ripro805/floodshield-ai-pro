'use client';

import { useState } from 'react';
import Link from 'next/link';
import { z } from 'zod';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Shield, Loader2, Mail, ArrowLeft } from 'lucide-react';
import { motion } from 'framer-motion';
import { getApiErrorMessage, postForgotPassword } from '@/lib/api';

const schema = z.object({
  email: z.string().email('Please enter a valid email'),
});

type FormData = z.infer<typeof schema>;

export default function ForgotPasswordPage() {
  const [message, setMessage] = useState<string | null>(null);
  const [resetToken, setResetToken] = useState<string | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<FormData>({
    resolver: zodResolver(schema),
  });

  const onSubmit = async ({ email }: FormData) => {
    setApiError(null);
    setMessage(null);
    setResetToken(null);
    try {
      const response = await postForgotPassword(email);
      setMessage(response.message);
      if (response.reset_token) setResetToken(response.reset_token);
    } catch (error) {
      setApiError(getApiErrorMessage(error));
    }
  };

  return (
    <main className="min-h-screen flex items-center justify-center px-6 py-20">
      <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} className="w-full max-w-md">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-teal-400 flex items-center justify-center">
            <Shield size={20} className="text-white" />
          </div>
          <span className="font-black text-xl text-white" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
            FloodShield<span className="text-blue-400"> AI</span>
          </span>
        </div>

        <Link href="/login" className="inline-flex items-center gap-2 text-white/50 hover:text-white text-sm mb-6 transition">
          <ArrowLeft size={15} /> Back to sign in
        </Link>
        <h1 className="text-3xl font-black text-white mb-2" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
          Forgot password?
        </h1>
        <p className="text-white/50 mb-8">Enter your account email and we&apos;ll help you get back in.</p>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <div>
            <label className="block text-xs font-semibold text-white/60 uppercase tracking-wider mb-1.5" htmlFor="forgot-email">Email</label>
            <div className="relative">
              <Mail size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-white/30" />
              <input
                id="forgot-email"
                type="email"
                autoComplete="email"
                {...register('email')}
                placeholder="you@example.com"
                className="w-full pl-11 pr-4 py-3 rounded-xl text-white placeholder:text-white/30 text-sm border focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 transition"
                style={{ background: 'rgba(255,255,255,0.05)', borderColor: errors.email ? '#F43F5E' : 'rgba(255,255,255,0.1)' }}
              />
            </div>
            {errors.email && <p className="text-red-400 text-xs mt-1">{errors.email.message}</p>}
          </div>

          {apiError && <div className="rounded-xl px-4 py-3 text-sm text-red-400 border border-red-400/20 bg-red-400/08">{apiError}</div>}
          {message && <div className="rounded-xl px-4 py-3 text-sm text-teal-300 border border-teal-400/20 bg-teal-400/08">{message}</div>}
          {resetToken && (
            <Link
              href={`/reset-password?token=${encodeURIComponent(resetToken)}`}
              className="block w-full py-3 rounded-xl text-center font-bold text-white bg-gradient-to-r from-blue-500 to-teal-400 hover:opacity-90 transition"
            >
              Continue to reset password
            </Link>
          )}

          {!resetToken && (
            <button type="submit" disabled={isSubmitting} className="w-full py-3 rounded-xl font-bold text-white flex items-center justify-center gap-2 transition disabled:opacity-60" style={{ background: 'linear-gradient(135deg, #38BDF8, #2DD4BF)' }}>
              {isSubmitting && <Loader2 size={18} className="animate-spin" />}
              {isSubmitting ? 'Preparing…' : 'Send reset instructions'}
            </button>
          )}
        </form>
      </motion.div>
    </main>
  );
}
