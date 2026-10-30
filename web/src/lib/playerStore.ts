import { useSyncExternalStore } from 'react'

export type Source = 'overlay' | 'clip'

export interface PlayerState {
  frame: number
  frameCount: number
  fps: number
  playing: boolean
  rate: number
  loop: boolean
  source: Source
  boxes: boolean
  /** Hover frame on the chart (not applied to the player while playing). */
  hover: number | null
}

let state: PlayerState = {
  frame: 0,
  frameCount: 80,
  fps: 20,
  playing: false,
  rate: 1,
  loop: false,
  source: 'overlay',
  boxes: true,
  hover: null,
}

const listeners = new Set<() => void>()

function emit() {
  for (const l of listeners) l()
}

function set(partial: Partial<PlayerState>) {
  state = { ...state, ...partial }
  emit()
}

function clampFrame(f: number): number {
  if (!Number.isFinite(f)) return 0
  return Math.min(state.frameCount - 1, Math.max(0, Math.round(f)))
}

export const player = {
  get: () => state,
  subscribe(fn: () => void) {
    listeners.add(fn)
    return () => {
      listeners.delete(fn)
    }
  },
  configure(frameCount: number, fps: number) {
    set({ frameCount: Math.max(1, frameCount), fps: fps > 0 ? fps : 20, frame: 0, playing: false, hover: null })
  },
  /** Scrub: pauses and seeks. */
  seek(f: number) {
    set({ frame: clampFrame(f), playing: false })
  },
  /** Playback clock update: frame only, no seek side effects. */
  tick(f: number) {
    const c = clampFrame(f)
    if (c !== state.frame) set({ frame: c })
  },
  step(delta: number) {
    set({ frame: clampFrame(state.frame + delta), playing: false })
  },
  play() {
    if (!state.playing) set({ playing: true })
  },
  pause() {
    if (state.playing) set({ playing: false })
  },
  toggle() {
    set({ playing: !state.playing })
  },
  setRate(rate: number) {
    set({ rate })
  },
  setLoop(loop: boolean) {
    set({ loop })
  },
  setSource(source: Source) {
    set({ source })
  },
  setBoxes(boxes: boolean) {
    set({ boxes })
  },
  setHover(hover: number | null) {
    if (hover !== state.hover) set({ hover })
  },
}

export function usePlayer(): PlayerState {
  return useSyncExternalStore(player.subscribe, player.get, player.get)
}
