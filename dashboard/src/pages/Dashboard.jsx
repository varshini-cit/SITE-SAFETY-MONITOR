import { useEffect, useState } from 'react'
import {
  Activity, Users, ShieldAlert, BellRing, HardHat, Video,
  ShieldCheck, Clock, AlertTriangle, Cpu,
} from 'lucide-react'
import PageHeader from '../components/PageHeader.jsx'
import StatCard from '../components/StatCard.jsx'
import GlassCard, { CardHeader } from '../components/GlassCard.jsx'
import StatusPill from '../components/StatusPill.jsx'
import ComplianceRing from '../components/ComplianceRing.jsx'
import { api, formatBytes, formatTime, pct } from '../lib/api.js'

export default function Dashboard() {
  const [summary, setSummary] = useState(null)
  const [health, setHealth] = useState(null)
  const [events, setEvents] = useState([])

  useEffect(() => {
    api.summary().then(setSummary)
    api.health().then(setHealth)
    api.events().then(setEvents)
  }, [])

  const ev = summary?.latest_event
  const compliance = summary
    ? 1 - summary.violations_confirmed / Math.max(summary.persons_detected_latest, 1)
    : null

  return (
    <div className="animate-fade-up">
      <PageHeader
        title="Dashboard"
        subtitle="Real-time PPE compliance overview — powered by the real pipeline outputs"
        right={
          <StatusPill tone={summary?.model_present ? 'safe' : 'danger'} pulse>
            {summary?.model_present ? 'Model Loaded' : 'Model Missing'}
          </StatusPill>
        }
      />

      {/* Stat cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard icon={Users} label="Persons Detected" value={summary?.persons_detected_latest ?? '—'} sub="latest event" tone="accent" delay={0} />
        <StatCard icon={ShieldAlert} label="PPE Violations" value={summary?.violations_confirmed ?? '—'} sub={`${summary?.helmet_violations ?? 0} helmet · ${summary?.vest_violations ?? 0} vest`} tone="danger" delay={60} />
        <StatCard icon={BellRing} label="Alerts Generated" value={summary?.alerts_generated ?? '—'} sub="after 8-frame persistence" tone="warn" delay={120} />
        <StatCard icon={Video} label="Processed Video" value={summary?.processed_video_present ? formatBytes(summary.processed_video_size) : 'None'} sub="outputs/videos/" tone="slate" delay={180} />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Video monitor */}
        <GlassCard className="lg:col-span-2 overflow-hidden">
          <CardHeader
            icon={Cpu}
            title="Processed Site Feed"
            subtitle="outputs/videos/processed_site_video.mp4"
            right={<StatusPill tone="accent" pulse>Processed</StatusPill>}
          />
          <div className="relative">
            <video
              className="aspect-video w-full bg-black object-contain"
              src={`/api/videos/processed_site_video.mp4?v=2`}
              controls
              muted
              loop
            />
            <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-accent/60 to-transparent animate-scanline" />
          </div>
        </GlassCard>

        {/* Compliance + latest violation */}
        <div className="space-y-4">
          <GlassCard className="flex flex-col items-center p-5">
            <h3 className="mb-3 self-start text-sm font-semibold text-white">Compliance Status</h3>
            {compliance != null ? (
              <ComplianceRing value={compliance} label="current session" />
            ) : (
              <p className="py-6 text-sm text-slate-500">Loading…</p>
            )}
            <p className="mt-2 text-center text-xs text-slate-500">
              Based on {summary?.persons_detected_latest ?? 0} tracked person(s) and{' '}
              {summary?.violations_confirmed ?? 0} confirmed violation(s) in the current session.
            </p>
          </GlassCard>

          <GlassCard className="p-5">
            <h3 className="mb-3 text-sm font-semibold text-white">Latest Violation</h3>
            {ev ? (
              <div className="space-y-2.5">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 text-warn" />
                  <span className="text-sm font-semibold text-white">Missing PPE</span>
                  <StatusPill tone="danger">Confirmed</StatusPill>
                </div>
                <div className="grid grid-cols-2 gap-2 font-mono text-[11px] text-slate-400">
                  <span>track_id: <span className="text-slate-200">#{ev.track_id}</span></span>
                  <span>frame: <span className="text-slate-200">{ev.frame_number}</span></span>
                  <span>video t: <span className="text-slate-200">{ev.video_timestamp}</span></span>
                  <span>conf: <span className="text-slate-200">{ev.confidence ? `${(ev.confidence * 100).toFixed(1)}%` : '—'}</span></span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {(ev.missing || []).map((m) => (
                    <StatusPill key={m} tone="warn">missing {m}</StatusPill>
                  ))}
                </div>
                {ev.snapshot && (
                  <img
                    src={`/api/snapshots/${ev.snapshot.split(/[\\/]/).pop()}`}
                    alt="latest violation snapshot"
                    className="mt-1 w-full rounded-lg ring-1 ring-white/10"
                  />
                )}
              </div>
            ) : (
              <p className="py-4 text-sm text-slate-500">No violations recorded yet.</p>
            )}
          </GlassCard>
        </div>
      </div>

      {/* Recent events */}
      <GlassCard className="mt-4">
        <CardHeader icon={Clock} title="Recent Events" subtitle="from violations_log.json (newest first)" />
        <div className="divide-y divide-white/[0.04]">
          {events.length === 0 && (
            <p className="px-5 py-6 text-sm text-slate-500">No confirmed violations logged.</p>
          )}
          {events.map((e, i) => (
            <div key={i} className="flex flex-wrap items-center gap-3 px-5 py-3 text-sm">
              <StatusPill tone="danger">Violation</StatusPill>
              <span className="text-slate-300">missing {(e.missing || []).join(' + ') || 'PPE'}</span>
              <span className="font-mono text-xs text-slate-500">#{e.track_id}</span>
              <span className="ml-auto font-mono text-xs text-slate-500">frame {e.frame_number} · {formatTime(e.timestamp)}</span>
            </div>
          ))}
        </div>
      </GlassCard>
    </div>
  )
}
