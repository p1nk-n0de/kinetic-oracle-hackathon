import type { VerificationStatus } from '../types'

export const VERDICT_CAPTION = 'from the verifier over SAM 3.1 tracks; tool status and model text are never consulted'

export function shortHash(h: string | null | undefined, n = 12): string {
  if (!h) return '—'
  return h.length > n ? `${h.slice(0, n)}…` : h
}

export function fmtPx(v: number | null | undefined, digits = 0): string {
  if (v == null || !Number.isFinite(v)) return 'n/a'
  const sign = v > 0 ? '+' : v < 0 ? '−' : ''
  return `${sign}${Math.abs(v).toFixed(digits)} px`
}

export function fmtSigned(v: number | null | undefined, digits = 1): string {
  if (v == null || !Number.isFinite(v)) return 'n/a'
  const sign = v > 0 ? '+' : v < 0 ? '−' : ''
  return `${sign}${Math.abs(v).toFixed(digits)}`
}

export function fmtUsd(v: number | null | undefined, digits = 4): string {
  if (v == null || !Number.isFinite(v)) return '—'
  return `$${v.toFixed(digits)}`
}

export function fmtPct(v: number | null | undefined, digits = 0): string {
  if (v == null || !Number.isFinite(v)) return '—'
  return `${(v * 100).toFixed(digits)}%`
}

export function fmtBytes(n: number | null | undefined): string {
  if (n == null) return '—'
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / (1024 * 1024)).toFixed(2)} MB`
}

export function fmtInt(n: number | null | undefined): string {
  return n == null ? '—' : n.toLocaleString('en-GB')
}

export function fmtIso(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toISOString().replace('T', ' ').replace(/\.\d+Z$/, 'Z').replace(/Z$/, ' UTC')
}

export function fmtClock(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toISOString().slice(11, 19)
}

export function frameTime(frame: number, fps: number): string {
  return `${(frame / fps).toFixed(2)} s`
}

export function statusTone(status: VerificationStatus | string | null | undefined): 'pass' | 'fail' | 'inconclusive' | 'error' {
  switch (status) {
    case 'PASS':
      return 'pass'
    case 'FAIL':
      return 'fail'
    case 'INCONCLUSIVE':
      return 'inconclusive'
    default:
      return 'error'
  }
}

export function durationBetween(a: string | null | undefined, b: string | null | undefined): string {
  if (!a || !b) return '—'
  const ms = new Date(b).getTime() - new Date(a).getTime()
  if (!Number.isFinite(ms)) return '—'
  const s = Math.round(ms / 1000)
  return s < 60 ? `${s} s` : `${Math.floor(s / 60)} min ${s % 60} s`
}

export function kindLabel(kind: string): string {
  if (kind === 'closed_loop') return 'closed loop'
  if (kind === 'clip_evaluation') return 'clip evaluation'
  return kind
}

export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(' ')
}
