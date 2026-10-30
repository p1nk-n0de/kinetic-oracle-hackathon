import { useCallback, useEffect, useMemo, useRef } from 'react'
import type { LoadedRun } from '../types'
import { frameTime } from '../lib/format'
import { player, usePlayer, type Source } from '../lib/playerStore'
import { Btn, IconBtn, Section, Segmented } from './ui'
import { VideoPane } from './VideoPane'

function paneTitles(run: LoadedRun): { left: [string, string]; right: [string, string] } {
  const p1 = run.passes[0]?.record
  const pl = run.passes[run.passes.length - 1]?.record
  if (run.manifest.kind === 'closed_loop') {
    return {
      left: ['The agent that believed its tool: MCP said OK', `pass ${p1?.index ?? 1} · ${p1?.label ?? ''} · before any repair`],
      right: ['After Muse repair via Godot MCP', pl ? `pass ${pl.index} · ${pl.label} · patched, relaunched, re-captured` : 'no repair pass'],
    }
  }
  return {
    left: [`Pass ${p1?.index ?? 1} — ${p1?.label ?? ''}`, 'pre-captured clip, tracked and verified live'],
    right: [pl ? `Pass ${pl.index} — ${pl.label}` : 'Pass 2', 'pre-captured clip, tracked and verified live'],
  }
}

export function SplitPlayer({ run }: { run: LoadedRun }) {
  const st = usePlayer()
  const { frame, frameCount: N, fps, playing, rate, loop, source, boxes } = st
  const left = run.passes[0] ?? null
  const right = run.passes.length > 1 ? (run.passes[run.passes.length - 1] ?? null) : null
  const titles = useMemo(() => paneTitles(run), [run])
  const videos = useRef<Map<string, HTMLVideoElement>>(new Map())

  const setVideo = useCallback(
    (key: string) => (el: HTMLVideoElement | null) => {
      if (el) videos.current.set(key, el)
      else videos.current.delete(key)
    },
    [],
  )
  const leftRef = useMemo(() => setVideo('left'), [setVideo])
  const rightRef = useMemo(() => setVideo('right'), [setVideo])

  /** Frame-accurate seek: the middle of frame f is (f + 0.5) / fps. */
  const seekAll = useCallback(
    (f: number) => {
      const t = (f + 0.5) / fps
      videos.current.forEach((v) => {
        if (Math.abs(v.currentTime - t) > 1e-4) v.currentTime = t
      })
    },
    [fps],
  )

  useEffect(() => {
    if (!playing) seekAll(frame)
  }, [frame, playing, source, seekAll])

  const onLoaded = useCallback(() => {
    if (!player.get().playing) seekAll(player.get().frame)
  }, [seekAll])

  useEffect(() => {
    if (!playing) {
      videos.current.forEach((v) => v.pause())
      return
    }
    const vids = Array.from(videos.current.values())
    const master = vids[0]
    if (!master) {
      player.pause()
      return
    }
    let raf = 0
    let cancelled = false
    const startFrame = player.get().frame >= N - 1 ? 0 : player.get().frame
    for (const v of vids) {
      v.playbackRate = rate
      v.currentTime = startFrame / fps + 1e-3
    }
    const tick = () => {
      if (cancelled) return
      const t = master.currentTime
      const f = Math.min(N - 1, Math.max(0, Math.floor(t * fps + 1e-3)))
      player.tick(f)
      for (const v of vids) {
        if (v !== master && Math.abs(v.currentTime - t) > 0.75 / fps) v.currentTime = t
      }
      if (master.ended || t >= (N - 0.5) / fps) {
        if (player.get().loop) {
          for (const v of vids) {
            v.currentTime = 0
            void v.play().catch(() => undefined)
          }
        } else {
          player.seek(N - 1)
          return
        }
      }
      raf = requestAnimationFrame(tick)
    }
    Promise.all(vids.map((v) => v.play().catch(() => undefined))).then(() => {
      if (!cancelled) raf = requestAnimationFrame(tick)
    })
    return () => {
      cancelled = true
      cancelAnimationFrame(raf)
      for (const v of vids) v.pause()
    }
  }, [playing, rate, fps, N])

  // keyboard: space play/pause, arrows step (shift = 5 frames), home/end
  useEffect(() => {
    const onKey = (ev: KeyboardEvent) => {
      const tgt = ev.target as HTMLElement | null
      const isRange = tgt instanceof HTMLInputElement && tgt.type === 'range'
      if (isRange) {
        // the scrubber keeps focus after a drag: space must still play/pause; arrows/Home/End already move the slider natively
        if (ev.key === ' ') {
          ev.preventDefault()
          player.toggle()
        }
        return
      }
      if (tgt && ['INPUT', 'SELECT', 'TEXTAREA', 'BUTTON'].includes(tgt.tagName)) return
      if (ev.key === ' ') {
        ev.preventDefault()
        player.toggle()
      } else if (ev.key === 'ArrowLeft') {
        ev.preventDefault()
        player.step(ev.shiftKey ? -5 : -1)
      } else if (ev.key === 'ArrowRight') {
        ev.preventDefault()
        player.step(ev.shiftKey ? 5 : 1)
      } else if (ev.key === 'Home') {
        player.seek(0)
      } else if (ev.key === 'End') {
        player.seek(player.get().frameCount - 1)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const tFails = run.passes.filter((p) => p.record.t_fail != null).map((p) => ({ pass: p.record.index, f: p.record.t_fail as number }))
  const isClosedLoop = run.manifest.kind === 'closed_loop'

  return (
    <Section
      id="player"
      title="Split-screen player — one scrubber, two clips, frame-locked"
      subtitle={`${N} frames @ ${fps} fps · ${run.contract?.frame_size.join('×') ?? '960×540'} px · both videos seek to (frame + 0.5) / fps · boxes and bottom edges are redrawn from tracks.json for the current frame`}
      right={
        <>
          <Segmented<Source>
            ariaLabel="video source"
            value={source}
            onChange={player.setSource}
            options={[
              { value: 'overlay', label: 'overlay.mp4', title: 'masks, boxes and HUD burned in by the pipeline' },
              { value: 'clip', label: 'clip.mp4', title: 'the raw frames SAM 3.1 received' },
            ]}
          />
          <Btn active={boxes} onClick={() => player.setBoxes(!boxes)} title="draw boxes / bottom edges / E(t) gauge from tracks.json on a canvas layer">
            live boxes {boxes ? 'on' : 'off'}
          </Btn>
        </>
      }
    >
      <div className="grid gap-5 lg:grid-cols-2">
        <VideoPane
          title={titles.left[0]}
          subtitle={titles.left[1]}
          pass={left}
          contract={run.contract}
          frame={frame}
          source={source}
          boxes={boxes}
          videoRef={leftRef}
          onLoaded={onLoaded}
          showOpenLoop={isClosedLoop}
        />
        <VideoPane
          title={titles.right[0]}
          subtitle={titles.right[1]}
          pass={right}
          contract={run.contract}
          frame={frame}
          source={source}
          boxes={boxes}
          videoRef={rightRef}
          onLoaded={onLoaded}
          showOpenLoop={isClosedLoop}
        />
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3 rounded-lg border border-line bg-card-2/60 px-3 py-2">
        <div className="flex items-center gap-1">
          <IconBtn name="skip-start" title="first frame (Home)" onClick={() => player.seek(0)} />
          <IconBtn name="step-back" title="previous frame (←)" onClick={() => player.step(-1)} />
          <IconBtn name={playing ? 'pause' : 'play'} title={playing ? 'pause (space)' : 'play (space)'} onClick={player.toggle} big />
          <IconBtn name="step-fwd" title="next frame (→)" onClick={() => player.step(1)} />
          <IconBtn name="skip-end" title="last frame (End)" onClick={() => player.seek(N - 1)} />
        </div>
        <input
          type="range"
          min={0}
          max={N - 1}
          step={1}
          value={frame}
          aria-label="frame"
          onChange={(ev) => player.seek(Number(ev.target.value))}
          className="min-w-[10rem] flex-1"
        />
        <span className="mono num whitespace-nowrap text-sm text-ink">
          f {String(frame).padStart(2, '0')} <span className="text-ink-3">/ {N - 1}</span> · {frameTime(frame, fps)}
        </span>
        <label className="flex items-center gap-1 text-xs text-ink-2">
          speed
          <select value={rate} onChange={(ev) => player.setRate(Number(ev.target.value))} className="rounded-md border border-line-2 bg-card-2 px-1.5 py-1 text-xs text-ink">
            <option value={0.25}>0.25×</option>
            <option value={0.5}>0.5×</option>
            <option value={1}>1×</option>
          </select>
        </label>
        <Btn active={loop} onClick={() => player.setLoop(!loop)} title="restart at the end">
          loop
        </Btn>
        {tFails.map((t) => (
          <Btn key={t.pass} onClick={() => player.seek(t.f)} title={`jump to the verifier's t_fail of pass ${t.pass}`}>
            → t_fail pass {t.pass}: f{t.f}
          </Btn>
        ))}
        {run.contract && (
          <Btn onClick={() => player.seek(run.contract?.coverage.critical_window[0] ?? 0)} title="start of the contract's critical window">
            → window start f{run.contract.coverage.critical_window[0]}
          </Btn>
        )}
      </div>
    </Section>
  )
}
