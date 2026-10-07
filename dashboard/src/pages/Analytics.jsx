import { useEffect, useState } from 'react'
import { BarChart3, LineChart, Layers, Target, Clock } from 'lucide-react'
import PageHeader from '../components/PageHeader.jsx'
import GlassCard, { CardHeader } from '../components/GlassCard.jsx'
import StatusPill from '../components/StatusPill.jsx'
import AreaChart from '../components/AreaChart.jsx'
import { api, pct } from '../lib/api.js'

const COLORS = { map50: '#22d3ee', precision: '#34d399', recall: '#fbbf24' }

export default function Analytics() {
  const [training, setTraining] = useState(null)
  const [dataset, setDataset] = useState(null)

  useEffect(() => {
    api.training().then(setTraining)
    api.dataset().then(setDataset)
  }, [])

  const epochs = training?.epochs || []
  const perClass = (training?.per_class_valid || []).filter((r) => r.class !== 'all')

  return (
    <div className="animate-fade-up">
      <PageHeader
        title="Analytics"
        subtitle="Real training telemetry from runs/detect/ppe_smoke — no synthetic numbers"
        right={<StatusPill tone="accent">{training?.epochs_completed ?? '—'} epochs completed</StatusPill>}
      />

      {/* Headline training stats */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatMini label="Best mAP@0.5 (valid)" value={pct(Math.max(...epochs.map((e) => e.map50), 0))} tone="accent" />
        <StatMini label="Final Precision (valid)" value={pct(epochs.at(-1)?.precision)} tone="safe" />
        <StatMini label="Final Recall (valid)" value={pct(epochs.at(-1)?.recall)} tone="warn" />
        <StatMini
          label="Training Duration"
          value={training?.duration_hours != null ? `${training.duration_hours.toFixed(2)} h` : '—'}
          tone="slate"
          icon={Clock}
        />
      </div>

      {/* Training curves */}
      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-2">
        <GlassCard>
          <CardHeader
            icon={LineChart}
            title="Accuracy Metrics per Epoch"
            subtitle="results.csv — validation on the 114-image valid split"
            right={
              <div className="flex gap-3 text-[10px] font-medium text-slate-400">
                <Legend color={COLORS.map50} label="mAP50" />
                <Legend color={COLORS.precision} label="Precision" />
                <Legend color={COLORS.recall} label="Recall" />
              </div>
            }
          />
          <div className="p-4">
            {epochs.length > 0 ? (
              <AreaChart
                height={230}
                yMax={1}
                formatY={(v) => `${Math.round(v * 100)}%`}
                series={[
                  { label: 'mAP50', color: COLORS.map50, points: epochs.map((e) => e.map50) },
                  { label: 'Precision', color: COLORS.precision, points: epochs.map((e) => e.precision) },
                  { label: 'Recall', color: COLORS.recall, points: epochs.map((e) => e.recall) },
                ]}
              />
            ) : (
              <Empty label="No training results found" />
            )}
          </div>
        </GlassCard>

        <GlassCard>
          <CardHeader
            icon={LineChart}
            title="Training Losses per Epoch"
            subtitle="lower is better"
            right={
              <div className="flex gap-3 text-[10px] font-medium text-slate-400">
                <Legend color="#f87171" label="box loss" />
                <Legend color="#a78bfa" label="cls loss" />
              </div>
            }
          />
          <div className="p-4">
            {epochs.length > 0 ? (
              <AreaChart
                height={230}
                series={[
                  { label: 'box', color: '#f87171', points: epochs.map((e) => e.box_loss) },
                  { label: 'cls', color: '#a78bfa', points: epochs.map((e) => e.cls_loss) },
                ]}
              />
            ) : (
              <Empty label="No training results found" />
            )}
          </div>
        </GlassCard>
      </div>

      {/* Per-class table */}
      <GlassCard className="mt-4 overflow-hidden">
        <CardHeader
          icon={Layers}
          title="Per-Class Validation Results"
          subtitle="final validation table from the ppe_smoke run"
        />
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-white/[0.06] text-[11px] uppercase tracking-wider text-slate-500">
                <th className="px-5 py-3 font-semibold">Class</th>
                <th className="px-5 py-3 font-semibold">Images</th>
                <th className="px-5 py-3 font-semibold">Instances</th>
                <th className="px-5 py-3 font-semibold">Precision</th>
                <th className="px-5 py-3 font-semibold">Recall</th>
                <th className="px-5 py-3 font-semibold">mAP@0.5</th>
                <th className="px-5 py-3 font-semibold">mAP@0.5:0.95</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.04]">
              {training?.overall_valid && (
                <tr className="bg-accent/[0.04] font-semibold text-white">
                  <td className="px-5 py-3">all</td>
                  <td className="px-5 py-3 font-mono">{training.overall_valid.images}</td>
                  <td className="px-5 py-3 font-mono">{training.overall_valid.instances}</td>
                  <td className="px-5 py-3 font-mono">{training.overall_valid.precision.toFixed(3)}</td>
                  <td className="px-5 py-3 font-mono">{training.overall_valid.recall.toFixed(3)}</td>
                  <td className="px-5 py-3 font-mono text-accent">{training.overall_valid.map50.toFixed(3)}</td>
                  <td className="px-5 py-3 font-mono">{training.overall_valid.map50_95.toFixed(3)}</td>
                </tr>
              )}
              {perClass.map((r) => (
                <tr key={r.class} className="text-slate-300 transition hover:bg-white/[0.02]">
                  <td className="px-5 py-3 font-medium text-slate-200">{r.class}</td>
                  <td className="px-5 py-3 font-mono">{r.images}</td>
                  <td className="px-5 py-3 font-mono">{r.instances}</td>
                  <td className="px-5 py-3 font-mono">{r.precision.toFixed(3)}</td>
                  <td className="px-5 py-3 font-mono">{r.recall.toFixed(3)}</td>
                  <td className="px-5 py-3 font-mono">{r.map50.toFixed(3)}</td>
                  <td className="px-5 py-3 font-mono">{r.map50_95.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {perClass.length === 0 && (
            <p className="px-5 py-6 text-sm text-slate-500">Per-class table not available.</p>
          )}
        </div>
      </GlassCard>

      {/* Dataset composition */}
      <GlassCard className="mt-4">
        <CardHeader icon={Target} title="Dataset Composition" subtitle="real image counts from data/dataset.yaml" />
        <div className="grid grid-cols-1 gap-4 p-5 sm:grid-cols-3">
          {dataset?.splits &&
            Object.entries(dataset.splits).map(([split, info]) => (
              <div key={split} className="rounded-xl bg-white/[0.03] p-4 ring-1 ring-white/[0.06]">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">{split}</p>
                <p className="mt-1 text-2xl font-bold text-white">{info.images}</p>
                <p className="mt-0.5 truncate font-mono text-[10px] text-slate-600">{info.path}</p>
              </div>
            ))}
        </div>
        <div className="border-t border-white/[0.05] px-5 py-4">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
            Classes ({dataset?.nc ?? 10})
          </p>
          <div className="flex flex-wrap gap-1.5">
            {(dataset?.classes || []).map((c) => (
              <StatusPill key={c} tone="slate">{c}</StatusPill>
            ))}
          </div>
        </div>
      </GlassCard>
    </div>
  )
}

function StatMini({ label, value, tone = 'accent', icon: Icon }) {
  const tones = {
    accent: 'text-accent',
    safe: 'text-safe',
    warn: 'text-warn',
    slate: 'text-slate-300',
  }
  return (
    <GlassCard hover className="animate-fade-up p-4">
      <div className="flex items-center justify-between">
        <p className="text-[11px] font-medium uppercase tracking-wider text-slate-500">{label}</p>
        {Icon && <Icon className="h-4 w-4 text-slate-500" />}
      </div>
      <p className={`mt-2 text-2xl font-bold ${tones[tone]}`}>{value}</p>
    </GlassCard>
  )
}

function Legend({ color, label }) {
  return (
    <span className="flex items-center gap-1">
      <span className="h-1.5 w-4 rounded-full" style={{ background: color }} />
      {label}
    </span>
  )
}

function Empty({ label }) {
  return <p className="py-10 text-center text-sm text-slate-500">{label}</p>
}
