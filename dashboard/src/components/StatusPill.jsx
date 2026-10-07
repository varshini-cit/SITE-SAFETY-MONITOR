const tones = {
  safe: 'bg-safe/10 text-safe ring-safe/30',
  warn: 'bg-warn/10 text-warn ring-warn/30',
  danger: 'bg-danger/10 text-danger ring-danger/30',
  slate: 'bg-slate-400/10 text-slate-300 ring-slate-400/25',
  accent: 'bg-accent/10 text-accent ring-accent/30',
}

export default function StatusPill({ tone = 'slate', children, pulse = false }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ${tones[tone]}`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${
          pulse ? 'animate-pulse-slow' : ''
        } bg-current`}
      />
      {children}
    </span>
  )
}
