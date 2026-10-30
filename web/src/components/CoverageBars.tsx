import type { LoadedPass } from '../types'
import { fmtPct } from '../lib/format'
import { CONCEPT, INK } from '../lib/theme'

/** Per-concept coverage vs the contract's gates. Below-gate rows carry an icon + text, never colour alone. */
export function CoverageBars({ pass }: { pass: LoadedPass }) {
  const c = pass.verification?.coverage ?? {}
  const minTotal = c.min_total_coverage ?? 0
  const minWindow = c.min_window_coverage ?? 0
  const win = c.critical_window ?? [0, 0]
  const approach = pass.verification?.approach
  const rows: { label: string; color: string; total: number | undefined; window: number | undefined }[] = [
    { label: 'mover', color: CONCEPT.mover, total: c.mover_total, window: c.mover_window },
    { label: 'barrier', color: CONCEPT.barrier, total: c.barrier_total, window: c.barrier_window },
    { label: 'both', color: INK.secondary, total: c.both_total, window: c.both_window },
  ]
  return (
    <div className="space-y-1.5">
      <div className="grid grid-cols-[3.6rem_1fr_1fr] gap-x-3 text-[10px] uppercase tracking-wider text-ink-3">
        <span />
        <span>
          total · gate ≥ {fmtPct(minTotal)}
        </span>
        <span>
          window [{win[0]},{win[1]}] · gate ≥ {fmtPct(minWindow)}
        </span>
      </div>
      {rows.map((r) => (
        <div key={r.label} className="grid grid-cols-[3.6rem_1fr_1fr] items-center gap-x-3">
          <span className="inline-flex items-center gap-1.5 text-xs text-ink-2">
            <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: r.color }} />
            {r.label}
          </span>
          <Bar value={r.total} gate={r.label === 'both' ? null : minTotal} />
          <Bar value={r.window} gate={r.label === 'both' ? minWindow : null} />
        </div>
      ))}
      <p className="text-[10px] leading-snug text-ink-3">gates: each concept ≥ {fmtPct(minTotal)} of all frames; both tracked in ≥ {fmtPct(minWindow)} of the critical window. Unmet ⇒ INCONCLUSIVE, never PASS.</p>
      {approach && (
        <p className="text-xs text-ink-2">
          {approach.exercised ? 'contract exercised' : '⚠ contract not exercised'}
          <span className="mono num text-ink-3">
            {' '}· closest approach {fmtPx(approach.max_E_px)}, needed ≥ {fmtPx(approach.required_max_E_px)} ({approach.approach_body_heights} body height)
          </span>
        </p>
      )}
    </div>
  )
}

function fmtPx(v: number | null): string {
  return v == null ? 'n/a' : `${v > 0 ? '+' : ''}${Math.round(v)} px`
}

function Bar({ value, gate }: { value: number | undefined; gate: number | null }) {
  if (value == null) return <span className="text-xs text-ink-3">—</span>
  const below = gate != null && value < gate
  return (
    <div className="flex items-center gap-2">
      <div className="relative h-2.5 flex-1 overflow-hidden rounded-sm bg-line/70">
        <div className="absolute inset-y-0 left-0 rounded-r-sm" style={{ width: `${Math.min(100, value * 100)}%`, background: below ? '#fab219' : '#8b94a7' }} />
        {gate != null && <div className="absolute inset-y-0 w-px bg-ink" style={{ left: `${gate * 100}%` }} title={`gate ${fmtPct(gate)}`} />}
      </div>
      <span className="mono num w-14 text-right text-xs text-ink">
        {below ? '⚠ ' : ''}
        {fmtPct(value, 1)}
      </span>
    </div>
  )
}
