export default function GlassCard({ children, className = '', hover = false }) {
  return (
    <div className={`glass ${hover ? 'glass-hover' : ''} ${className}`}>{children}</div>
  )
}

export function CardHeader({ icon: Icon, title, subtitle, right }) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-white/[0.05] px-5 py-4">
      <div className="flex items-center gap-2.5">
        {Icon && (
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent/10 ring-1 ring-accent/20">
            <Icon className="h-4 w-4 text-accent" />
          </div>
        )}
        <div>
          <h3 className="text-sm font-semibold text-white">{title}</h3>
          {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
        </div>
      </div>
      {right}
    </div>
  )
}
