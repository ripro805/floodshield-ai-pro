'use client';

import React, { useState, useEffect } from 'react';
import Image from 'next/image';
import { usePathname } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';

const LOADING_STEPS = [
  'Initializing Predictive Intelligence...',
  'Syncing Hydrological & Satellite Feeds...',
  'Calibrating 64-District Early Warning Shield...',
  'Welcome to FloodShield AI Pro',
];

export default function SplashLoader() {
  const pathname = usePathname();
  const [visible, setVisible] = useState(false);
  const [stepIndex, setStepIndex] = useState(0);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    // Only trigger entrance animation on project root / entry
    if (pathname !== '/') {
      setVisible(false);
      return;
    }

    // Check if splash has already played in this browser session
    const hasSeenSplash = sessionStorage.getItem('fs_splash_seen');
    if (hasSeenSplash) {
      setVisible(false);
      return;
    }

    setVisible(true);

    // Step progression
    const stepInterval = setInterval(() => {
      setStepIndex((prev) => (prev < LOADING_STEPS.length - 1 ? prev + 1 : prev));
    }, 550);

    // Progress bar smooth advance
    const progressInterval = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 100) {
          clearInterval(progressInterval);
          return 100;
        }
        return prev + 2.5;
      });
    }, 45);

    // Graceful auto-dismiss after completion
    const timer = setTimeout(() => {
      setVisible(false);
      sessionStorage.setItem('fs_splash_seen', 'true');
    }, 2300);

    return () => {
      clearInterval(stepInterval);
      clearInterval(progressInterval);
      clearTimeout(timer);
    };
  }, []);

  const handleSkip = () => {
    setVisible(false);
    sessionStorage.setItem('fs_splash_seen', 'true');
  };

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          key="splash-loader"
          initial={{ opacity: 1 }}
          exit={{
            opacity: 0,
            scale: 1.06,
            filter: 'blur(12px)',
            transition: { duration: 0.65, ease: [0.22, 1, 0.36, 1] },
          }}
          className="fixed inset-0 z-[9999] flex flex-col items-center justify-center overflow-hidden select-none"
          style={{
            background: 'radial-gradient(ellipse at center, #0B192C 0%, #060B14 70%, #03070E 100%)',
          }}
          onClick={handleSkip}
          title="Click to enter immediately"
        >
          {/* Ambient luminous glow circles */}
          <div
            className="absolute w-[450px] h-[450px] rounded-full pointer-events-none opacity-25 blur-[100px]"
            style={{
              background: 'radial-gradient(circle, rgba(56,189,248,0.8) 0%, rgba(45,212,191,0.4) 60%, transparent 100%)',
            }}
          />
          <div
            className="absolute w-[600px] h-[600px] rounded-full pointer-events-none opacity-10 blur-[140px]"
            style={{
              background: 'radial-gradient(circle, rgba(14,165,233,0.6) 0%, transparent 70%)',
            }}
          />

          {/* Animated pulse radar rings */}
          <div className="relative flex items-center justify-center">
            <motion.div
              animate={{
                scale: [1, 1.45, 1.8],
                opacity: [0.6, 0.25, 0],
              }}
              transition={{
                duration: 2.2,
                repeat: Infinity,
                ease: 'easeOut',
              }}
              className="absolute w-44 h-44 rounded-full border border-cyan-400/30"
              style={{
                boxShadow: '0 0 40px rgba(56,189,248,0.2)',
              }}
            />
            <motion.div
              animate={{
                scale: [1, 1.35, 1.65],
                opacity: [0.5, 0.2, 0],
              }}
              transition={{
                duration: 2.2,
                repeat: Infinity,
                delay: 0.5,
                ease: 'easeOut',
              }}
              className="absolute w-44 h-44 rounded-full border border-teal-400/25"
            />

            {/* Central Animated Logo Container */}
            <motion.div
              initial={{ scale: 0.65, opacity: 0, rotate: -4 }}
              animate={{
                scale: [0.65, 1.12, 0.98, 1.05, 1.0],
                opacity: [0, 1, 1, 1, 1],
                rotate: [-4, 2, -1, 1, 0],
              }}
              transition={{
                duration: 1.8,
                ease: [0.34, 1.56, 0.64, 1],
              }}
              className="relative z-10 w-36 h-36 md:w-44 md:h-44 p-3 rounded-3xl flex items-center justify-center"
              style={{
                background: 'rgba(255, 255, 255, 0.03)',
                backdropFilter: 'blur(20px)',
                border: '1px solid rgba(56, 189, 248, 0.25)',
                boxShadow:
                  '0 0 50px rgba(56, 189, 248, 0.35), inset 0 0 20px rgba(45, 212, 191, 0.15)',
              }}
            >
              {/* Continuous Breathing Glow behind Logo */}
              <motion.div
                animate={{
                  opacity: [0.4, 0.8, 0.4],
                  scale: [0.95, 1.05, 0.95],
                }}
                transition={{
                  duration: 2.0,
                  repeat: Infinity,
                  ease: 'easeInOut',
                }}
                className="absolute inset-0 rounded-3xl"
                style={{
                  background:
                    'radial-gradient(circle, rgba(56, 189, 248, 0.3) 0%, rgba(45, 212, 191, 0.15) 50%, transparent 80%)',
                }}
              />

              <Image
                src="/logo.png"
                alt="FloodShield AI Pro Official Logo"
                width={160}
                height={160}
                priority
                className="object-contain relative z-10 drop-shadow-[0_0_24px_rgba(56,189,248,0.5)]"
              />
            </motion.div>
          </div>

          {/* Typography */}
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.35, duration: 0.7 }}
            className="mt-8 text-center px-4 z-10"
          >
            <h1
              className="text-3xl md:text-4xl font-black tracking-tight text-white"
              style={{ fontFamily: 'Space Grotesk, sans-serif' }}
            >
              FloodShield{' '}
              <span
                style={{
                  background: 'linear-gradient(135deg, #38BDF8 0%, #2DD4BF 100%)',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                }}
              >
                AI Pro
              </span>
            </h1>
            <p className="text-white/50 text-xs md:text-sm mt-1.5 tracking-wider uppercase font-medium">
              National Flood & Epidemic Early Warning Decision System
            </p>
          </motion.div>

          {/* Dynamic Loading Step Text & Progress Bar */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.5, duration: 0.5 }}
            className="mt-6 flex flex-col items-center w-64 md:w-80 z-10"
          >
            {/* Smooth Status Label */}
            <motion.span
              key={stepIndex}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              className="text-xs text-cyan-300/80 font-mono tracking-tight mb-2.5 h-4"
            >
              {LOADING_STEPS[stepIndex]}
            </motion.span>

            {/* Glowing Progress Bar */}
            <div className="w-full h-1.5 bg-white/10 rounded-full overflow-hidden p-0.5 border border-white/05">
              <motion.div
                className="h-full rounded-full"
                style={{
                  width: `${progress}%`,
                  background: 'linear-gradient(90deg, #0284C7, #38BDF8, #2DD4BF)',
                  boxShadow: '0 0 12px rgba(56, 189, 248, 0.8)',
                }}
              />
            </div>

            {/* Quick Skip hint */}
            <span className="text-[10px] text-white/30 mt-3 hover:text-white/60 transition cursor-pointer">
              Click anywhere to skip
            </span>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
