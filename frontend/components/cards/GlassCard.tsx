'use client';

import { motion, type HTMLMotionProps } from 'framer-motion';
import { forwardRef, useRef, useCallback } from 'react';

interface GlassCardProps extends HTMLMotionProps<'div'> {
  glowColor?: string;
  children: React.ReactNode;
  tilt?: boolean;
}

const GlassCard = forwardRef<HTMLDivElement, GlassCardProps>(
  ({ glowColor = 'rgba(56,189,248,0.2)', tilt = true, className = '', children, style, ...rest }, ref) => {
    const cardRef = useRef<HTMLDivElement>(null);

    const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
      if (!tilt || !cardRef.current) return;
      const rect = cardRef.current.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const cx = rect.width / 2;
      const cy = rect.height / 2;
      const rotX = ((y - cy) / cy) * -6;
      const rotY = ((x - cx) / cx) * 6;
      cardRef.current.style.transform = `perspective(800px) rotateX(${rotX}deg) rotateY(${rotY}deg) translateY(-4px)`;
    }, [tilt]);

    const handleMouseLeave = useCallback(() => {
      if (!cardRef.current) return;
      cardRef.current.style.transform = '';
    }, []);

    return (
      <motion.div
        ref={(node) => {
          (cardRef as React.MutableRefObject<HTMLDivElement | null>).current = node;
          if (typeof ref === 'function') ref(node);
          else if (ref) ref.current = node;
        }}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
        className={`relative rounded-2xl border transition-all duration-300 ${className}`}
        style={{
          background: 'rgba(255,255,255,0.05)',
          backdropFilter: 'blur(24px)',
          WebkitBackdropFilter: 'blur(24px)',
          borderColor: 'rgba(255,255,255,0.10)',
          borderTopColor: 'rgba(255,255,255,0.18)',
          borderLeftColor: 'rgba(255,255,255,0.14)',
          transition: 'box-shadow 0.3s, border-color 0.3s, transform 0.2s',
          ...style,
        }}
        whileHover={{
          boxShadow: `0 8px 32px ${glowColor}, 0 2px 8px rgba(0,0,0,0.4)`,
        }}
        initial={{ boxShadow: '0 4px 16px rgba(0,0,0,0.3)' }}
        {...rest}
      >
        {children}
      </motion.div>
    );
  }
);

GlassCard.displayName = 'GlassCard';
export default GlassCard;
