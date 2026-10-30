import type { LoadedRun, RunIndex } from '../types'
import { durationBetween, fmtIso, fmtUsd, kindLabel } from '../lib/format'
import { VerdictBadge } from './VerdictBadge'
import { Pill } from './ui'

const NAV: [string, string][] = [
  ['#player', 'Player'],
  ['#residual', 'Residual E(t)'],
  ['#contract', 'Contract'],
  ['#diagnosis', 'Diagnosis'],
  ['#provenance', 'Provenance'],
]

export function TopBar({ index, selected, onSelect, run, loading }: { index: RunIndex | null; selected: string | null; onSelect: (id: string) => void; run: LoadedRun | null; loading: boolean }) {
  const m = run?.manifest ?? null
  const lastPass = m?.passes[m.passes.length - 1] ?? null
  return (
    <header className="sticky top-0 z-20 border-b border-line bg-plane/90 backdrop-blur">
      <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-x-5 gap-y-2 px-5 py-2.5">
        <div className="flex items-center gap-3">
          <svg width="28" height="28" viewBox="0 0 32 32" aria-hidden="true">
            <rect width="32" height="32" rx="6" fill="#131a29" />
            <path d="M6 22 L14 22 L14 12 L26 12" fill="none" stroke="#4ade80" strokeWidth="3" />
            <path d="M6 16 L26 16" stroke="#f472b6" strokeWidth="2" strokeDasharray="3 3" />
          </svg>
          <div className="leading-tight">
            <div className="text-sm font-bold tracking-wide text-ink">KINETIC-ORACLE</div>
            <div className="text-[11px] text-ink-3">ProprioSAM · telemetry dashboard · offline bundles</div>
          </div>
        </div>
        <label className="flex items-center gap-2 text-xs text-ink-2">
          run
          <select
            value={selected ?? ''}
            onChange={(ev) => onSelect(ev.target.value)}
            className="mono max-w-[26rem] rounded-md border border-line-2 bg-card-2 px-2 py-1 text-xs text-ink"
            aria-label="select run bundle"
          >
            {(index?.runs ?? []).map((r) => (
              <option key={r.run_id} value={r.run_id}>
                {r.run_id} · {kindLabel(r.kind)} · {r.final_verdict ?? r.status}
              </option>
            ))}
          </select>
        </label>
        {m && (
          <div className="flex flex-wrap items-center gap-2">
            <Pill tone="info">{kindLabel(m.kind)}</Pill>
            <Pill tone={m.status === 'COMPLETE' ? 'ok' : 'warn'}>{m.status}</Pill>
            <Pill title={fmtIso(m.created_at)}>
              {fmtIso(m.created_at)} · {durationBetween(m.created_at, m.finished_at)}
            </Pill>
            <Pill>
              {m.passes.length} pass{m.passes.length === 1 ? '' : 'es'} · {m.repair_turns.length} repair turn{m.repair_turns.length === 1 ? '' : 's'} · {fmtUsd(m.spend.est_cost_usd, 3)}
            </Pill>
          </div>
        )}
        <div className="ml-auto flex flex-wrap items-center gap-3">
          {m && lastPass && (
            <VerdictBadge status={lastPass.verification_status} tFail={lastPass.t_fail} label={`final verdict (pass ${lastPass.index})`} size="sm" extra={m.kind === 'closed_loop' ? `manifest: ${m.final_verdict}` : undefined} />
          )}
          {loading && <span className="text-xs text-ink-3">loading…</span>}
        </div>
      </div>
      <nav className="mx-auto flex max-w-[1600px] flex-wrap gap-4 px-5 pb-2 text-xs">
        {NAV.map(([href, label]) => (
          <a key={href} href={href} className="text-ink-3 hover:text-ink">
            {label}
          </a>
        ))}
        <span className="ml-auto text-[11px] text-ink-3">space play/pause · ← → step (shift ×5) · Home/End</span>
      </nav>
    </header>
  )
}
