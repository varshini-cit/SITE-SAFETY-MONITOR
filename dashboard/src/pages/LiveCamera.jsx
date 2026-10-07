import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Play, Square, Users, ShieldCheck, ShieldAlert, Bell, Info,
  AlertTriangle, Activity, Video,
} from 'lucide-react'
import PageHeader from '../components/PageHeader.jsx'
import GlassCard, { CardHeader } from '../components/GlassCard.jsx'
import StatusPill from '../components/StatusPill.jsx'
import StatCard from '../components/StatCard.jsx'
import { api, formatTime } from '../lib/api.js'

const FRAME_INTERVAL_MS = 300   // pacing between processed frames (CPU-bound backend)
const CAPTURE_WIDTH = 640       // frames are sent to Python at this width

function camErrorMessage(err) {
  switch (err && err.name) {
    case 'NotAllowedError':
    case 'PermissionDeniedError':
      return 'Camera permission denied. Allow camera access in your browser, then press Start Camera again.'
    case 'NotFoundError':
    case 'DevicesNotFoundError':
      return 'No camera found on this device.'
    case 'NotReadableError':
      return 'Camera is already in use by another application.'
    default:
      return `Camera error: ${err && err.name ? err.name : 'unknown'}`
  }
}

function detectionColor(className) {
  const n = String(className || '').toLowerCase()
  if (n === 'person') return '#22d3ee'          // accent cyan
  if (n.startsWith('no-')) return '#fbbf24'     // warn amber for missing-PPE classes
  if (n === 'machinery' || n === 'vehicle') return '#fbbf24'
  return '#34d399'                              // compliant PPE classes (hardhat, mask, vest...)
}

export default function LiveCamera() {
  const [camState, setCamState] = useState('idle') // idle | starting | live | error
  const [camError, setCamError] = useState(null)
  const [session, setSession] = useState(null)     // real per-frame payload from Python
  const [liveEvents, setLiveEvents] = useState([]) // isolated outputs/live_camera log
  const [aspect, setAspect] = useState(4 / 3)

  const videoRef = useRef(null)
  const overlayRef = useRef(null)
  const offscreenRef = useRef(null)
  const streamRef = useRef(null)
  const timerRef = useRef(null)
  const runningRef = useRef(false)

  // ------------------------------------------------------------------
  // Overlay drawing (real backend detections, frame-coordinate space)
  // ------------------------------------------------------------------
  const drawOverlay = useCallback((detections, width, height) => {
    const canvas = overlayRef.current
    if (!canvas) return
    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width
      canvas.height = height
    }
    const ctx = canvas.getContext('2d')
    ctx.clearRect(0, 0, width, height)
    if (!detections) return
    for (const det of detections) {
      const [x1, y1, x2, y2] = det.bbox
      const color = detectionColor(det.class_name)
      ctx.strokeStyle = color
      ctx.lineWidth = 2
      ctx.strokeRect(x1, y1, x2 - x1, y2 - y1)
      const conf = det.confidence != null ? ` ${(det.confidence * 100).toFixed(0)}%` : ''
      const id = det.track_id != null ? ` id${det.track_id}` : ''
      const label = `${det.class_name}${conf}${id}`
      ctx.font = '600 11px ui-monospace, monospace'
      const tw = ctx.measureText(label).width
      ctx.fillStyle = color
      ctx.fillRect(x1, Math.max(0, y1 - 14), tw + 8, 14)
      ctx.fillStyle = '#0b1220'
      ctx.fillText(label, x1 + 4, Math.max(10, y1 - 3))
    }
  }, [])

  const clearOverlay = useCallback(() => {
    const canvas = overlayRef.current
    if (canvas) {
      const ctx = canvas.getContext('2d')
      ctx.clearRect(0, 0, canvas.width, canvas.height)
    }
  }, [])

  // ------------------------------------------------------------------
  // Frame loop: webcam -> JPEG -> POST /api/live/frame -> overlay + stats
  // ------------------------------------------------------------------
  const tick = useCallback(async () => {
    if (!runningRef.current) return
    try {
      const video = videoRef.current
      if (video && video.readyState >= 2 && video.videoWidth > 0) {
        const w = CAPTURE_WIDTH
        const h = Math.max(2, Math.round((video.videoHeight / video.videoWidth) * w))
        if (!offscreenRef.current) offscreenRef.current = document.createElement('canvas')
        const off = offscreenRef.current
        if (off.width !== w || off.height !== h) { off.width = w; off.height = h }
        const octx = off.getContext('2d')
        octx.drawImage(video, 0, 0, w, h)

        const blob = await new Promise((resolve) => off.toBlob(resolve, 'image/jpeg', 0.7))
        if (blob && runningRef.current) {
          const payload = await api.liveFrame(blob)
          if (payload && payload.running && !payload.busy && !payload.stopped) {
            setSession(payload)
            drawOverlay(payload.detections, w, h)
          } else if (payload && payload.busy) {
            // backend still inferring the previous frame — skip this tick
          } else if (payload && payload.error) {
            setSession((s) => ({ ...(s || {}), ...payload }))
          }
        }
      }
    } catch {
      // transient network/inference hiccup: keep the loop alive
    }
    if (runningRef.current) {
      timerRef.current = setTimeout(tick, FRAME_INTERVAL_MS)
    }
  }, [drawOverlay])

  const refreshLiveEvents = useCallback(() => {
    api.liveEvents().then(setLiveEvents)
  }, [])

  // ------------------------------------------------------------------
  // Start / Stop camera (browser permission + server session lifecycle)
  // ------------------------------------------------------------------
  const startCamera = useCallback(async () => {
    if (camState === 'starting' || camState === 'live') return
    setCamError(null)
    setCamState('starting')
    try {
      // 1. Server session: lazy-loads the EXISTING models/ppe_model.pt.
      const res = await api.liveStart()
      if (res == null) throw new Error('Backend /api/live/start unreachable — is the API server running?')

      // 2. Browser webcam via the normal permission system.
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' },
        audio: false,
      })
      streamRef.current = stream
      const video = videoRef.current
      video.srcObject = stream
      await video.play()

      const onMeta = () => {
        if (video.videoWidth > 0) setAspect(video.videoWidth / video.videoHeight)
      }
      if (video.readyState >= 1) onMeta()
      else video.addEventListener('loadedmetadata', onMeta, { once: true })

      // 3. Begin processing frames with the real backend pipeline.
      runningRef.current = true
      setCamState('live')
      refreshLiveEvents()
      timerRef.current = setTimeout(tick, FRAME_INTERVAL_MS)
    } catch (err) {
      // Camera failed: release the server session we just started.
      api.liveStop()
      setCamState('error')
      setCamError(camErrorMessage(err))
    }
  }, [camState, tick, refreshLiveEvents])

  const stopCamera = useCallback(async () => {
    runningRef.current = false
    if (timerRef.current) { clearTimeout(timerRef.current); timerRef.current = null }
    const stream = streamRef.current
    if (stream) {
      for (const track of stream.getTracks()) track.stop()  // releases the webcam
      streamRef.current = null
    }
    if (videoRef.current) videoRef.current.srcObject = null
    clearOverlay()
    setCamState('idle')
    try {
      const res = await api.liveStop()
      if (res) setSession(null)
    } catch { /* backend already gone */ }
    refreshLiveEvents()
  }, [clearOverlay, refreshLiveEvents])

  // Stop everything if the page is closed/left (camera must never stay on).
  useEffect(() => {
    return () => {
      runningRef.current = false
      if (timerRef.current) clearTimeout(timerRef.current)
      const stream = streamRef.current
      if (stream) for (const track of stream.getTracks()) track.stop()
      api.liveStop()
    }
  }, [])

  // Poll the isolated live log while the page is open.
  useEffect(() => {
    refreshLiveEvents()
    const id = setInterval(refreshLiveEvents, 5000)
    return () => clearInterval(id)
  }, [refreshLiveEvents])

  const ppeTone = session
    ? (session.ppe_status === 'VIOLATION' ? 'danger' : session.ppe_status === 'SAFE' ? 'safe' : 'slate')
    : 'slate'
  const nextConfirm = (() => {
    if (!session || session.current_violations === 0) return null
    const counts = session.persons.flatMap((p) => Object.values(p.persistence_counts || {}))
    if (!counts.length) return null
    const maxCount = Math.max(...counts)
    return { current: maxCount, target: session.persistence_frames, left: Math.max(0, session.persistence_frames - maxCount) }
  })()

  return (
    <div className="animate-fade-up">
      <PageHeader
        title="LIVE CAMERA — PROTOTYPE"
        subtitle="Laptop webcam → existing YOLOv8 pipeline → 8-frame persistence → isolated live alerts"
        right={<StatusPill tone="warn" pulse>Webcam prototype — no CCTV/RTSP</StatusPill>}
      />

      {/* Prototype disclaimer (exact wording required) */}
      <GlassCard className="mb-4 border border-warn/25 p-4">
        <p className="flex items-start gap-2 text-sm text-slate-300">
          <Info className="mt-0.5 h-4 w-4 shrink-0 text-warn" />
          <span>
            Laptop webcam is used as a prototype camera source. In deployment, this input can be replaced by an IP CCTV/RTSP stream.
          </span>
        </p>
      </GlassCard>

      {/* Controls */}
      <GlassCard className="mb-4 flex flex-wrap items-center gap-3 p-4">
        <button
          onClick={startCamera}
          disabled={camState === 'starting' || camState === 'live'}
          className="inline-flex items-center gap-2 rounded-xl bg-accent/15 px-4 py-2 text-sm font-semibold text-accent ring-1 ring-accent/30 transition hover:bg-accent/25 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Play className="h-4 w-4" /> Start Camera
        </button>
        <button
          onClick={stopCamera}
          disabled={camState !== 'live' && camState !== 'starting'}
          className="inline-flex items-center gap-2 rounded-xl bg-danger/10 px-4 py-2 text-sm font-semibold text-danger ring-1 ring-danger/30 transition hover:bg-danger/20 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Square className="h-4 w-4" /> Stop Camera
        </button>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <StatusPill tone={camState === 'live' ? 'safe' : camState === 'error' ? 'danger' : 'slate'} pulse={camState === 'live'}>
            Camera: {camState === 'live' ? 'LIVE' : camState.toUpperCase()}
          </StatusPill>
          {camState === 'live' && session && (
            <StatusPill tone={session.last_error ? 'danger' : 'accent'} pulse>
              <Activity className="h-3 w-3" />
              {session.last_error ? 'Processing error' : `Inference ${session.latency_ms ?? '—'} ms`}
            </StatusPill>
          )}
        </div>
      </GlassCard>

      {camError && (
        <GlassCard className="mb-4 border border-danger/30 p-4">
          <p className="flex items-start gap-2 text-sm text-danger">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            {camError}
          </p>
        </GlassCard>
      )}

      {/* Violation banner — shown only after a violation is CONFIRMED (8 frames) */}
      {session && session.violation_active && (
        <div className="mb-4 animate-fade-up rounded-2xl border border-danger/40 bg-danger/10 p-4 shadow-[0_0_40px_rgba(239,68,68,0.15)]">
          <p className="flex flex-wrap items-center gap-2 text-lg font-bold text-danger">
            ⚠️ PPE VIOLATION DETECTED
          </p>
          <p className="mt-1 text-sm text-slate-300">
            {session.last_alert?.missing?.length
              ? `Missing: ${session.last_alert.missing.join(', ')} · confidence ${(session.last_alert.confidence * 100).toFixed(1)}% · alert saved to outputs/live_camera/`
              : 'Confirmed by 8-frame persistence rule.'}
          </p>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Webcam + overlay */}
        <GlassCard className="overflow-hidden lg:col-span-2">
          <CardHeader
            icon={Video}
            title="LIVE WEBCAM"
            subtitle="browser camera → JPEG frames → Python YOLOv8 inference"
            right={<StatusPill tone={camState === 'live' ? 'safe' : 'slate'} pulse={camState === 'live'}>
              {camState === 'live' ? 'Processing' : 'Idle'}
            </StatusPill>}
          />
          <div className="p-4">
            <div className="relative mx-auto overflow-hidden rounded-xl bg-black ring-1 ring-white/[0.06]" style={{ aspectRatio: String(aspect) }}>
              <video
                ref={videoRef}
                className="absolute inset-0 h-full w-full object-contain"
                muted playsInline autoPlay
              />
              <canvas ref={overlayRef} className="pointer-events-none absolute inset-0 h-full w-full" />
              {camState !== 'live' && (
                <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-center">
                  <Video className="h-8 w-8 text-slate-600" />
                  <p className="text-sm text-slate-500">
                    {camState === 'starting' ? 'Starting model + requesting camera…' : 'Camera stopped — press Start Camera'}
                  </p>
                </div>
              )}
            </div>
            {camState === 'live' && session && (
              <p className="mt-3 text-center font-mono text-[11px] text-slate-500">
                {session.processed_frames} frames processed · {session.persons_detected} person(s) in frame ·
                persistence rule: {session.persistence_frames} consecutive frames
                {nextConfirm && ` · next confirmation in ${nextConfirm.left} frame(s) (${nextConfirm.current}/${nextConfirm.target})`}
              </p>
            )}
          </div>
        </GlassCard>

        {/* Live stats + recent live alerts */}
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <StatCard icon={Users} label="Persons Detected" value={session ? session.persons_detected : '—'} tone="accent" />
            <StatCard
              icon={session?.ppe_status === 'VIOLATION' ? ShieldAlert : ShieldCheck}
              label="PPE Status"
              value={session ? session.ppe_status : '—'}
              tone={ppeTone}
            />
            <StatCard icon={ShieldAlert} label="Current Violations" value={session ? session.current_violations : '—'} tone={session?.current_violations > 0 ? 'danger' : 'slate'} />
            <StatCard icon={Bell} label="Alerts (session)" value={session ? session.session_alerts : '—'} tone="accent" />
          </div>

          <GlassCard>
            <CardHeader icon={Bell} title="Live Violations" subtitle="isolated store: outputs/live_camera/" />
            <div className="divide-y divide-white/[0.04]">
              {liveEvents.length === 0 && (
                <p className="px-5 py-6 text-sm text-slate-500">
                  No live violations confirmed yet — remove your helmet/vest in view of the camera and hold still for 8 processed frames.
                </p>
              )}
              {liveEvents.slice(-5).reverse().map((ev, i) => (
                <div key={`${ev.timestamp}-${i}`} className="flex items-center gap-3 px-5 py-3">
                  {ev.snapshot && (
                    <img
                      src={api.liveSnapshotUrl(ev.snapshot.split(/[\\/]/).pop())}
                      alt="live violation snapshot"
                      className="h-12 w-16 rounded-lg object-cover ring-1 ring-white/10"
                    />
                  )}
                  <div className="min-w-0">
                    <p className="truncate text-xs font-semibold text-slate-200">
                      {ev.missing ? ev.missing.join(' + ') : ev.violation_type}
                    </p>
                    <p className="text-[11px] text-slate-500">
                      {formatTime(ev.timestamp)}
                      {ev.confidence != null && ` · conf ${(ev.confidence * 100).toFixed(1)}%`}
                      {ev.track_id != null && ` · id${ev.track_id}`}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </GlassCard>
        </div>
      </div>
    </div>
  )
}
