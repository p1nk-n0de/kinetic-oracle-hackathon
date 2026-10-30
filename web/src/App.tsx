import { useCallback, useEffect, useState } from 'react'
import type { LoadedRun, RunIndex } from './types'
import { loadIndex, loadRun } from './lib/load'
import { player } from './lib/playerStore'
import { VERDICT_CAPTION, kindLabel } from './lib/format'
import { TopBar } from './components/TopBar'
import { SplitPlayer } from './components/SplitPlayer'
import { ResidualChart } from './components/ResidualChart'
import { ContractPanel } from './components/ContractPanel'
import { DiagnosisPanel } from './components/DiagnosisPanel'
import { ProvenancePanel } from './components/ProvenancePanel'
import { VerdictBadge } from './components/VerdictBadge'
import { Pill } from './components/ui'

function runFromHash(): string | null {
  const m = /run=([^&]+)/.exec(window.location.hash)
  return m && m[1] ? decodeURIComponent(m[1]) : null
}

export default function App() {
  const [index, setIndex] = useState<RunIndex | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [run, setRun] = useState<LoadedRun | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadIndex()
      .then((idx) => {
        setIndex(idx)
        const wanted = runFromHash()
        const first = idx.runs[0]?.run_id ?? null
        setSelected(wanted && idx.runs.some((r) => r.run_id === wanted) ? wanted : first)
        if (!first) {
          setLoading(false)
          setError('index.json lists no runs. Export a bundle with `python -m scripts.export_bundle_for_web`.')
        }
      })
      .catch((e: Error) => {
        setError(e.message)
        setLoading(false)
      })
  }, [])

  useEffect(() => {
    if (!selected) return
    let cancelled = false
    setLoading(true)
    setError(null)
    loadRun(selected)
      .then((r) => {
        if (cancelled) return
        const fc = r.contract?.frame_count ?? r.passes[0]?.record.frame_count ?? 80
        player.configure(fc, r.contract?.fps ?? 20)
        setRun(r)
        window.history.replaceState(null, '', `#run=${encodeURIComponent(selected)}`)
      })
      .catch((e: Error) => {
        if (!cancelled) setError(`${selected}: ${e.message}`)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [selected])

  const onSelect = useCallback((id: string) => {
    player.pause()
    setSelected(id)
  }, [])

  return (
    <div className="min-h-screen bg-plane text-ink">
      <TopBar index={index} selected={selected} onSelect={onSelect} run={run} loading={loading} />
      <main className="mx-auto max-w-[1600px] space-y-6 px-5 py-6">
        {error && <div className="rounded-lg border border-bad/60 bg-bad/10 px-4 py-3 text-sm text-ink">{error}</div>}
        {!run && !error && <p className="text-sm text-ink-3">Loading bundle…</p>}
        {run && (
          <>
            <RunSummary run={run} />
            <SplitPlayer run={run} />
            <ResidualChart run={run} />
            <ContractPanel run={run} />
            <DiagnosisPanel run={run} />
            <ProvenancePanel run={run} />
          </>
        )}
      </main>
      <footer className="mx-auto max-w-[1600px] px-5 pb-8 text-[11px] text-ink-3">
        Static dashboard over committed run bundles (web/public/runs). No network calls at runtime; nothing here calls any model. All verdicts are {VERDICT_CAPTION}.
      </footer>
    </div>
  )
}

function RunSummary({ run }: { run: LoadedRun }) {
  const m = run.manifest
  const first = m.passes[0]
  const last = m.passes[m.passes.length - 1]
  const story =
    m.kind === 'closed_loop'
      ? `The agent drove the player through Godot MCP and its tool reported success. The verifier watched the rendered clip: pass 1 ${first?.verification_status ?? '—'}${first?.t_fail != null ? ` at frame ${first.t_fail}` : ''}. ${m.repair_turns.length ? `Muse Spark then diagnosed the scene blind (${m.repair_turns.reduce((n, t) => n + t.tool_calls, 0)} tool calls, ${m.repair_turns.reduce((n, t) => n + t.patches.length, 0)} patch) and the patched game was re-captured: pass ${last?.index} ${last?.verification_status}.` : ''}`
      : `Two pre-captured clips were tracked by SAM 3.1 and scored under one frozen contract: ${m.passes.map((p) => `${p.label} ${p.verification_status}${p.t_fail != null ? ` @${p.t_fail}` : ''}`).join(', ')}.`
  return (
    <section className="flex flex-wrap items-start justify-between gap-4 rounded-xl border border-line bg-card/70 px-5 py-3">
      <div className="min-w-0 max-w-3xl">
        <h1 className="mono text-sm font-semibold text-ink">
          {m.run_id} <Pill tone="neutral">{kindLabel(m.kind)}</Pill>
        </h1>
        <p className="mt-1 text-xs leading-relaxed text-ink-2">{story}</p>
        <p className="mt-1 text-[11px] text-ink-3">manifest.verdict_basis: “{m.verdict_basis}”</p>
      </div>
      <div className="flex flex-wrap items-start gap-4">
        {m.passes.map((p) => (
          <VerdictBadge key={p.index} status={p.verification_status} tFail={p.t_fail} label={`pass ${p.index} · ${p.label}`} size="sm" />
        ))}
      </div>
    </section>
  )
}
