import type { OpenLoop, VerificationStatus } from '../types'
import { VERDICT_CAPTION, statusTone } from '../lib/format'
import { STATUS } from '../lib/theme'

/** The only way a verdict is ever shown: status + the caption naming its source. */
export function VerdictBadge({
  status,
  tFail,
  label = 'Verifier',
  size = 'md',
  caption = true,
  extra,
}: {
  status: VerificationStatus | string | null | undefined
  tFail?: number | null
  label?: string
  size?: 'sm' | 'md' | 'lg'
  caption?: boolean
  extra?: string
}) {
  const tone = statusTone(status)
  const color = STATUS[tone]
  const pad = size === 'lg' ? 'px-3 py-1.5 text-base' : size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-sm'
  return (
    <div className="inline-flex max-w-full flex-col items-start gap-1">
      <span
        className={`inline-flex items-center gap-2 rounded-md border font-semibold text-ink ${pad}`}
        style={{ borderColor: color, background: `${color}22` }}
        title={VERDICT_CAPTION}
      >
        <span className="inline-block h-2 w-2 shrink-0 rounded-full" style={{ background: color }} aria-hidden="true" />
        <span>
          {label}: {status ?? '—'}
          {tFail != null && <span className="mono num font-medium text-ink-2"> @ frame {tFail}</span>}
          {extra && <span className="font-medium text-ink-2"> · {extra}</span>}
        </span>
      </span>
      {caption && <span className="text-[11px] leading-tight text-ink-3">{VERDICT_CAPTION}</span>}
    </div>
  )
}

/** What the agent's tool said. Shown next to the verdict so the two can be compared, never merged. */
export function OpenLoopBadge({ openLoop, size = 'md' }: { openLoop: OpenLoop | null | undefined; size?: 'sm' | 'md' }) {
  const pad = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-sm'
  if (!openLoop || !openLoop.tool) {
    return (
      <div className="inline-flex flex-col items-start gap-1">
        <span className={`inline-flex items-center gap-2 rounded-md border border-line-2 bg-card-2 text-ink-2 ${pad}`}>
          <span className="inline-block h-2 w-2 rounded-full bg-neutral" aria-hidden="true" />
          Open loop: no tool result recorded (pre-captured clip)
        </span>
        <span className="text-[11px] leading-tight text-ink-3">clip_evaluation bundles score clips that were captured earlier</span>
      </div>
    )
  }
  const errored = openLoop.mcp_is_error === true
  const resultText = openLoop.result == null ? '' : JSON.stringify(openLoop.result)
  return (
    <div className="inline-flex max-w-full flex-col items-start gap-1">
      <span className={`inline-flex items-center gap-2 rounded-md border border-line-2 bg-card-2 text-ink-2 ${pad}`} title={resultText}>
        <span className="inline-block h-2 w-2 shrink-0 rounded-full bg-neutral" aria-hidden="true" />
        <span>
          MCP tool <span className="mono text-ink">{openLoop.tool}</span> said{' '}
          <span className="font-semibold text-ink">{errored ? 'ERROR' : 'OK'}</span>
          <span className="text-ink-3"> (is_error = {String(openLoop.mcp_is_error ?? 'unknown')})</span>
        </span>
      </span>
      <span className="text-[11px] leading-tight text-ink-3">{openLoop.note ?? 'recorded for the audit; never consulted for the verdict'}</span>
    </div>
  )
}
