import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  MonitorPlay,
  ShieldAlert,
  Camera,
  BarChart3,
  HardHat,
  Video,
} from 'lucide-react'

const links = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/live', label: 'Live Monitor', icon: MonitorPlay },
  { to: '/live-camera', label: 'Live Camera', icon: Video },
  { to: '/violations', label: 'Violations', icon: ShieldAlert },
  { to: '/snapshots', label: 'Snapshots', icon: Camera },
  { to: '/analytics', label: 'Analytics', icon: BarChart3 },
]

export default function Sidebar({ systemOk }) {
  return (
    <aside className="fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-white/[0.06] bg-ink-900/80 backdrop-blur-xl">
      {/* Brand */}
      <div className="flex items-center gap-3 px-5 pb-6 pt-6">
        <div className="relative flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-accent/30 to-safe/20 ring-1 ring-accent/40">
          <HardHat className="h-5 w-5 text-accent" />
          <span className="absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full bg-safe ring-2 ring-ink-900" />
        </div>
        <div>
          <h1 className="text-sm font-bold leading-tight tracking-tight text-white">
            Site Safety <span className="gradient-text">Monitor</span>
          </h1>
          <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-slate-500">
            AI PPE Compliance
          </p>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 space-y-1 px-3">
        {links.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-200 ${
                isActive
                  ? 'bg-gradient-to-r from-accent/15 to-transparent text-white shadow-[inset_0_0_0_1px_rgba(34,211,238,0.25)]'
                  : 'text-slate-400 hover:bg-white/[0.04] hover:text-slate-200'
              }`
            }
          >
            {({ isActive }) => (
              <>
                <Icon
                  className={`h-4.5 w-4.5 h-[18px] w-[18px] transition-colors ${
                    isActive ? 'text-accent' : 'text-slate-500 group-hover:text-slate-300'
                  }`}
                />
                {label}
                {isActive && (
                  <span className="ml-auto h-1.5 w-1.5 rounded-full bg-accent animate-pulse-slow" />
                )}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* System status footer */}
      <div className="m-3 rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
        <div className="flex items-center gap-2">
          <span
            className={`h-2 w-2 rounded-full ${
              systemOk ? 'bg-safe animate-pulse-slow' : 'bg-danger'
            }`}
          />
          <span className="text-xs font-semibold text-slate-300">
            {systemOk ? 'System Operational' : 'System Degraded'}
          </span>
        </div>
        <p className="mt-1 font-mono text-[10px] text-slate-500">
          YOLOv8n · CPU inference
        </p>
      </div>
    </aside>
  )
}
