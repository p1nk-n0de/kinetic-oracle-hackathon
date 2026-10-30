// Colour roles. Chart marks were validated with the dataviz palette validator against the dark
// surface (#0f1420). Overlay colours on the video follow the Python overlay renderer
// (mover green, barrier magenta) so the live-drawn boxes agree with the burned-in ones.

export const SURFACE = '#0f1420'

/** Per-pass series colours (fixed order, never cycled: pass 1 is always orange). */
export const PASS_COLORS = ['#d95926', '#3987e5', '#199e70', '#c98500'] as const

export function passColor(index: number): string {
  const i = Math.max(0, index - 1) % PASS_COLORS.length
  return PASS_COLORS[i] ?? PASS_COLORS[0]
}

/** Concept identity on the video canvas (bright, to read over game pixels). */
export const OVERLAY = {
  mover: '#4ade80',
  barrier: '#f472b6',
} as const

/** Concept identity in charts and strips (darker steps for the dark surface). */
export const CONCEPT = {
  mover: '#1fa36b',
  barrier: '#c9519e',
} as const

/** Status palette: reserved for verdicts, never reused for series. */
export const STATUS = {
  pass: '#0ca30c',
  fail: '#d03b3b',
  inconclusive: '#fab219',
  error: '#898781',
} as const

export const INK = {
  primary: '#f0efec',
  secondary: '#c3c2b7',
  muted: '#898781',
  grid: '#1e2535',
  axis: '#2d3547',
} as const
