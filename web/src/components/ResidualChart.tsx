import { useCallback, useMemo, useRef, useState, type PointerEvent as RPointerEvent } from 'react'
import type { LoadedPass, LoadedRun } from '../types'
import { fmtPx, frameTime } from '../lib/format'
import { CONCEPT, INK, STATUS, SURFACE, passColor } from '../lib/theme'
import { player, usePlayer } from '../lib/playerStore'
import { VerdictBadge } from './VerdictBadge'
import { Collapsible, Section, Swatch } from './ui'
import { CoverageBars } from './CoverageBars'

const W = 1000
const PLOT_H = 300
const ML = 56
const MR = 24
const MT = 34
const MB = 26
const STRIP_H = 8
const STRIP_GAP = 3

function niceStep(span: number, target = 6): number {
  const raw = span / target
  const pow = Math.pow(10, Math.floor(Math.log10(raw)))
  for (const m of [1, 2, 5, 10]) if (raw <= m * pow) return m * pow
  return 10 * pow
}

interface Segment {
  pts: [number, number][]
}

function segments(values: (number | null | undefined)[], x: (f: number) => number, y: (e: number) => number): { lines: Segment[]; singles: [number, number][] } {
  const lines: Segment[] = []
  const singles: [number, number][] = []
  let cur: [number, number][] = []
  const flush = () => {
    if (cur.length >= 2) lines.push({ pts: cur })
    else if (cur.length === 1 && cur[0]) singles.push(cur[0])
    cur = []
  }
  values.forEach((v, f) => {
    if (v == null) flush()
    else cur.push([x(f), y(v)])
  })
  flush()
  return { lines, singles }
}

export function ResidualChart({ run }: { run: LoadedRun }) {
  const { frame, playing, hover, frameCount: N, fps } = usePlayer()
  const contract = run.contract
  const threshold = contract?.rule.threshold_px ?? 0
  const persistence = contract?.rule.persistence_frames ?? 0
  const win = contract?.coverage.critical_window ?? [0, N - 1]
  const passes = run.passes.filter((p) => p.verification)
  const svgRef = useRef<SVGSVGElement | null>(null)
  const [dragging, setDragging] = useState(false)

  const stripsH = passes.length * (2 * STRIP_H + STRIP_GAP) + 10
  const H = MT + PLOT_H + MB + stripsH

  const { ymin, ymax } = useMemo(() => {
    let lo = Math.min(0, threshold)
    let hi = Math.max(0, threshold)
    for (const p of passes) for (const e of p.verification?.residual ?? []) if (e != null) (lo = Math.min(lo, e)), (hi = Math.max(hi, e))
    const span = Math.max(40, hi - lo)
    const pad = span * 0.08
    return { ymin: lo - pad, ymax: hi + pad }
  }, [passes, threshold])

  const x = useCallback((f: number) => ML + (f / Math.max(1, N - 1)) * (W - ML - MR), [N])
  const y = useCallback((e: number) => MT + (1 - (e - ymin) / (ymax - ymin)) * PLOT_H, [ymin, ymax])
  const plotBottom = MT + PLOT_H
  const cellW = (W - ML - MR) / Math.max(1, N - 1)

  const ticks = useMemo(() => {
    const step = niceStep(ymax - ymin)
    const out: number[] = []
    for (let v = Math.ceil(ymin / step) * step; v <= ymax; v += step) out.push(Math.round(v * 1000) / 1000)
    return out
  }, [ymin, ymax])
  const xTicks = useMemo(() => {
    const step = N > 40 ? 10 : 5
    const out: number[] = []
    for (let f = 0; f < N; f += step) out.push(f)
    if (!out.includes(N - 1)) out.push(N - 1)
    return out
  }, [N])

  const series = useMemo(
    () => passes.map((p) => ({ pass: p, color: passColor(p.record.index), ...segments(p.verification?.residual ?? [], x, y) })),
    [passes, x, y],
  )

  const frameFromEvent = (ev: RPointerEvent<SVGElement>): number => {
    const svg = svgRef.current
    if (!svg) return 0
    const r = svg.getBoundingClientRect()
    const sx = ((ev.clientX - r.left) / r.width) * W
    const f = Math.round(((sx - ML) / (W - ML - MR)) * (N - 1))
    return Math.min(N - 1, Math.max(0, f))
  }
  const onMove = (ev: RPointerEvent<SVGRectElement>) => {
    const f = frameFromEvent(ev)
    player.setHover(f)
    if (!playing || dragging) player.seek(f)
  }
  const onDown = (ev: RPointerEvent<SVGRectElement>) => {
    setDragging(true)
    ev.currentTarget.setPointerCapture(ev.pointerId)
    player.seek(frameFromEvent(ev))
  }
  const onUp = (ev: RPointerEvent<SVGRectElement>) => {
    setDragging(false)
    ev.currentTarget.releasePointerCapture(ev.pointerId)
  }

  const cursorFrame = frame
  const hoverFrame = playing && hover != null && hover !== frame ? hover : null

  const maxMarkers = passes
    .map((p) => {
      const v = p.verification
      if (!v || v.max_residual == null || v.max_residual_frame == null) return null
      return { pass: p, f: v.max_residual_frame, e: v.max_residual, color: passColor(p.record.index) }
    })
    .filter((m): m is NonNullable<typeof m> => m !== null)

  return (
    <Section
      id="residual"
      title="Residual E(t) = y_bottom(barrier) − y_bottom(mover)"
      subtitle={`source pixels, y grows downward · E > ${threshold} px for ${persistence} consecutive tracked frames ⇒ FAIL · gaps are frames where either concept is untracked · hover to scrub (drag while playing)`}
      right={
        <div className="flex flex-wrap items-center gap-3 text-xs text-ink-2">
          {passes.map((p) => (
            <span key={p.record.index} className="inline-flex items-center gap-1.5">
              <Swatch color={passColor(p.record.index)} />
              pass {p.record.index} — {p.record.label}
              <span className="text-ink-3">· {p.record.verification_status}{p.record.t_fail != null ? ` @${p.record.t_fail}` : ''}</span>
            </span>
          ))}
          <span className="inline-flex items-center gap-1.5">
            <Swatch color={CONCEPT.mover} kind="square" /> mover tracked
          </span>
          <span className="inline-flex items-center gap-1.5">
            <Swatch color={CONCEPT.barrier} kind="square" /> barrier tracked
          </span>
        </div>
      }
    >
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="min-w-0">
          <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} className="block w-full select-none" role="img" aria-label="residual E(t) per pass">
            {/* critical window */}
            <rect x={x(win[0]) - cellW / 2} y={MT} width={x(win[1]) - x(win[0]) + cellW} height={PLOT_H} fill="#ffffff" opacity={0.045} />
            <text x={x(win[0]) + 6} y={plotBottom - 8} fontSize={11} fill={INK.muted}>
              critical window [{win[0]}, {win[1]}] · coverage gates apply here
            </text>
            {/* crossing zone above threshold */}
            <rect x={ML} y={MT} width={W - ML - MR} height={Math.max(0, y(threshold) - MT)} fill={STATUS.fail} opacity={0.07} />
            {y(threshold) - MT > 24 && (
              <text x={ML + 8} y={y(threshold) - 7} fontSize={11} fill={INK.muted}>
                crossing zone above: E(t) {'>'} {threshold} px for {persistence} tracked frames ⇒ FAIL
              </text>
            )}
            {/* grid */}
            {ticks.map((t) => (
              <g key={t}>
                <line x1={ML} x2={W - MR} y1={y(t)} y2={y(t)} stroke={t === 0 ? INK.axis : INK.grid} strokeWidth={1} />
                <text x={ML - 8} y={y(t) + 4} fontSize={11} textAnchor="end" fill={INK.muted} className="num">
                  {t > 0 ? `+${t}` : t}
                </text>
              </g>
            ))}
            <text x={12} y={MT + PLOT_H / 2} fontSize={11} fill={INK.muted} transform={`rotate(-90 12 ${MT + PLOT_H / 2})`} textAnchor="middle">
              E(t) px
            </text>
            {xTicks.map((f) => (
              <g key={f}>
                <line x1={x(f)} x2={x(f)} y1={plotBottom} y2={plotBottom + 4} stroke={INK.axis} />
                <text x={x(f)} y={plotBottom + 16} fontSize={11} textAnchor="middle" fill={INK.muted} className="num">
                  {f}
                </text>
              </g>
            ))}
            {/* threshold */}
            <line x1={ML} x2={W - MR} y1={y(threshold)} y2={y(threshold)} stroke={INK.secondary} strokeWidth={1.25} strokeDasharray="6 4" />
            <text x={W - MR - 4} y={y(threshold) - 5} fontSize={11} textAnchor="end" fill={INK.secondary}>
              threshold +{threshold} px
            </text>
            {/* violation runs + t_fail markers */}
            {passes.map((p, i) => {
              const v = p.verification
              if (!v || v.t_fail == null) return null
              const run = v.violation_run ?? [v.t_fail]
              const f0 = run[0] ?? v.t_fail
              const f1 = run[run.length - 1] ?? v.t_fail
              const c = passColor(p.record.index)
              return (
                <g key={p.record.index}>
                  <rect x={x(f0) - cellW / 2} y={MT} width={x(f1) - x(f0) + cellW} height={PLOT_H} fill={c} opacity={0.14} />
                  <line x1={x(v.t_fail)} x2={x(v.t_fail)} y1={MT - 6 - i * 13} y2={plotBottom} stroke={c} strokeWidth={1.5} />
                  <g transform={`translate(${x(v.t_fail) + 6} ${MT - 9 - i * 13})`}>
                    <rect x={-2} y={-10} width={118} height={13} fill={SURFACE} opacity={0.85} />
                    <rect x={0} y={-8} width={8} height={8} fill={c} />
                    <text x={12} y={-1} fontSize={11} fill={INK.secondary}>
                      pass {p.record.index} t_fail = {v.t_fail}
                    </text>
                  </g>
                </g>
              )
            })}
            {/* series */}
            {series.map((s) => (
              <g key={s.pass.record.index}>
                {s.lines.map((seg, i) => (
                  <path key={i} d={seg.pts.map(([px, py], j) => `${j === 0 ? 'M' : 'L'}${px.toFixed(1)} ${py.toFixed(1)}`).join(' ')} fill="none" stroke={s.color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
                ))}
                {s.singles.map(([px, py], i) => (
                  <circle key={i} cx={px} cy={py} r={3} fill={s.color} />
                ))}
              </g>
            ))}
            {/* max E markers (the extreme, labelled) */}
            {maxMarkers.map((m, i) => (
              <g key={m.pass.record.index}>
                <circle cx={x(m.f)} cy={y(m.e)} r={4.5} fill={m.color} stroke={SURFACE} strokeWidth={2} />
                <text x={x(m.f) + (m.f > N * 0.75 ? -8 : 8)} y={y(m.e) + (i % 2 ? 16 : -8)} fontSize={11} textAnchor={m.f > N * 0.75 ? 'end' : 'start'} fill={INK.secondary} className="num">
                  pass {m.pass.record.index} max {fmtPx(m.e)} @ f{m.f}
                </text>
              </g>
            ))}
            {/* hover cursor while playing */}
            {hoverFrame != null && <line x1={x(hoverFrame)} x2={x(hoverFrame)} y1={MT} y2={plotBottom} stroke={INK.muted} strokeDasharray="3 3" />}
            {/* cursor synchronised with the player */}
            <line x1={x(cursorFrame)} x2={x(cursorFrame)} y1={MT - 4} y2={plotBottom + stripsH + 4} stroke={INK.primary} strokeWidth={1} opacity={0.85} />
            {series.map((s) => {
              const e = s.pass.verification?.residual[cursorFrame] ?? null
              return e == null ? null : <circle key={s.pass.record.index} cx={x(cursorFrame)} cy={y(e)} r={4.5} fill={s.color} stroke={SURFACE} strokeWidth={2} />
            })}
            {/* readout */}
            <g transform={`translate(${ML + 10} ${MT + 8})`}>
              <rect x={0} y={0} width={180} height={18 + 15 * series.length} rx={4} fill="#131a29" opacity={0.92} stroke={INK.grid} />
              <text x={8} y={13} fontSize={11} fill={INK.secondary} className="num">
                frame {cursorFrame} · {frameTime(cursorFrame, fps)}
              </text>
              {series.map((s, i) => {
                const e = s.pass.verification?.residual[cursorFrame] ?? null
                return (
                  <g key={s.pass.record.index} transform={`translate(8 ${28 + i * 15})`}>
                    <rect x={0} y={-8} width={10} height={3} fill={s.color} />
                    <text x={16} y={0} fontSize={11} fill={INK.primary} className="num">
                      pass {s.pass.record.index}: {e == null ? 'untracked' : fmtPx(e)}
                    </text>
                  </g>
                )
              })}
            </g>
            {/* tracked strips */}
            {passes.map((p, i) => {
              const top = plotBottom + MB + i * (2 * STRIP_H + STRIP_GAP)
              const mover = new Set(p.tracks?.mover.points.map((q) => q.frame) ?? [])
              const barrier = new Set(p.tracks?.barrier.points.map((q) => q.frame) ?? [])
              const cells: number[] = []
              for (let f = 0; f < N; f++) cells.push(f)
              return (
                <g key={p.record.index}>
                  <text x={ML - 8} y={top + STRIP_H - 1} fontSize={10} textAnchor="end" fill={INK.muted}>
                    p{p.record.index} mover
                  </text>
                  <text x={ML - 8} y={top + 2 * STRIP_H - 1} fontSize={10} textAnchor="end" fill={INK.muted}>
                    p{p.record.index} barrier
                  </text>
                  {cells.map((f) => (
                    <g key={f}>
                      <rect x={x(f) - cellW / 2 + 1} y={top} width={Math.max(1, cellW - 2)} height={STRIP_H - 1} fill={mover.has(f) ? CONCEPT.mover : INK.grid} />
                      <rect x={x(f) - cellW / 2 + 1} y={top + STRIP_H} width={Math.max(1, cellW - 2)} height={STRIP_H - 1} fill={barrier.has(f) ? CONCEPT.barrier : INK.grid} />
                    </g>
                  ))}
                </g>
              )
            })}
            {/* hit area */}
            <rect
              x={ML - cellW / 2}
              y={MT - 10}
              width={W - ML - MR + cellW}
              height={PLOT_H + MB + stripsH + 10}
              fill="transparent"
              style={{ cursor: 'crosshair', touchAction: 'none' }}
              onPointerMove={onMove}
              onPointerDown={onDown}
              onPointerUp={onUp}
              onPointerLeave={() => player.setHover(null)}
            />
          </svg>
          <Collapsible summary="E(t) table — every frame, every pass (the chart's text twin)" className="mt-3">
            <ResidualTable passes={passes} N={N} />
          </Collapsible>
        </div>
        <div className="min-w-0 space-y-4">
          {passes.map((p) => (
            <div key={p.record.index} className="rounded-lg border border-line bg-surface/50 p-3">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <span className="inline-flex items-center gap-1.5 text-xs text-ink-2">
                  <Swatch color={passColor(p.record.index)} /> pass {p.record.index} — {p.record.label}
                </span>
                <VerdictBadge status={p.record.verification_status} tFail={p.record.t_fail} size="sm" caption={false} />
              </div>
              <CoverageBars pass={p} />
              {p.verification?.reasons.length ? <p className="mt-2 text-[11px] leading-snug text-ink-3">verifier: {p.verification.reasons.join('; ')}</p> : null}
            </div>
          ))}
          <p className="text-[11px] leading-snug text-ink-3">Verdicts above are from the verifier over SAM 3.1 tracks; tool status and model text are never consulted.</p>
        </div>
      </div>
    </Section>
  )
}

function ResidualTable({ passes, N }: { passes: LoadedPass[]; N: number }) {
  const rows: number[] = []
  for (let f = 0; f < N; f++) rows.push(f)
  return (
    <div className="max-h-80 overflow-auto">
      <table className="mono num w-full text-right text-[11px]">
        <thead className="sticky top-0 bg-card text-ink-3">
          <tr>
            <th className="px-2 py-1 text-left">frame</th>
            {passes.map((p) => (
              <th key={p.record.index} className="px-2 py-1" colSpan={3}>
                pass {p.record.index}: E · mover bottom · barrier bottom
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((f) => (
            <tr key={f} className="border-t border-line/60">
              <td className="px-2 py-0.5 text-left text-ink-3">{f}</td>
              {passes.map((p) => {
                const v = p.verification
                const e = v?.residual[f] ?? null
                const tf = v?.t_fail != null && f >= v.t_fail && (v.violation_run ?? []).includes(f)
                return (
                  <FragmentCells key={p.record.index} e={e} mb={v?.mover_bottom[f] ?? null} bb={v?.barrier_bottom[f] ?? null} violation={!!tf} />
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function FragmentCells({ e, mb, bb, violation }: { e: number | null; mb: number | null; bb: number | null; violation: boolean }) {
  return (
    <>
      <td className={`px-2 py-0.5 ${violation ? 'text-bad' : 'text-ink'}`}>{e == null ? '—' : fmtPx(e)}</td>
      <td className="px-2 py-0.5 text-ink-2">{mb == null ? '—' : mb.toFixed(0)}</td>
      <td className="px-2 py-0.5 text-ink-2">{bb == null ? '—' : bb.toFixed(0)}</td>
    </>
  )
}
