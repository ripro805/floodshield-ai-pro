import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
        display: ['Space Grotesk', 'sans-serif'],
      },
      colors: {
        // Risk levels
        risk: {
          low: '#2DD4BF',
          medium: '#FBBF24',
          high: '#FB923C',
          critical: '#F43F5E',
          accent: '#38BDF8',
        },
      },
      backgroundColor: {
        'glass': 'rgba(255,255,255,0.05)',
        'glass-dark': 'rgba(6,11,20,0.8)',
      },
      borderColor: {
        'glass': 'rgba(255,255,255,0.10)',
        'glass-bright': 'rgba(255,255,255,0.18)',
      },
      boxShadow: {
        'glass': '0 4px 16px rgba(0,0,0,0.3)',
        'glass-lg': '0 8px 32px rgba(0,0,0,0.4)',
      },
      animation: {
        'pulse-glow': 'pulse-glow 2s ease-in-out infinite',
      },
      keyframes: {
        'pulse-glow': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.5' },
        },
      },
    },
  },
  plugins: [],
};

export default config;
