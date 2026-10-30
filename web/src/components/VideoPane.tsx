import { useEffect, useMemo, useRef } from 'react'
import type { LoadedPass, SensoryContract, TrackPoint, Tracks } from '../types'
import { fmtPx, frameTime } from '../lib/format'
import { OVERLAY, STATUS } from '../lib/theme'
import type { Source } from '../lib/playerStore'
import { OpenLoopBadge, VerdictBadge } from './VerdictBadge'
import { Empty } from './ui'

interface Props {
  title: string
  subtitle: string
  pass: LoadedPass | null
  contract: SensoryContract | null
  frame: number
  source: Source
  boxes: boolean
  videoRef: (el: HTMLVideoElement | null) => void
  onLoaded: () => void
  showOpenLoop: boolean
}

function indexPoints(tracks: Tracks | null): { mover: Map<number, TrackPoint>; barrier: Map<number, TrackPoint> } {
  const mover = new Map<number, TrackPoint>()
  const barrier = new Map<number, TrackPoint>()
  if (tracks) {
    for (const p of tracks.mover.points) mover.set(p.frame, p)
    for (const p of tracks.barrier.points) barrier.set(p.frame, p)
  }
  return { mover, barrier }
}

function drawLabel(ctx: CanvasRenderingContext2D, text: string, x: number, y: number, color: string) {
  ctx.font = '600 15px system-ui, sans-serif'
  const w = ctx.measureText(text).width + 10
  ctx.fillStyle = 'rgba(10, 14, 23, 0.78)'
  ctx.fillRect(x, y - 19, w, 20)
  ctx.fillStyle = color
  ctx.fillText(text, x + 5, y - 4)
}

function drawTrackPoint(ctx: CanvasRenderingContext2D, p: TrackPoint, color: string, label: string, W: number) {
  ctx.lineWidth = 2.5
  ctx.strokeStyle = color
  ctx.strokeRect(p.x1 + 0.5, p.y1 + 0.5, p.x2 - p.x1, p.y2 - p.y1)
  // bottom edge: the quantity the contract measures
  ctx.lineWidth = 2
  ctx.beginPath()
  ctx.moveTo(Math.max(0, p.x1 - 14), p.bottom + 0.5)
  ctx.lineTo(Math.min(W, p.x2 + 14), p.bottom + 0.5)
  ctx.stroke()
  ctx.fillStyle = color
  ctx.beginPath()
  ctx.arc(p.cx, p.cy, 4, 0, Math.PI * 2)
  ctx.fill()
  drawLabel(ctx, label, p.x1, Math.max(20, p.y1 - 3), color)
}

export function VideoPane({ title, subtitle, pass, contract, frame, source, boxes, videoRef, onLoaded, showOpenLoop }: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const [W, H] = contract?.frame_size ?? pass?.tracks?.mover.frame_size ?? [960, 540]
  const fps = contract?.fps ?? 20
  const pts = useMemo(() => indexPoints(pass?.tracks ?? null), [pass])
  const ver = pass?.verification ?? null
  const residual = ver?.residual ?? []
  const e = residual[frame] ?? null
  const threshold = contract?.rule.threshold_px ?? 0

  useEffect(() => {
    const c = canvasRef.current
    if (!c) return
    const ctx = c.getContext('2d')
    if (!ctx) return
    ctx.clearRect(0, 0, c.width, c.height)
    if (!boxes || !pass?.tracks) return
    const m = pts.mover.get(frame)
    const b = pts.barrier.get(frame)
    if (b) drawTrackPoint(ctx, b, OVERLAY.barrier, `${pass.tracks.barrier.concept} #${pass.tracks.barrier.object_id ?? '?'}`, W)
    if (m) drawTrackPoint(ctx, m, OVERLAY.mover, `${pass.tracks.mover.concept} #${pass.tracks.mover.object_id ?? '?'}`, W)
    if (m && b && e != null) {
      // residual gauge: barrier bottom -> mover bottom, drawn to the right of both boxes
      const x = Math.min(W - 60, Math.max(m.x2, b.x2) + 34)
      const violating = e > threshold
      const color = violating ? STATUS.fail : '#f0efec'
      ctx.strokeStyle = color
      ctx.fillStyle = color
      ctx.lineWidth = 2
      ctx.setLineDash(violating ? [] : [5, 4])
      ctx.beginPath()
      ctx.moveTo(x, b.bottom)
      ctx.lineTo(x, m.bottom)
      ctx.stroke()
      ctx.setLineDash([])
      for (const y of [b.bottom, m.bottom]) {
        ctx.beginPath()
        ctx.moveTo(x - 6, y + 0.5)
        ctx.lineTo(x + 6, y + 0.5)
        ctx.stroke()
      }
      const ly = Math.min(m.bottom, b.bottom) + Math.abs(m.bottom - b.bottom) / 2
      drawLabel(ctx, `E = ${fmtPx(e)}`, x + 10, ly + 8, color)
    }
  }, [frame, pts, boxes, pass, W, e, threshold])

  const src = pass ? (source === 'overlay' ? (pass.overlayUrl ?? pass.clipUrl) : pass.clipUrl) : null
  const statusText = (() => {
    if (!ver) return null
    if (ver.t_fail != null && frame >= ver.t_fail) return { text: `VIOLATION since frame ${ver.t_fail}`, tone: STATUS.fail }
    if (frame === (ver.frame_count ?? 80) - 1) return { text: ver.status, tone: ver.status === 'PASS' ? STATUS.pass : STATUS.inconclusive }
    return { text: 'tracking', tone: '#c3c2b7' }
  })()
  const mb = ver?.mover_bottom[frame] ?? null
  const bb = ver?.barrier_bottom[frame] ?? null

  return (
    <div className="flex min-w-0 flex-col gap-2">
      <div className="min-w-0">
        <h3 className="truncate text-sm font-semibold text-ink" title={title}>
          {title}
        </h3>
        <p className="truncate text-xs text-ink-3">{subtitle}</p>
      </div>
      <div className="relative aspect-video w-full overflow-hidden rounded-lg border border-line bg-black">
        {src ? (
          <video
            key={src}
            ref={videoRef}
            src={src}
            muted
            playsInline
            preload="auto"
            onLoadedData={onLoaded}
            className="absolute inset-0 h-full w-full"
          />
        ) : (
          <div className="absolute inset-0 flex items-center justify-center p-6">
            <Empty>No second pass in this bundle: the run ended before a repair was re-captured.</Empty>
          </div>
        )}
        <canvas ref={canvasRef} width={W} height={H} className="pointer-events-none absolute inset-0 h-full w-full" aria-hidden="true" />
        {pass && source !== 'overlay' && (
          <div className="pointer-events-none absolute left-2 top-2 rounded bg-plane/70 px-2 py-0.5 text-[11px] text-ink-2">
            pass {pass.record.index} · raw clip (what SAM received)
            {boxes ? ' + live boxes from tracks.json' : ''}
          </div>
        )}
      </div>
      {pass && (
        <div className="mono num flex flex-wrap items-center gap-x-4 gap-y-1 rounded-md border border-line bg-surface/60 px-3 py-1.5 text-xs text-ink-2">
          <span>
            f <span className="text-ink">{String(frame).padStart(2, '0')}</span> · {frameTime(frame, fps)}
          </span>
          <span>
            E(t) <span className="font-semibold text-ink">{fmtPx(e)}</span>
          </span>
          <span title="y_bottom of the mover box, source pixels">
            <span style={{ color: OVERLAY.mover }}>●</span> bottom {mb == null ? 'untracked' : mb.toFixed(0)}
          </span>
          <span title="y_bottom of the barrier box, source pixels">
            <span style={{ color: OVERLAY.barrier }}>●</span> bottom {bb == null ? 'untracked' : bb.toFixed(0)}
          </span>
          {statusText && (
            <span className="ml-auto font-sans font-semibold" style={{ color: statusText.tone }}>
              {statusText.text}
            </span>
          )}
        </div>
      )}
      {pass && (
        <div className="flex flex-wrap items-start gap-x-4 gap-y-2">
          {showOpenLoop && <OpenLoopBadge openLoop={pass.record.open_loop} size="sm" />}
          <VerdictBadge status={pass.record.verification_status} tFail={pass.record.t_fail} size="sm" />
        </div>
      )}
    </div>
  )
}
