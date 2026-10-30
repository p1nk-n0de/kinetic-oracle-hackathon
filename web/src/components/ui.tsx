import { useState, type ReactNode } from 'react'
import { cx, shortHash } from '../lib/format'

export function Section({
  id,
  title,
  subtitle,
  right,
  children,
  className,
}: {
  id?: string
  title: ReactNode
  subtitle?: ReactNode
  right?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section id={id} className={cx('rounded-xl border border-line bg-card/70', className)}>
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-5 py-3">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold tracking-wide text-ink">{title}</h2>
          {subtitle && <p className="mt-0.5 text-xs text-ink-3">{subtitle}</p>}
        </div>
        {right && <div className="flex flex-wrap items-center gap-2">{right}</div>}
      </header>
      <div className="px-5 py-4">{children}</div>
    </section>
  )
}

export function SubHead({ children, right }: { children: ReactNode; right?: ReactNode }) {
  return (
    <div className="mb-2 flex items-center justify-between gap-3">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-ink-3">{children}</h3>
      {right}
    </div>
  )
}

export function Kv({ items, className }: { items: [ReactNode, ReactNode][]; className?: string }) {
  return (
    <dl className={cx('kv', className)}>
      {items.map(([k, v], i) => (
        <div key={i} className="contents">
          <dt>{k}</dt>
          <dd>{v}</dd>
        </div>
      ))}
    </dl>
  )
}

export function Hash({ value, n = 12, className, full = false }: { value: string | null | undefined; n?: number; className?: string; full?: boolean }) {
  const [copied, setCopied] = useState(false)
  if (!value) return <span className={cx('text-ink-3', className)}>—</span>
  const copy = async () => {
    try {
      await navigator.clipboard?.writeText(value)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 900)
    } catch {
      /* clipboard unavailable: nothing to do */
    }
  }
  return (
    <button
      type="button"
      onClick={copy}
      title={`${value}\n(click to copy)`}
      className={cx('mono inline-block cursor-copy rounded px-1 text-left text-xs text-ink-2 hover:bg-card-2 hover:text-ink', className)}
    >
      {copied ? 'copied' : full ? value : shortHash(value, n)}
    </button>
  )
}

export type Tone = 'neutral' | 'ok' | 'bad' | 'warn' | 'info' | 'mover' | 'barrier' | 'truth'

const TONE_CLASS: Record<Tone, string> = {
  neutral: 'border-line-2 bg-card-2 text-ink-2',
  ok: 'border-ok/50 bg-ok/10 text-ink',
  bad: 'border-bad/60 bg-bad/10 text-ink',
  warn: 'border-warn/60 bg-warn/10 text-ink',
  info: 'border-pass2/60 bg-pass2/10 text-ink',
  mover: 'border-mover/60 bg-mover/10 text-ink',
  barrier: 'border-barrier/60 bg-barrier/10 text-ink',
  truth: 'border-truth/60 bg-truth/10 text-ink',
}

export function Pill({ children, tone = 'neutral', className, title }: { children: ReactNode; tone?: Tone; className?: string; title?: string }) {
  return (
    <span title={title} className={cx('inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-medium', TONE_CLASS[tone], className)}>
      {children}
    </span>
  )
}

export function Check({ ok, yes = 'yes', no = 'no', unknown = 'unknown' }: { ok: boolean | null | undefined; yes?: string; no?: string; unknown?: string }) {
  if (ok == null) return <span className="text-ink-3">? {unknown}</span>
  return ok ? (
    <span className="text-ink">
      <span className="text-ok">✓</span> {yes}
    </span>
  ) : (
    <span className="text-ink">
      <span className="text-bad">✗</span> {no}
    </span>
  )
}

export function Collapsible({ summary, children, open, className }: { summary: ReactNode; children: ReactNode; open?: boolean; className?: string }) {
  return (
    <details open={open} className={cx('group rounded-lg border border-line bg-surface/40', className)}>
      <summary className="px-3 py-2 text-xs font-medium text-ink-2 hover:text-ink">{summary}</summary>
      <div className="border-t border-line px-3 py-3">{children}</div>
    </details>
  )
}

export function JsonView({ value, maxChars = 6000, className }: { value: unknown; maxChars?: number; className?: string }) {
  const [all, setAll] = useState(false)
  const text = typeof value === 'string' ? value : JSON.stringify(value, null, 1)
  const truncated = !all && text.length > maxChars
  return (
    <div className={className}>
      <pre className="block max-h-96 overflow-auto">{truncated ? `${text.slice(0, maxChars)}\n…` : text}</pre>
      {text.length > maxChars && (
        <button type="button" className="mt-1 text-xs text-pass2 hover:underline" onClick={() => setAll((v) => !v)}>
          {all ? 'show less' : `show all ${text.length.toLocaleString()} characters`}
        </button>
      )}
    </div>
  )
}

export function Btn({
  children,
  onClick,
  active,
  title,
  disabled,
  className,
  size = 'sm',
}: {
  children: ReactNode
  onClick?: () => void
  active?: boolean
  title?: string
  disabled?: boolean
  className?: string
  size?: 'sm' | 'xs'
}) {
  return (
    <button
      type="button"
      title={title}
      disabled={disabled}
      onClick={onClick}
      className={cx(
        'inline-flex items-center gap-1 rounded-md border transition-colors',
        size === 'sm' ? 'px-2.5 py-1 text-xs' : 'px-2 py-0.5 text-[11px]',
        active ? 'border-ink/60 bg-ink/10 text-ink' : 'border-line-2 bg-card-2 text-ink-2 hover:border-ink-3 hover:text-ink',
        disabled && 'cursor-not-allowed opacity-40',
        className,
      )}
    >
      {children}
    </button>
  )
}

export function Segmented<T extends string>({ value, options, onChange, ariaLabel }: { value: T; options: { value: T; label: string; title?: string }[]; onChange: (v: T) => void; ariaLabel?: string }) {
  return (
    <div role="group" aria-label={ariaLabel} className="inline-flex overflow-hidden rounded-md border border-line-2">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          title={o.title}
          onClick={() => onChange(o.value)}
          className={cx('px-2.5 py-1 text-xs transition-colors', o.value === value ? 'bg-ink/15 text-ink' : 'bg-card-2 text-ink-2 hover:text-ink')}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

export function Icon({ name, size = 16 }: { name: 'play' | 'pause' | 'step-back' | 'step-fwd' | 'skip-start' | 'skip-end' | 'target'; size?: number }) {
  const paths: Record<typeof name, ReactNode> = {
    play: <path d="M5 3.5v13l11-6.5z" fill="currentColor" />,
    pause: (
      <>
        <rect x="4" y="3.5" width="4" height="13" fill="currentColor" />
        <rect x="12" y="3.5" width="4" height="13" fill="currentColor" />
      </>
    ),
    'step-back': (
      <>
        <rect x="4" y="4" width="2.2" height="12" fill="currentColor" />
        <path d="M16 4v12L7.5 10z" fill="currentColor" />
      </>
    ),
    'step-fwd': (
      <>
        <rect x="13.8" y="4" width="2.2" height="12" fill="currentColor" />
        <path d="M4 4v12l8.5-6z" fill="currentColor" />
      </>
    ),
    'skip-start': (
      <>
        <rect x="3" y="4" width="2.2" height="12" fill="currentColor" />
        <path d="M10.5 4v12L5.5 10z" fill="currentColor" />
        <path d="M17 4v12l-5-6z" fill="currentColor" />
      </>
    ),
    'skip-end': (
      <>
        <rect x="14.8" y="4" width="2.2" height="12" fill="currentColor" />
        <path d="M9.5 4v12l5-6z" fill="currentColor" />
        <path d="M3 4v12l5-6z" fill="currentColor" />
      </>
    ),
    target: (
      <>
        <circle cx="10" cy="10" r="6" fill="none" stroke="currentColor" strokeWidth="1.6" />
        <circle cx="10" cy="10" r="1.6" fill="currentColor" />
        <path d="M10 1.5v3M10 15.5v3M1.5 10h3M15.5 10h3" stroke="currentColor" strokeWidth="1.6" />
      </>
    ),
  }
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" aria-hidden="true">
      {paths[name]}
    </svg>
  )
}

export function IconBtn({ name, onClick, title, disabled, big }: { name: Parameters<typeof Icon>[0]['name']; onClick: () => void; title: string; disabled?: boolean; big?: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      aria-label={title}
      disabled={disabled}
      className={cx(
        'inline-flex items-center justify-center rounded-md border border-line-2 bg-card-2 text-ink-2 transition-colors hover:border-ink-3 hover:text-ink disabled:cursor-not-allowed disabled:opacity-40',
        big ? 'h-9 w-11' : 'h-8 w-8',
      )}
    >
      <Icon name={name} size={big ? 20 : 16} />
    </button>
  )
}

export function Swatch({ color, kind = 'line' }: { color: string; kind?: 'line' | 'dot' | 'square' }) {
  if (kind === 'dot') return <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: color }} />
  if (kind === 'square') return <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: color }} />
  return <span className="inline-block h-0.5 w-4 rounded" style={{ background: color }} />
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="rounded-lg border border-dashed border-line-2 px-3 py-4 text-center text-xs text-ink-3">{children}</p>
}
