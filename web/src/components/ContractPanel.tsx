import type { LoadedRun } from '../types'
import { fmtIso, fmtPct } from '../lib/format'
import { Check, Collapsible, Empty, Hash, Kv, Pill, Section, SubHead } from './ui'

export function ContractPanel({ run }: { run: LoadedRun }) {
  const c = run.contract
  const m = run.manifest
  if (!c) {
    return (
      <Section id="contract" title="Sensory contract">
        <Empty>contract.json is missing from this bundle.</Empty>
      </Section>
    )
  }
  const rule = m.rule_sha256
  return (
    <Section
      id="contract"
      title="Sensory contract — frozen before any clip was scored"
      subtitle="Muse Spark compiled the instance (concepts, thresholds, window, statement) from the objective and scene brief; the geometric rule family is fixed library code. The instance was hashed before measurement and never changed."
      right={
        <>
          <Pill tone="mover">mover: {c.mover_concept}</Pill>
          <Pill tone="barrier">barrier: {c.barrier_concept}</Pill>
          <Pill tone={c.frozen_sha256 === m.contract_sha256 ? 'ok' : 'bad'} title="contract.json frozen_sha256 == run_manifest.json contract_sha256">
            frozen hash {c.frozen_sha256 === m.contract_sha256 ? 'matches manifest' : 'MISMATCH'}
          </Pill>
        </>
      }
    >
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-4">
          <div>
            <SubHead>Falsifiable statement</SubHead>
            <blockquote className="rounded-lg border-l-2 border-ink-3 bg-surface/60 px-4 py-3 text-sm leading-relaxed text-ink">{c.statement}</blockquote>
          </div>
          <Kv
            items={[
              ['objective', c.objective],
              ['expected if satisfied', c.expected_pass_behaviour],
              ['expected if violated', c.expected_fail_signature],
            ]}
          />
          <Collapsible summary="scene brief (what the compiler was told about the camera and the scene)">
            <p className="text-xs leading-relaxed text-ink-2">{c.scene_brief}</p>
          </Collapsible>
          <div>
            <SubHead>Concept vocabulary (SAM 3.1 phrases the tracker was calibrated on)</SubHead>
            <div className="flex flex-wrap gap-1.5">
              {c.concept_vocabulary.map((v) => (
                <Pill key={v} tone={v === c.mover_concept ? 'mover' : v === c.barrier_concept ? 'barrier' : 'neutral'}>
                  {v}
                </Pill>
              ))}
            </div>
          </div>
        </div>
        <div className="space-y-4">
          <div>
            <SubHead>Rule (fixed family, frozen parameters)</SubHead>
            <Kv
              items={[
                ['family', <span className="mono text-xs">{c.rule.family}</span>],
                ['definition', c.rule.definition],
                ['threshold_px', <span className="mono num">{c.rule.threshold_px} px</span>],
                ['persistence_frames', <span className="mono num">{c.rule.persistence_frames} consecutive tracked frames</span>],
                ['edges', <span className="mono text-xs">mover.{c.rule.mover_edge} vs barrier.{c.rule.barrier_edge}</span>],
              ]}
            />
          </div>
          <div>
            <SubHead>Coverage gates (unmet ⇒ INCONCLUSIVE, never PASS)</SubHead>
            <Kv
              items={[
                ['critical window', <span className="mono num">frames [{c.coverage.critical_window[0]}, {c.coverage.critical_window[1]}]</span>],
                ['min window coverage', <span className="mono num">{fmtPct(c.coverage.min_window_coverage)} of window frames with both concepts tracked</span>],
                ['min total coverage', <span className="mono num">{fmtPct(c.coverage.min_total_coverage)} of all frames, each concept</span>],
                ['clip', <span className="mono num">{c.frame_count} frames @ {c.fps} fps · {c.frame_size[0]}×{c.frame_size[1]} px</span>],
              ]}
            />
          </div>
          <div>
            <SubHead>Hashes</SubHead>
            <Kv
              items={[
                ['contract_id', <span className="mono text-xs">{c.contract_id}</span>],
                ['frozen_sha256 (contract.json)', <Hash value={c.frozen_sha256} n={24} />],
                ['contract_sha256 (manifest)', <span className="inline-flex items-center gap-2"><Hash value={m.contract_sha256} n={24} /><Check ok={c.frozen_sha256 === m.contract_sha256} yes="equal" no="different" /></span>],
                ['rule_sha256 (verifier source at run time)', <Hash value={rule} n={24} />],
                ['schema', <span className="mono text-xs">{c.schema_version}</span>],
              ]}
            />
          </div>
          {c.compiled_by && (
            <div>
              <SubHead>Compiled by</SubHead>
              <Kv
                items={[
                  ['model', <span className="mono text-xs">{c.compiled_by.model ?? '—'}</span>],
                  ['request id', <Hash value={c.compiled_by.request_id} n={40} />],
                  ['response id', <Hash value={c.compiled_by.response_id} n={40} />],
                  ['compiled at', fmtIso(c.compiled_by.created_at)],
                  ['prompt version · attempt', <span className="mono text-xs">{c.compiled_by.prompt_version ?? '—'} · {c.compiled_by.attempt ?? '—'}</span>],
                ]}
              />
              {c.compiled_by.raw_output && (
                <Collapsible summary="raw structured output returned by the compiler" className="mt-2">
                  <pre className="block">{c.compiled_by.raw_output}</pre>
                </Collapsible>
              )}
            </div>
          )}
        </div>
      </div>
    </Section>
  )
}
