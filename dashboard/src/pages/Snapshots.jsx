import { useEffect, useState } from 'react'
import { Camera, Download, FileImage } from 'lucide-react'
import PageHeader from '../components/PageHeader.jsx'
import GlassCard, { CardHeader } from '../components/GlassCard.jsx'
import StatusPill from '../components/StatusPill.jsx'
import { api, formatBytes } from '../lib/api.js'

export default function Snapshots() {
  const [snaps, setSnaps] = useState([])

  useEffect(() => {
    api.snapshots().then(setSnaps)
  }, [])

  return (
    <div className="animate-fade-up">
      <PageHeader
        title="Snapshots"
        subtitle="Captured automatically when a violation is confirmed"
        right={<StatusPill tone="accent">{snaps.length} files</StatusPill>}
      />

      {snaps.length === 0 ? (
        <GlassCard className="p-10 text-center">
          <Camera className="mx-auto mb-3 h-10 w-10 text-slate-600" />
          <p className="text-sm text-slate-400">No snapshots yet.</p>
        </GlassCard>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {snaps.map((s) => (
            <GlassCard key={s.filename} hover className="overflow-hidden">
              <img
                src={s.url}
                alt={s.filename}
                className="aspect-square w-full object-cover"
              />
              <div className="flex items-center gap-2 border-t border-white/[0.05] px-4 py-3">
                <FileImage className="h-4 w-4 shrink-0 text-accent" />
                <div className="min-w-0 flex-1">
                  <p className="truncate font-mono text-[11px] text-slate-300">{s.filename}</p>
                  <p className="text-[10px] text-slate-500">{formatBytes(s.size_bytes)}</p>
                </div>
                <a
                  href={s.url}
                  download={s.filename}
                  className="rounded-lg bg-white/[0.05] p-2 text-slate-400 ring-1 ring-white/[0.08] transition hover:bg-white/[0.1] hover:text-white"
                  title="Download"
                >
                  <Download className="h-3.5 w-3.5" />
                </a>
              </div>
            </GlassCard>
          ))}
        </div>
      )}
    </div>
  )
}
