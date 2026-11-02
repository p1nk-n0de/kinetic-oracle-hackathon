import type {
  ApiCall,
  FetchedFile,
  LoadedPass,
  LoadedRun,
  LoadedTurn,
  Patch,
  PromptJson,
  RunIndex,
  RunManifest,
  SamRaw,
  SensoryContract,
  Tracks,
  TranscriptItem,
  TruthHidden,
  TruthRow,
  VerificationResult,
} from '../types'

/** Everything is static: `public/runs/<run_id>/...` relative to the page (works from any sub-path). */
export const RUNS_BASE = `${import.meta.env.BASE_URL}runs/`

export function runUrl(runId: string, rel: string): string {
  return `${RUNS_BASE}${encodeURIComponent(runId)}/${rel.split('/').map(encodeURIComponent).join('/')}`
}

export async function sha256Hex(buf: ArrayBuffer): Promise<string | null> {
  if (typeof crypto === 'undefined' || !crypto.subtle) return null
  try {
    const digest = await crypto.subtle.digest('SHA-256', buf)
    return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, '0')).join('')
  } catch {
    return null
  }
}

/** Bundle files that a published copy may carry in redacted form (docs/SANITIZATION.md); never a replay input. */
const SANITIZABLE = new Set(['mcp_calls.jsonl', 'prompt.json', 'transcript.json'])

interface LedgerEntry {
  recorded_sha256: string
  public_sha256: string
}

let ledgerP: Promise<Record<string, Record<string, LedgerEntry>>> | null = null

/** runs/SANITIZATION_LEDGER.json, per run: redacted file -> recorded (original) and published hash. */
function loadLedger(): Promise<Record<string, Record<string, LedgerEntry>>> {
  ledgerP ??= fetchBytes(`${RUNS_BASE}SANITIZATION_LEDGER.json`)
    .then((buf) => {
      if (!buf) return {}
      const runs = (JSON.parse(decode(buf)).runs ?? {}) as Record<string, { files?: Record<string, LedgerEntry> }>
      return Object.fromEntries(Object.entries(runs).map(([id, r]) => [id, r.files ?? {}]))
    })
    .catch(() => ({}))
  return ledgerP
}

async function fetchBytes(url: string): Promise<ArrayBuffer | null> {
  const res = await fetch(url, { cache: 'no-cache' })
  if (res.status === 404) return null
  if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`)
  return res.arrayBuffer()
}

function decode(buf: ArrayBuffer): string {
  return new TextDecoder('utf-8').decode(buf)
}

function parseJsonl<T>(text: string): T[] {
  const out: T[] = []
  for (const line of text.split('\n')) {
    const s = line.trim()
    if (!s) continue
    try {
      out.push(JSON.parse(s) as T)
    } catch {
      // a truncated last line (crash mid-write) is reported, not fatal
    }
  }
  return out
}

export async function loadIndex(): Promise<RunIndex> {
  const buf = await fetchBytes(`${RUNS_BASE}index.json`)
  if (!buf) throw new Error(`${RUNS_BASE}index.json not found — run \`python -m scripts.export_bundle_for_web\``)
  return JSON.parse(decode(buf)) as RunIndex
}

interface Loader {
  files: FetchedFile[]
  warnings: string[]
  manifest: RunManifest
  runId: string
  ledger: Record<string, LedgerEntry>
}

/** Fetch one bundle file, hash it, record the result; null when the file is absent. */
async function pull(L: Loader, rel: string): Promise<ArrayBuffer | null> {
  let buf: ArrayBuffer | null = null
  try {
    buf = await fetchBytes(runUrl(L.runId, rel))
  } catch (e) {
    L.warnings.push(`${rel}: ${(e as Error).message}`)
    return null
  }
  const expected = L.manifest.files[rel] ?? null
  if (buf === null) {
    L.files.push({ path: rel, bytes: 0, sha256: null, manifest_sha256: expected, match: null })
    return null
  }
  const sha = await sha256Hex(buf)
  const match = sha && expected ? sha === expected : null
  const e = L.ledger[rel]
  const sanitized = match === false && !!e && SANITIZABLE.has(rel.split('/').pop() ?? '') && e.recorded_sha256 === expected && e.public_sha256 === sha
  L.files.push({ path: rel, bytes: buf.byteLength, sha256: sha, manifest_sha256: expected, match, sanitized })
  return buf
}

async function pullJson<T>(L: Loader, rel: string): Promise<T | null> {
  const buf = await pull(L, rel)
  if (!buf) return null
  try {
    return JSON.parse(decode(buf)) as T
  } catch (e) {
    L.warnings.push(`${rel}: invalid JSON (${(e as Error).message})`)
    return null
  }
}

async function pullText(L: Loader, rel: string): Promise<string | null> {
  const buf = await pull(L, rel)
  return buf ? decode(buf) : null
}

const num = (v: unknown, fallback = 0): number => (typeof v === 'number' && Number.isFinite(v) ? v : fallback)

/**
 * Two truth formats exist in real bundles:
 *  - closed_loop: {note, project, rows:[{frame, game_tick, physics_frame, tick_offset,
 *                   player:{global_position:{x,y,z}, velocity:{x,y,z}}}]}
 *  - clip_evaluation: [{i, tick, state:{node_path, properties:{global_position, velocity}}, frame_meta:{...}}]
 */
export function normalizeTruth(raw: unknown): TruthHidden | null {
  if (raw == null) return null
  const rows: TruthRow[] = []
  const readVec = (v: unknown): { x: number; y: number; z: number } => {
    const o = (v ?? {}) as Record<string, unknown>
    return { x: num(o.x), y: num(o.y), z: num(o.z) }
  }
  if (Array.isArray(raw)) {
    raw.forEach((item, i) => {
      const it = (item ?? {}) as Record<string, unknown>
      const state = (it.state ?? {}) as Record<string, unknown>
      const props = (state.properties ?? {}) as Record<string, unknown>
      const p = readVec(props.global_position)
      const v = readVec(props.velocity)
      rows.push({ frame: num(it.i, i), tick: typeof it.tick === 'number' ? it.tick : null, ...p, vx: v.x, vy: v.y, vz: v.z })
    })
    return { note: 'Engine ground truth captured with the clip (evaluation only; never shown to any model).', format: 'clip_frames', rows }
  }
  const obj = raw as Record<string, unknown>
  if (Array.isArray(obj.rows)) {
    obj.rows.forEach((item, i) => {
      const it = (item ?? {}) as Record<string, unknown>
      const player = (it.player ?? {}) as Record<string, unknown>
      const p = readVec(player.global_position)
      const v = readVec(player.velocity)
      rows.push({ frame: num(it.frame, i), tick: typeof it.game_tick === 'number' ? it.game_tick : null, ...p, vx: v.x, vy: v.y, vz: v.z })
    })
    return { note: typeof obj.note === 'string' ? obj.note : '', format: 'closed_loop_rows', rows }
  }
  return { note: 'unrecognised truth format', format: 'unknown', rows }
}

export async function loadRun(runId: string): Promise<LoadedRun> {
  const manifestBuf = await fetchBytes(runUrl(runId, 'run_manifest.json'))
  if (!manifestBuf) throw new Error(`run_manifest.json not found for ${runId}`)
  const manifest = JSON.parse(decode(manifestBuf)) as RunManifest
  const L: Loader = { files: [], warnings: [], manifest, runId, ledger: (await loadLedger())[runId] ?? {} }
  L.files.push({ path: 'run_manifest.json', bytes: manifestBuf.byteLength, sha256: await sha256Hex(manifestBuf), manifest_sha256: null, match: null })

  const contractP = manifest.contract_path ? pullJson<SensoryContract>(L, manifest.contract_path) : Promise.resolve(null)
  const apiP = pullText(L, 'api_calls.jsonl')

  const passesP = Promise.all(
    manifest.passes.map(async (rec): Promise<LoadedPass> => {
      const samRoles = Object.entries(rec.sam ?? {})
      const [tracks, verification, truthRaw, ...sams] = await Promise.all([
        pullJson<Tracks>(L, rec.tracks_path),
        pullJson<VerificationResult>(L, rec.verification_path),
        rec.truth_hidden_path ? pullJson<unknown>(L, rec.truth_hidden_path) : Promise.resolve(null),
        ...samRoles.map(([, meta]) => pullJson<SamRaw>(L, meta.raw_path)),
      ])
      const sam: Record<string, SamRaw> = {}
      samRoles.forEach(([role], i) => {
        const s = sams[i]
        if (s) sam[role] = s
      })
      return {
        record: rec,
        tracks,
        verification,
        sam,
        truth: normalizeTruth(truthRaw),
        clipUrl: runUrl(runId, rec.clip_path),
        overlayUrl: rec.overlay_path ? runUrl(runId, rec.overlay_path) : null,
      }
    }),
  )

  const turnsP = Promise.all(
    manifest.repair_turns.map(async (rec): Promise<LoadedTurn> => {
      const dir = rec.prompt_path.split('/').slice(0, -1).join('/')
      const [prompt, transcript, patches, diff] = await Promise.all([
        pullJson<PromptJson>(L, rec.prompt_path),
        pullJson<TranscriptItem[]>(L, rec.transcript_path),
        pullJson<Patch[]>(L, `${dir}/patches.json`),
        rec.diff_path ? pullText(L, rec.diff_path) : Promise.resolve(null),
      ])
      return { record: rec, prompt, transcript: transcript ?? [], patches: patches ?? rec.patches ?? [], diff }
    }),
  )

  const [contract, apiText, passes, turns] = await Promise.all([contractP, apiP, passesP, turnsP])
  const apiCalls = apiText ? parseJsonl<ApiCall>(apiText) : []
  L.files.sort((a, b) => a.path.localeCompare(b.path))
  return { id: runId, baseUrl: runUrl(runId, ''), manifest, contract, apiCalls, passes, turns, fetched: L.files, warnings: L.warnings }
}

/** On demand: fetch and hash the media files (not loaded by default; the <video> element streams them). */
export async function hashMedia(run: LoadedRun): Promise<FetchedFile[]> {
  const rels: string[] = []
  for (const p of run.manifest.passes) {
    rels.push(p.clip_path)
    if (p.overlay_path) rels.push(p.overlay_path)
  }
  const out: FetchedFile[] = []
  for (const rel of rels) {
    const expected = run.manifest.files[rel] ?? null
    try {
      const buf = await fetchBytes(runUrl(run.id, rel))
      if (!buf) {
        out.push({ path: rel, bytes: 0, sha256: null, manifest_sha256: expected, match: null })
        continue
      }
      const sha = await sha256Hex(buf)
      out.push({ path: rel, bytes: buf.byteLength, sha256: sha, manifest_sha256: expected, match: sha && expected ? sha === expected : null })
    } catch {
      out.push({ path: rel, bytes: 0, sha256: null, manifest_sha256: expected, match: null })
    }
  }
  return out
}
