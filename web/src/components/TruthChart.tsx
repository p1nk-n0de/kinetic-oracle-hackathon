import { useMemo } from 'react'
import type { LoadedPass } from '../types'
import { fmtSigned, frameTime } from '../lib/format'
import { INK, SURFACE, passColor } from '../lib/theme'
import { usePlayer } from '../lib/playerStore'
import { Swatch } from './ui'

const W = 1000
const H = 230
const ML = 56
const MR = 24
const MT = 22
const MB = 26

/** Engine ground truth: the player's z (metres, −Z is forward) per captured frame, one line per pass. */
export function TruthChart({ passes }: { passes: LoadedPass[] }) {
  const { frame, frameCount: N, fps } = usePlayer()
  const withTruth = passes.filter((p) => p.truth && p.truth.rows.length)
  const { zmin, zmax } = useMemo(() => {
    let lo = Infinity
    let hi = -Infinity
    for (const p of withTruth) for (const r of p.truth?.rows ?? []) (lo = Math.min(lo, r.z)), (hi = Math.max(hi, r.z))
    if (!Number.isFinite(lo)) return { zmin: -1, zmax: 1 }
    const pad = Math.max(0.5, (hi - lo) * 0.08)
    return { zmin: lo - pad, zmax: hi + pad }
  }, [withTruth])
  const x = (f: number) => ML + (f / Math.max(1, N - 1)) * (W - ML - MR)
  const y = (z: number) => MT + (1 - (z - zmin) / (zmax - zmin)) * (H - MT - MB)
  const ticks = useMemo(() => {
    const span = zmax - zmin
    const step = span > 12 ? 4 : span > 6 ? 2 : span > 3 ? 1 : 0.5
    const out: number[] = []
    for (let v = Math.ceil(zmin / step) * step; v <= zmax; v += step) out.push(Math.round(v * 100) / 100)
    return out
  }, [zmin, zmax])

  if (withTruth.length === 0) return <p className="text-xs text-ink-3">No truth_hidden.json in this bundle.</p>

  // put the readout in whichever left corner the early frames leave empty
  const early = withTruth.flatMap((p) => (p.truth?.rows ?? []).filter((r) => r.frame < N * 0.3).map((r) => y(r.z)))
  const earlyMean = early.length ? early.reduce((a, b) => a + b, 0) / early.length : MT
  const boxH = 18 + 15 * withTruth.length
  const readoutTop = earlyMean < MT + (H - MT - MB) / 2 ? H - MB - boxH - 6 : MT + 4

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center gap-3 text-xs text-ink-2">
        {withTruth.map((p) => (
          <span key={p.record.index} className="inline-flex items-center gap-1.5">
            <Swatch color={passColor(p.record.index)} /> pass {p.record.index} — {p.record.label}
            <span className="text-ink-3">({p.truth?.format})</span>
          </span>
        ))}
        <span className="ml-auto text-ink-3">player z (m), −Z is forward · cursor follows the player</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="block w-full" role="img" aria-label="engine ground truth: player z per frame">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={ML} x2={W - MR} y1={y(t)} y2={y(t)} stroke={INK.grid} />
            <text x={ML - 8} y={y(t) + 4} fontSize={11} textAnchor="end" fill={INK.muted} className="num">
              {t}
            </text>
          </g>
        ))}
        {Array.from({ length: Math.ceil(N / 10) + 1 }, (_, i) => Math.min(N - 1, i * 10)).map((f) => (
          <text key={f} x={x(f)} y={H - MB + 16} fontSize={11} textAnchor="middle" fill={INK.muted} className="num">
            {f}
          </text>
        ))}
        <text x={12} y={MT + (H - MT - MB) / 2} fontSize={11} fill={INK.muted} transform={`rotate(-90 12 ${MT + (H - MT - MB) / 2})`} textAnchor="middle">
          z (m)
        </text>
        {withTruth.map((p) => {
          const rows = (p.truth?.rows ?? []).filter((r) => r.frame < N)
          const d = rows.map((r, i) => `${i === 0 ? 'M' : 'L'}${x(r.frame).toFixed(1)} ${y(r.z).toFixed(1)}`).join(' ')
          const last = rows[rows.length - 1]
          const c = passColor(p.record.index)
          return (
            <g key={p.record.index}>
              <path d={d} fill="none" stroke={c} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
              {last && (
                <>
                  <circle cx={x(last.frame)} cy={y(last.z)} r={4} fill={c} stroke={SURFACE} strokeWidth={2} />
                  <text x={x(last.frame) - 8} y={y(last.z) + (p.record.index % 2 ? -8 : 16)} fontSize={11} textAnchor="end" fill={INK.secondary} className="num">
                    pass {p.record.index} ends at z = {last.z.toFixed(2)} m
                  </text>
                </>
              )}
            </g>
          )
        })}
        <line x1={x(frame)} x2={x(frame)} y1={MT - 4} y2={H - MB + 4} stroke={INK.primary} opacity={0.85} />
        {withTruth.map((p) => {
          const r = p.truth?.rows.find((q) => q.frame === frame)
          return r ? <circle key={p.record.index} cx={x(frame)} cy={y(r.z)} r={4.5} fill={passColor(p.record.index)} stroke={SURFACE} strokeWidth={2} /> : null
        })}
        <g transform={`translate(${ML + 10} ${readoutTop})`}>
          <rect x={0} y={0} width={220} height={18 + 15 * withTruth.length} rx={4} fill="#131a29" opacity={0.92} stroke={INK.grid} />
          <text x={8} y={13} fontSize={11} fill={INK.secondary} className="num">
            frame {frame} · {frameTime(frame, fps)}
          </text>
          {withTruth.map((p, i) => {
            const r = p.truth?.rows.find((q) => q.frame === frame)
            return (
              <g key={p.record.index} transform={`translate(8 ${28 + i * 15})`}>
                <rect x={0} y={-8} width={10} height={3} fill={passColor(p.record.index)} />
                <text x={16} y={0} fontSize={11} fill={INK.primary} className="num">
                  pass {p.record.index}: {r ? `z ${fmtSigned(r.z, 2)} m · vz ${fmtSigned(r.vz, 1)} · y ${fmtSigned(r.y, 3)}` : 'no row'}
                </text>
              </g>
            )
          })}
        </g>
      </svg>
    </div>
  )
}
