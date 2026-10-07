import { useId } from 'react'

/**
 * Lightweight dependency-free area/line chart (inline SVG).
 * series: [{ label, color, points: [number, ...] }]
 * All series must share the same x-length.
 */
export default function AreaChart({ series = [], height = 220, yMax = null, yMin = 0, formatY }) {
  const uid = useId().replace(/[:]/g, '')
  const W = 600
  const H = height
  const PAD_L = 44
  const PAD_R = 12
  const PAD_T = 12
  const PAD_B = 24

  const n = Math.max(...series.map((s) => s.points.length), 0)
  if (n === 0) return null

  const max = yMax ?? Math.max(...series.flatMap((s) => s.points)) * 1.08
  const min = yMin
  const x = (i) => PAD_L + (i / Math.max(n - 1, 1)) * (W - PAD_L - PAD_R)
  const y = (v) => PAD_T + (1 - (v - min) / (max - min || 1)) * (H - PAD_T - PAD_B)

  const yTicks = 4
  const tickVals = Array.from({ length: yTicks + 1 }, (_, i) => min + ((max - min) / yTicks) * i)

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img">
      <defs>
        {series.map((s, si) => (
          <linearGradient key={si} id={`${uid}-g${si}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={s.color} stopOpacity="0.28" />
            <stop offset="100%" stopColor={s.color} stopOpacity="0" />
          </linearGradient>
        ))}
      </defs>

      {/* grid + y labels */}
      {tickVals.map((tv, i) => (
        <g key={i}>
          <line
            x1={PAD_L}
            x2={W - PAD_R}
            y1={y(tv)}
            y2={y(tv)}
            stroke="rgba(255,255,255,0.05)"
            strokeDasharray="3 5"
          />
          <text
            x={PAD_L - 8}
            y={y(tv) + 3}
            textAnchor="end"
            className="fill-slate-500"
            style={{ fontSize: 9, fontFamily: 'JetBrains Mono, monospace' }}
          >
            {formatY ? formatY(tv) : tv.toFixed(2)}
          </text>
        </g>
      ))}

      {/* series */}
      {series.map((s, si) => {
        const pts = s.points.map((v, i) => `${x(i)},${y(v)}`).join(' ')
        const area = `${PAD_L},${y(min)} ${pts} ${x(n - 1)},${y(min)}`
        return (
          <g key={si}>
            <polygon points={area} fill={`url(#${uid}-g${si})`} />
            <polyline
              points={pts}
              fill="none"
              stroke={s.color}
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            {s.points.map((v, i) => (
              <circle key={i} cx={x(i)} cy={y(v)} r="2.5" fill={s.color} opacity="0.9" />
            ))}
          </g>
        )
      })}

      {/* x labels: epochs */}
      {n <= 12 &&
        Array.from({ length: n }, (_, i) => (
          <text
            key={i}
            x={x(i)}
            y={H - 6}
            textAnchor="middle"
            className="fill-slate-500"
            style={{ fontSize: 9, fontFamily: 'JetBrains Mono, monospace' }}
          >
            {i + 1}
          </text>
        ))}
    </svg>
  )
}
