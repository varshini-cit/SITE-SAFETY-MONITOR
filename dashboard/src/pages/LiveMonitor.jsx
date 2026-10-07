import { useEffect, useState } from 'react'
import { MonitorPlay, FolderOpen, ShieldAlert, Info } from 'lucide-react'
import PageHeader from '../components/PageHeader.jsx'
import GlassCard, { CardHeader } from '../components/GlassCard.jsx'
import StatusPill from '../components/StatusPill.jsx'
import { api, formatBytes } from '../lib/api.js'

// Cache-buster: the endpoint transparently serves an H.264 web copy; the ?v=
// forces browsers past any cached copy of the old mp4v (non-browser) bytes.
const VIDEO_BUST = '2'


export default function LiveMonitor() {
  const [videos, setVideos] = useState([])
  const [summary, setSummary] = useState(null)

  useEffect(() => {
    api.videos().then(setVideos)
    api.summary().then(setSummary)
  }, [])

  return (
    <div className="animate-fade-up">
      <PageHeader
        title="Live Monitor"
        subtitle="Processed feeds from the detection pipeline (pre-recorded prototype)"
        right={<StatusPill tone="accent" pulse>Pipeline Ready</StatusPill>}
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <GlassCard className="overflow-hidden lg:col-span-2">
          <CardHeader
            icon={MonitorPlay}
            title="Primary Feed"
            subtitle="outputs/videos/processed_site_video.mp4"
            right={<StatusPill tone="safe">8-frame rule active</StatusPill>}
          />
          <video
            className="aspect-video w-full bg-black object-contain"
            src={`/api/videos/processed_site_video.mp4?v=${VIDEO_BUST}`}
            controls muted loop
          />
        </GlassCard>

        <div className="space-y-4">
          <GlassCard className="p-5">
            <h3 className="mb-3 text-sm font-semibold text-white">Pipeline Configuration</h3>
            <ul className="space-y-2 font-mono text-xs text-slate-400">
              <li className="flex justify-between"><span>model</span><span className="text-slate-200">models/ppe_model.pt</span></li>
              <li className="flex justify-between"><span>imgsz</span><span className="text-slate-200">640</span></li>
              <li className="flex justify-between"><span>conf</span><span className="text-slate-200">0.25</span></li>
              <li className="flex justify-between"><span>overlap</span><span className="text-slate-200">0.05</span></li>
              <li className="flex justify-between"><span>persistence</span><span className="text-slate-200">8 frames</span></li>
              <li className="flex justify-between"><span>device</span><span className="text-slate-200">cpu</span></li>
            </ul>
            <p className="mt-3 flex items-start gap-1.5 text-[11px] leading-relaxed text-slate-500">
              <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              Values from src/config.py — the single source of truth for the pipeline.
            </p>
          </GlassCard>

          <GlassCard className="p-5">
            <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
              <ShieldAlert className="h-4 w-4 text-warn" /> Session Result
            </h3>
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-xl bg-white/[0.03] p-3 ring-1 ring-white/[0.06]">
                <p className="text-2xl font-bold text-white">{summary?.violations_confirmed ?? '—'}</p>
                <p className="text-[11px] text-slate-500">violations</p>
              </div>
              <div className="rounded-xl bg-white/[0.03] p-3 ring-1 ring-white/[0.06]">
                <p className="text-2xl font-bold text-white">{summary?.alerts_generated ?? '—'}</p>
                <p className="text-[11px] text-slate-500">alerts</p>
              </div>
            </div>
          </GlassCard>
        </div>
      </div>

      <GlassCard className="mt-4">
        <CardHeader icon={FolderOpen} title="All Processed Videos" subtitle="served from outputs/videos/" />
        <div className="divide-y divide-white/[0.04]">
          {videos.length === 0 && (
            <p className="px-5 py-6 text-sm text-slate-500">No processed videos yet — run run_detection.py first.</p>
          )}
          {videos.map((v) => (
            <div key={v.filename} className="flex flex-wrap items-center gap-3 px-5 py-3 text-sm">
              <MonitorPlay className="h-4 w-4 text-accent" />
              <span className="font-mono text-xs text-slate-300">{v.filename}</span>
              <span className="text-xs text-slate-500">{formatBytes(v.size_bytes)}</span>
              <a
                href={v.url}
                target="_blank"
                rel="noreferrer"
                className="ml-auto rounded-lg bg-accent/10 px-3 py-1.5 text-xs font-semibold text-accent ring-1 ring-accent/25 transition hover:bg-accent/20"
              >
                Open
              </a>
            </div>
          ))}
        </div>
      </GlassCard>
    </div>
  )
}
