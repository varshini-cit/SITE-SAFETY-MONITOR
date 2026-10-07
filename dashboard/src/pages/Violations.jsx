import { useEffect, useState } from 'react'
import { ShieldAlert, Clock, Hash, Image as ImageIcon } from 'lucide-react'
import PageHeader from '../components/PageHeader.jsx'
import GlassCard, { CardHeader } from '../components/GlassCard.jsx'
import StatusPill from '../components/StatusPill.jsx'
import { api, formatTime } from '../lib/api.js'

export default function Violations() {
  const [events, setEvents] = useState([])

  useEffect(() => {
    api.events().then(setEvents)
  }, [])

  return (
    <div className="animate-fade-up">
      <PageHeader
        title="Violations"
        subtitle="Confirmed PPE violations — each required 8 consecutive violating frames"
        right={<StatusPill tone="danger">{events.length} confirmed</StatusPill>}
      />

      {events.length === 0 ? (
        <GlassCard className="p-10 text-center">
          <ShieldCheck className="mx-auto mb-3 h-10 w-10 text-safe" />
          <p className="text-sm text-slate-400">
            No confirmed violations recorded. The pipeline is compliant.
          </p>
        </GlassCard>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {events.map((e, i) => (
            <GlassCard key={i} hover className="overflow-hidden">
              <div className="flex flex-col gap-4 p-5 sm:flex-row">
                <img
                  src={e.snapshot?.split(/[\\/]/).pop() ? `/api/snapshots/${e.snapshot.split(/[\\/]/).pop()}` : ''}
                  alt={`violation frame ${e.frame_number}`}
                  className="h-40 w-full rounded-xl object-cover ring-1 ring-white/10 sm:w-56"
                />
                <div className="flex-1 space-y-2.5">
                  <div className="flex items-center justify-between">
                    <span className="flex items-center gap-2 text-sm font-semibold text-white">
                      <ShieldAlert className="h-4 w-4 text-danger" />
                      Missing PPE — #{e.track_id}
                    </span>
                    <StatusPill tone="danger">Confirmed</StatusPill>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {(e.missing || []).map((m) => (
                      <StatusPill key={m} tone="warn">no {m}</StatusPill>
                    ))}
                  </div>
                  <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 font-mono text-[11px] text-slate-400">
                    <span className="flex items-center gap-1.5"><Clock className="h-3 w-3" />{formatTime(e.timestamp)}</span>
                    <span className="flex items-center gap-1.5"><Hash className="h-3 w-3" />frame {e.frame_number}</span>
                    <span>video t: {e.video_timestamp}</span>
                    <span>person conf: {e.confidence ? `${(e.confidence * 100).toFixed(1)}%` : '—'}</span>
                  </div>
                  <p className="truncate font-mono text-[10px] text-slate-600">
                    <ImageIcon className="mr-1 inline h-3 w-3" />
                    {e.snapshot?.split(/[\\/]/).pop()}
                  </p>
                </div>
              </div>
            </GlassCard>
          ))}
        </div>
      )}
    </div>
  )
}

function ShieldCheck(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z" />
      <path d="m9 12 2 2 4-4" />
    </svg>
  )
}
