import { TrendingUp, TrendingDown, Minus } from 'lucide-react'

export default function StatCard({ icon: Icon, label, value, sub, tone = 'accent', delay = 0 }) {
  const tones = {
    accent: 'from-accent/20 to-accent/5 text-accent ring-accent/30',
    safe: 'from-safe/20 to-safe/5 text-safe ring-safe/30',
    warn: 'from-warn/20 to-warn/5 text-warn ring-warn/30',
    danger: 'from-danger/20 to-danger/5 text-danger ring-danger/30',
    slate: 'from-slate-400/15 to-slate-400/5 text-slate-300 ring-slate-400/25',
  }

  return (
    <div
      className="glass glass-hover animate-fade-up p-5"
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-slate-500">
            {label}
          </p>
          <p className="mt-2 text-3xl font-bold tracking-tight text-white">{value}</p>
          {sub && (
            <p className="mt-1.5 flex items-center gap-1 text-xs text-slate-400">
              {sub}
            </p>
          )}
        </div>
        <div
          className={`flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br ring-1 ${tones[tone]}`}
        >
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </div>
  )
}

export function Trend({ value, suffix = 'vs prev' }) {
  if (value == null) return <Minus className="h-3.5 w-3.5 text-slate-600" />
  const up = value >= 0
  return (
    <span className={up ? 'text-safe' : 'text-danger'}>
      {up ? <TrendingUp className="inline h-3.5 w-3.5" /> : <TrendingDown className="inline h-3.5 w-3.5" />}
      {' '}
      {up ? '+' : ''}
      {value}
      {suffix ? ` ${suffix}` : ''}
    </span>
  )
}
