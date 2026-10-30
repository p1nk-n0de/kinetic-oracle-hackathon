import type { AssistantItem, LoadedRun, LoadedTurn, ToolItem, Usage } from '../types'
import { fmtUsd } from '../lib/format'
import { VerdictBadge } from './VerdictBadge'
import { Check, Collapsible, Empty, Hash, JsonView, Kv, Pill, Section, SubHead } from './ui'

function usageText(u: Usage | undefined): string {
  if (!u) return ''
  const parts: string[] = []
  if (u.input_tokens != null) parts.push(`in ${u.input_tokens.toLocaleString()}${u.input_tokens_details?.cached_tokens ? ` (${u.input_tokens_details.cached_tokens.toLocaleString()} cached)` : ''}`)
  if (u.output_tokens != null) parts.push(`out ${u.output_tokens.toLocaleString()}${u.output_tokens_details?.reasoning_tokens ? ` (${u.output_tokens_details.reasoning_tokens.toLocaleString()} reasoning)` : ''}`)
  return parts.join(' · ')
}

function shortArgs(args: unknown, max = 90): string {
  const s = typeof args === 'string' ? args : JSON.stringify(args)
  if (!s || s === '{}') return ''
  return s.length > max ? `${s.slice(0, max)}…` : s
}

function DiffView({ diff }: { diff: string }) {
  return (
    <pre className="block max-h-96 overflow-auto">
      {diff.split('\n').map((line, i) => {
        let cls = 'text-ink-2'
        if (line.startsWith('+++') || line.startsWith('---')) cls = 'text-ink-3'
        else if (line.startsWith('@@')) cls = 'text-pass2'
        else if (line.startsWith('+')) cls = 'text-ok'
        else if (line.startsWith('-')) cls = 'text-bad'
        return (
          <span key={i} className={`block ${cls}`}>
            {line || ' '}
          </span>
        )
      })}
    </pre>
  )
}

function Timeline({ turn }: { turn: LoadedTurn }) {
  let step = 0
  return (
    <ol className="relative ml-2 space-y-3 border-l border-line pl-5">
      {turn.transcript.map((item, i) => {
        if (item.type === 'assistant') {
          step += 1
          return <AssistantStep key={i} item={item} step={step} model={turn.record.model} />
        }
        return <ToolStep key={i} item={item} />
      })}
      {turn.transcript.length === 0 && <li className="text-xs text-ink-3">transcript.json missing</li>}
    </ol>
  )
}

function AssistantStep({ item, step, model }: { item: AssistantItem; step: number; model: string }) {
  return (
    <li className="relative">
      <span className="absolute -left-[26px] top-1.5 h-2.5 w-2.5 rounded-full bg-pass2" aria-hidden="true" />
      <div className="rounded-lg border border-line bg-card-2/60 px-3 py-2">
        <div className="mb-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-ink-3">
          <span className="font-semibold text-ink-2">
            {model} · response {step}
          </span>
          {item.request_id && (
            <span>
              request <Hash value={item.request_id} n={36} />
            </span>
          )}
          {item.status && <span>status {item.status}</span>}
          {item.usage && <span className="num">{usageText(item.usage)}</span>}
        </div>
        {item.text && <p className="mb-1.5 whitespace-pre-wrap text-xs italic leading-relaxed text-ink-2">“{item.text}”</p>}
        {item.calls.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {item.calls.map((c, j) => (
              <span key={j} className="mono inline-flex max-w-full items-center gap-1 rounded border border-line-2 bg-surface px-1.5 py-0.5 text-[11px] text-ink">
                <span className="text-pass2">▸</span> {c.name}
                <span className="truncate text-ink-3">({shortArgs(c.arguments)})</span>
              </span>
            ))}
          </div>
        )}
        {!item.text && item.calls.length === 0 && <p className="text-[11px] text-ink-3">(empty response)</p>}
      </div>
    </li>
  )
}

function ToolStep({ item }: { item: ToolItem }) {
  const isPatch = item.name === 'patch_source'
  return (
    <li className="relative">
      <span className={`absolute -left-[26px] top-1.5 h-2.5 w-2.5 rounded-sm ${isPatch ? 'bg-pass1' : 'bg-ink-3'}`} aria-hidden="true" />
      <details className="rounded-lg border border-line bg-surface/40">
        <summary className="px-3 py-2 text-xs text-ink-2 hover:text-ink">
          <span className="mono text-ink">{item.name}</span>
          <span className="mono ml-2 text-ink-3">{shortArgs(item.arguments, 120)}</span>
          <span className="ml-2 text-[11px] text-ink-3">· tool result (allowlisted adapter, read-only unless patch_source)</span>
        </summary>
        <div className="space-y-2 border-t border-line px-3 py-2">
          {shortArgs(item.arguments) && (
            <div>
              <p className="mb-1 text-[11px] uppercase tracking-wider text-ink-3">arguments</p>
              <JsonView value={item.arguments} maxChars={2000} />
            </div>
          )}
          <div>
            <p className="mb-1 text-[11px] uppercase tracking-wider text-ink-3">output returned to Muse</p>
            <JsonView value={item.output} maxChars={3000} />
          </div>
        </div>
      </details>
    </li>
  )
}

function TurnView({ run, turn }: { run: LoadedRun; turn: LoadedTurn }) {
  const r = turn.record
  const p = turn.prompt
  const ac = r.anti_cheat ?? {}
  const found = p?.banned_terms_found ?? ac.banned_terms_found ?? []
  const checked = p?.banned_terms_checked?.length ?? ac.banned_terms_checked ?? 0
  const afterPass = run.passes.find((x) => x.record.index === r.turn + 1) ?? null
  const promptHashAgrees = p ? p.prompt_sha256 === ac.prompt_sha256 : null
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2">
        <Pill tone="info">turn {r.turn}</Pill>
        <Pill>
          model <span className="mono">{r.model}</span>
          {r.escalated ? ' · escalated' : ''}
        </Pill>
        <Pill>{r.tool_calls} tool calls</Pill>
        <Pill>{r.patches.length} patch{r.patches.length === 1 ? '' : 'es'}</Pill>
        <Pill>est {fmtUsd(r.est_cost_usd)}</Pill>
        <Pill tone={found.length ? 'bad' : 'ok'} title="banned-term screen of the outgoing prompt">
          anti-cheat screen: {found.length ? `${found.length} banned term(s) FOUND` : `0 of ${checked} banned terms present`}
        </Pill>
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <div className="min-w-0 space-y-4">
          <div>
            <SubHead
              right={
                <span className="text-[11px] text-ink-3">
                  prompt sha256 <Hash value={p?.prompt_sha256 ?? ac.prompt_sha256} n={16} /> · manifest agrees <Check ok={promptHashAgrees} />
                </span>
              }
            >
              Evidence prompt — the exact user message Muse saw (prompt.json → user)
            </SubHead>
            {p ? <pre className="block max-h-[28rem] overflow-auto">{p.user}</pre> : <Empty>prompt.json missing</Empty>}
            <p className="mt-1.5 text-[11px] leading-snug text-ink-3">
              Muse received only: the objective, the frozen contract, what the agent's tool reported, the verifier's measured numbers, and the allowlisted tools. No ground truth, no fixture notes,
              no diffs, no hints. Source filenames mentioned in turn-1 prompt: <Check ok={!(p?.mentions_source_filenames ?? ac.mentions_source_filenames)} yes="none" no="yes" />.
            </p>
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            <Collapsible summary={`banned-term screen: ${checked} terms checked, ${found.length} found`}>
              <ul className="mono flex flex-wrap gap-1 text-[11px]">
                {(p?.banned_terms_checked ?? []).map((t) => (
                  <li key={t} className={`rounded border px-1.5 py-0.5 ${found.includes(t) ? 'border-bad bg-bad/20 text-ink' : 'border-line text-ink-2'}`}>
                    {t}
                  </li>
                ))}
                {!p && <li className="text-ink-3">term list lives in prompt.json (missing)</li>}
              </ul>
            </Collapsible>
            <Collapsible summary="system instructions given to Muse">
              <p className="whitespace-pre-wrap text-xs leading-relaxed text-ink-2">{p?.instructions ?? '—'}</p>
            </Collapsible>
            <Collapsible summary={`tool surface offered (${p?.tools.length ?? 0} allowlisted functions)`} className="sm:col-span-2">
              <ul className="space-y-1.5">
                {(p?.tools ?? []).map((t) => (
                  <li key={t.name} className="text-xs">
                    <span className="mono text-ink">{t.name}</span> <span className="text-ink-3">— {t.description}</span>
                  </li>
                ))}
              </ul>
            </Collapsible>
          </div>
        </div>

        <div className="min-w-0 space-y-4">
          <div>
            <SubHead>Tool-call transcript (ordered)</SubHead>
            <Timeline turn={turn} />
          </div>
        </div>
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <div className="min-w-0">
          <SubHead>Patches applied by the adapter (find → replace, exactly once)</SubHead>
          {turn.patches.length === 0 && <Empty>no patch in this turn</Empty>}
          <div className="space-y-3">
            {turn.patches.map((pt, i) => (
              <div key={i} className="rounded-lg border border-line bg-surface/40 p-3">
                <Kv
                  items={[
                    ['file', <span className="mono text-xs text-ink">{pt.path}</span>],
                    ['reason (model text)', <span className="text-xs italic text-ink-2">{pt.reason}</span>],
                    ['find', <pre className="block">{pt.find}</pre>],
                    ['replace', <pre className="block">{pt.replace}</pre>],
                    ['applied at', <span className="mono text-xs">{pt.ts ?? '—'}</span>],
                  ]}
                />
              </div>
            ))}
          </div>
        </div>
        <div className="min-w-0">
          <SubHead
            right={
              <span className="text-[11px] text-ink-3">
                diff sha256 <Hash value={r.diff_sha256} n={16} />
              </span>
            }
          >
            Unified diff (diff.patch)
          </SubHead>
          {turn.diff ? <DiffView diff={turn.diff} /> : <Empty>no diff recorded</Empty>}
        </div>
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <div className="rounded-lg border border-line-2 bg-card-2/50 p-3">
          <p className="mb-1 text-[11px] uppercase tracking-wider text-ink-3">Model's closing text — recorded, never consulted</p>
          <pre className="whitespace-pre-wrap font-sans text-xs italic leading-relaxed text-ink-2">{r.outcome_text || '(none)'}</pre>
        </div>
        <div className="rounded-lg border border-line p-3">
          <p className="mb-2 text-[11px] uppercase tracking-wider text-ink-3">Outcome — what the verifier measured after relaunch and re-capture</p>
          {afterPass ? (
            <div className="space-y-2">
              <VerdictBadge status={afterPass.record.verification_status} tFail={afterPass.record.t_fail} label={`pass ${afterPass.record.index}`} />
              <p className="text-xs text-ink-2">
                {afterPass.verification?.reasons.join('; ')} · max E(t) {afterPass.record.max_residual != null ? `${afterPass.record.max_residual > 0 ? '+' : ''}${afterPass.record.max_residual.toFixed(1)} px` : 'n/a'}
                {afterPass.record.project_tree_sha256 && (
                  <>
                    {' '}
                    · patched tree <Hash value={afterPass.record.project_tree_sha256} />
                  </>
                )}
              </p>
            </div>
          ) : (
            <Empty>no pass was captured after this turn (run ended or errored)</Empty>
          )}
        </div>
      </div>
    </div>
  )
}

export function DiagnosisPanel({ run }: { run: LoadedRun }) {
  return (
    <Section
      id="diagnosis"
      title="Blind diagnosis — Muse Spark repairs the scene through the allowlisted Godot MCP surface"
      subtitle="Everything Muse saw and did, in order. Its words are shown as words; the only verdict is the verifier's re-measurement of the patched game."
    >
      {run.turns.length === 0 ? (
        <Empty>
          No repair turns in this bundle. {run.manifest.kind === 'clip_evaluation' ? 'clip_evaluation runs only track and verify pre-captured clips.' : 'The first pass passed, or the run stopped before diagnosis.'}
        </Empty>
      ) : (
        <div className="space-y-8">
          {run.turns.map((t) => (
            <TurnView key={t.record.turn} run={run} turn={t} />
          ))}
        </div>
      )}
    </Section>
  )
}
