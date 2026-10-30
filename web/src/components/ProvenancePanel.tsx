import { useMemo, useState, type ReactNode } from 'react'
import type { FetchedFile, LoadedRun } from '../types'
import { fmtBytes, fmtClock, fmtInt, fmtIso, fmtUsd } from '../lib/format'
import { hashMedia } from '../lib/load'
import { Btn, Check, Collapsible, Hash, Kv, Pill, Section, SubHead } from './ui'
import { TruthChart } from './TruthChart'

type HashState = 'verified' | 'mismatch' | 'not-fetched' | 'not-distributed' | 'absent' | 'no-webcrypto'

function classify(path: string, fetched: Map<string, FetchedFile>): HashState {
  const f = fetched.get(path)
  if (path.includes('/frames/') || path.startsWith('workspace/')) return f ? (f.match === true ? 'verified' : f.match === false ? 'mismatch' : 'no-webcrypto') : 'not-distributed'
  if (!f) return 'not-fetched'
  if (f.bytes === 0 && f.sha256 === null) return 'absent'
  if (f.match === true) return 'verified'
  if (f.match === false) return 'mismatch'
  return 'no-webcrypto'
}

const STATE_LABEL: Record<HashState, [string, string]> = {
  verified: ['✓ verified in browser', 'text-ok'],
  mismatch: ['✗ MISMATCH', 'text-bad'],
  'not-fetched': ['not fetched (media streams via <video>)', 'text-ink-3'],
  'not-distributed': ['not distributed (gitignored; hashed at write time)', 'text-ink-3'],
  absent: ['absent (404)', 'text-warn'],
  'no-webcrypto': ['fetched; hash unavailable (no WebCrypto)', 'text-ink-3'],
}

export function ProvenancePanel({ run }: { run: LoadedRun }) {
  const m = run.manifest
  const [showFrames, setShowFrames] = useState(false)
  const [showWorkspace, setShowWorkspace] = useState(false)
  const [media, setMedia] = useState<FetchedFile[] | null>(null)
  const [hashing, setHashing] = useState(false)

  const fetched = useMemo(() => {
    const map = new Map<string, FetchedFile>()
    for (const f of run.fetched) map.set(f.path, f)
    for (const f of media ?? []) map.set(f.path, f)
    return map
  }, [run.fetched, media])

  const files = useMemo(() => Object.entries(m.files).sort(([a], [b]) => a.localeCompare(b)), [m.files])
  const counts = useMemo(() => {
    const c: Record<HashState, number> = { verified: 0, mismatch: 0, 'not-fetched': 0, 'not-distributed': 0, absent: 0, 'no-webcrypto': 0 }
    for (const [p] of files) c[classify(p, fetched)] += 1
    return c
  }, [files, fetched])
  const visible = files.filter(([p]) => (showFrames || !p.includes('/frames/')) && (showWorkspace || !p.startsWith('workspace/')))

  const apiIds = new Set(run.apiCalls.map((c) => c.request_id).filter(Boolean))
  const manifestIds = new Set(m.request_ids)
  const idsAgree = apiIds.size === manifestIds.size && [...apiIds].every((id) => manifestIds.has(id))

  const verifyMedia = async () => {
    setHashing(true)
    try {
      setMedia(await hashMedia(run))
    } finally {
      setHashing(false)
    }
  }

  const b = m.baseline ?? {}
  const w = m.workspace ?? {}
  const env = m.environment ?? {}
  const godot = (env.godot ?? null) as Record<string, unknown> | null

  return (
    <Section
      id="provenance"
      title="Provenance — every number labelled by its source"
      subtitle="Models and request ids from Meta's API logs, sha256 of every bundle file (recomputed in this browser for the files it fetched), tree hashes proving the original project was never mutated, and the spend meter."
    >
      <div className="grid gap-6 xl:grid-cols-2">
        <div className="space-y-5">
          <div>
            <SubHead>Models used</SubHead>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(m.models).map(([role, model]) => (
                <Pill key={role}>
                  <span className="text-ink-3">{role}</span> <span className="mono">{model}</span>
                </Pill>
              ))}
            </div>
            <p className="mt-1.5 text-[11px] text-ink-3">Runtime models are Meta's only: SAM 3.1 for tracking, Muse Spark for contract compilation and blind diagnosis{m.models.escalation ? `, ${m.models.escalation} as escalation (unused when turn 1 repairs)` : ''}.</p>
          </div>

          <div>
            <SubHead>Baseline and working copy (tree sha256, .godot/ excluded)</SubHead>
            {b.tree_sha256 ? (
              <Kv
                items={[
                  ['baseline project', <span className="mono text-xs text-ink-2">{b.path ?? '—'}</span>],
                  ['baseline tree before run', <Hash value={b.tree_sha256} n={24} />],
                  ['baseline tree after run', <span className="inline-flex flex-wrap items-center gap-2"><Hash value={b.tree_sha256_after_run} n={24} /><Check ok={b.unchanged} yes="baseline unchanged" no="BASELINE MUTATED" /></span>],
                  ['staged copy tree', <span className="inline-flex flex-wrap items-center gap-2"><Hash value={w.staged_tree_sha256} n={24} /><Check ok={w.baseline_match_at_stage} yes="copy matched baseline at stage" no="copy differed at stage" /></span>],
                  ['copy tree after repair', <span className="inline-flex flex-wrap items-center gap-2"><Hash value={w.final_tree_sha256} n={24} /><span className="text-xs text-ink-2">{w.modified_during_run ? 'modified during run (patched)' : 'unmodified'}</span></span>],
                  ['files in tree', <span className="mono num">{b.files ?? '—'}</span>],
                  ['staged at', fmtIso(w.staged_at)],
                ]}
              />
            ) : (
              <p className="text-xs text-ink-3">No project was staged: clip_evaluation bundles score pre-captured clips.</p>
            )}
            {m.passes.some((p) => p.project_tree_sha256) && (
              <Kv className="mt-2" items={m.passes.map((p) => [`pass ${p.index} project tree`, <Hash key={p.index} value={p.project_tree_sha256} n={24} />] as [string, ReactNode])} />
            )}
          </div>

          <div>
            <SubHead>Spend (Meta API, estimated at published prices)</SubHead>
            <Kv
              items={[
                ['calls', <span className="mono num">{fmtInt(m.spend.calls)}</span>],
                ['estimated cost', <span className="mono num">{fmtUsd(m.spend.est_cost_usd)}</span>],
                ...Object.entries(m.spend.by_model ?? {}).map(([model, s]) => [
                  <span key={model} className="mono">{model === 'None' ? 'file uploads' : model}</span>,
                  <span key={`${model}-v`} className="mono num">
                    {s.calls} calls · {s.cached} cached · {fmtUsd(s.est_cost_usd)}
                  </span>,
                ] as [ReactNode, ReactNode]),
              ]}
            />
          </div>

          <div>
            <SubHead>Environment</SubHead>
            <Kv
              items={[
                ['host', <span className="mono text-xs">{String(env.host ?? '—')}</span>],
                ['python · propriosam', <span className="mono text-xs">{String(env.python ?? '—')} · {String(env.propriosam ?? '—')}</span>],
                ['godot', <span className="mono text-xs">{godot ? `${String(godot.version ?? '—')} (${String(godot.binary ?? '')})` : '— (no Godot in a clip evaluation)'}</span>],
                ['run', <span className="mono text-xs">{fmtIso(m.created_at)} → {fmtIso(m.finished_at)}</span>],
                ['notes', <span className="text-xs text-ink-2">{m.notes.join(' ') || '—'}</span>],
              ]}
            />
          </div>
        </div>

        <div className="space-y-5">
          <div>
            <SubHead
              right={
                <span className="text-[11px] text-ink-3">
                  api_calls.jsonl ids = manifest request_ids: <Check ok={idsAgree} yes={`${apiIds.size} match`} no={`${apiIds.size} vs ${manifestIds.size}`} />
                </span>
              }
            >
              Every Meta request ({run.apiCalls.length} calls, x-request-id)
            </SubHead>
            <div className="max-h-72 overflow-auto rounded-lg border border-line">
              <table className="w-full text-left text-[11px]">
                <thead className="sticky top-0 bg-card text-ink-3">
                  <tr>
                    <th className="px-2 py-1">time</th>
                    <th className="px-2 py-1">purpose</th>
                    <th className="px-2 py-1">model</th>
                    <th className="px-2 py-1">request id</th>
                    <th className="px-2 py-1 text-right">http</th>
                    <th className="px-2 py-1 text-right">latency</th>
                    <th className="px-2 py-1 text-right">usage</th>
                    <th className="px-2 py-1 text-right">est $</th>
                  </tr>
                </thead>
                <tbody className="num">
                  {run.apiCalls.map((c, i) => (
                    <tr key={i} className="border-t border-line/60">
                      <td className="mono px-2 py-0.5 text-ink-3">{fmtClock(c.ts)}</td>
                      <td className="px-2 py-0.5 text-ink-2">{c.purpose}</td>
                      <td className="mono px-2 py-0.5 text-ink-2">{c.model ?? 'upload'}</td>
                      <td className="px-2 py-0.5">
                        <Hash value={c.request_id} n={36} />
                      </td>
                      <td className="mono px-2 py-0.5 text-right text-ink-2">{c.http}</td>
                      <td className="mono px-2 py-0.5 text-right text-ink-2">{c.latency_s.toFixed(1)}s</td>
                      <td className="mono px-2 py-0.5 text-right text-ink-2">
                        {c.usage?.video_frames_processed != null
                          ? `${c.usage.video_frames_processed} frames`
                          : c.usage?.input_tokens != null
                            ? `${fmtInt(c.usage.input_tokens)}→${fmtInt(c.usage.output_tokens)}`
                            : c.bytes != null
                              ? fmtBytes(c.bytes)
                              : '—'}
                      </td>
                      <td className="mono px-2 py-0.5 text-right text-ink-2">{c.est_cost_usd.toFixed(4)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div>
            <SubHead
              right={
                <div className="flex flex-wrap items-center gap-1.5">
                  <Btn size="xs" active={showFrames} onClick={() => setShowFrames((v) => !v)}>
                    frames
                  </Btn>
                  <Btn size="xs" active={showWorkspace} onClick={() => setShowWorkspace((v) => !v)}>
                    workspace
                  </Btn>
                  <Btn size="xs" onClick={verifyMedia} disabled={hashing} title="fetch clip.mp4 / overlay.mp4 and hash them here">
                    {hashing ? 'hashing…' : media ? 'media re-verified' : 'verify media hashes'}
                  </Btn>
                </div>
              }
            >
              Bundle file hashes ({files.length} entries · {counts.verified} verified here{counts.mismatch ? ` · ${counts.mismatch} MISMATCH` : ''})
            </SubHead>
            <div className="max-h-72 overflow-auto rounded-lg border border-line">
              <table className="w-full text-left text-[11px]">
                <thead className="sticky top-0 bg-card text-ink-3">
                  <tr>
                    <th className="px-2 py-1">file</th>
                    <th className="px-2 py-1">sha256 (manifest)</th>
                    <th className="px-2 py-1">status</th>
                  </tr>
                </thead>
                <tbody>
                  {visible.map(([path, sha]) => {
                    const st = classify(path, fetched)
                    const [label, cls] = STATE_LABEL[st]
                    return (
                      <tr key={path} className="border-t border-line/60">
                        <td className="mono px-2 py-0.5 text-ink-2">{path}</td>
                        <td className="px-2 py-0.5">
                          <Hash value={sha} n={16} />
                        </td>
                        <td className={`px-2 py-0.5 ${cls}`}>{label}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            <p className="mt-1.5 text-[11px] leading-snug text-ink-3">
              {counts['not-distributed']} entries are raw frames or the staged workspace: hashed when the bundle was written, gitignored since. The offline replay (<span className="mono">scripts/replay_run.py</span>) performs the
              same check over the full bundle.
            </p>
          </div>

          {run.warnings.length > 0 && (
            <Collapsible summary={`${run.warnings.length} loader warning(s)`}>
              <ul className="mono space-y-1 text-[11px] text-warn">
                {run.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </Collapsible>
          )}
        </div>
      </div>

      <div className="mt-8 rounded-xl border-2 border-dashed border-truth/60 bg-truth/5 p-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-semibold text-ink">Hidden ground truth (evaluation only, never shown to any model)</h3>
          <Pill tone="truth">truth_hidden.json · read by nobody in the loop</Pill>
        </div>
        <p className="mb-3 text-xs leading-relaxed text-ink-2">
          The engine's own player position per captured frame, saved alongside each clip for evaluating the verifier after the fact. It is never read by the verifier, never
          included in any prompt, and the anti-cheat screen bans its filename from outgoing text. It exists so the SAM-based verdicts above can be checked against physics.
        </p>
        <TruthChart passes={run.passes} />
        {run.passes.some((p) => p.truth?.note) && <p className="mt-2 text-[11px] text-ink-3">file note: {run.passes.find((p) => p.truth?.note)?.truth?.note}</p>}
      </div>
    </Section>
  )
}
