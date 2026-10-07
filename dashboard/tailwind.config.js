/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      colors: {
        ink: {
          950: '#05070d',
          900: '#0a0e17',
          850: '#0d1320',
          800: '#111827',
          700: '#1a2332',
        },
        accent: {
          DEFAULT: '#22d3ee',
          soft: '#67e8f9',
        },
        safe: '#34d399',
        warn: '#fbbf24',
        danger: '#f87171',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'glow': 'glow 2.5s ease-in-out infinite alternate',
      },
      keyframes: {
        glow: {
          '0%': { boxShadow: '0 0 12px rgba(34,211,238,0.15)' },
          '100%': { boxShadow: '0 0 24px rgba(34,211,238,0.35)' },
        },
      },
    },
  },
  plugins: [],
}
