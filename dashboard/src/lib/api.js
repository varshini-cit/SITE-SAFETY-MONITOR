const BASE = '/api'

async function getJson(path, fallback = null) {
  try {
    const res = await fetch(`${BASE}${path}`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return await res.json()
  } catch (err) {
    console.error(`API ${path} failed:`, err)
    return fallback
  }
}

export const api = {
  health: () => getJson('/health'),
  summary: () => getJson('/summary'),
  events: () => getJson('/events', []),
  snapshots: () => getJson('/snapshots', []),
  videos: () => getJson('/videos', []),
  training: () => getJson('/training'),
  dataset: () => getJson('/dataset'),
  testEval: () => getJson('/test-eval'),
  // ---- LIVE CAMERA — PROTOTYPE (isolated outputs/live_camera/ area) ----
  liveStart: () => postJson('/live/start'),
  liveStop: () => postJson('/live/stop'),
  liveFrame: async (blob) => {
    try {
      const res = await fetch(`${BASE}/live/frame`, {
        method: 'POST',
        headers: { 'Content-Type': 'image/jpeg' },
        body: blob,
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      return await res.json()
    } catch {
      return null // transient hiccup: the frame loop simply retries
    }
  },
  liveStatus: () => getJson('/live/status', { running: false }),
  liveEvents: () => getJson('/live/events', []),
  liveSnapshotUrl: (name) => `${BASE}/live/snapshots/${encodeURIComponent(name)}`,
}

async function postJson(path) {
  try {
    const res = await fetch(`${BASE}${path}`, { method: 'POST' })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return await res.json()
  } catch (err) {
    console.error(`API POST ${path} failed:`, err)
    return null
  }
}

export function formatBytes(bytes) {
  if (bytes == null) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function formatTime(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch {
    return iso
  }
}

export function formatDate(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleDateString([], { month: 'short', day: 'numeric' })
  } catch {
    return iso
  }
}

export function pct(v, digits = 1) {
  if (v == null) return '—'
  return `${(v * 100).toFixed(digits)}%`
}
