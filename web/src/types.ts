// Bundle schema as written by propriosam/artifacts.py (RunManifest / PassRecord / RepairTurnRecord),
// propriosam/sensory_contract.py (SensoryContract), propriosam/verifier.py (VerificationResult) and
// propriosam/vision_tracker.py (Track.to_json). Only the fields the dashboard reads are typed strictly.

export type VerificationStatus = 'PASS' | 'FAIL' | 'INCONCLUSIVE' | 'ERROR'

export interface RunIndexEntry {
  run_id: string
  kind: string
  status: string
  final_verdict: string | null
  verdict_basis?: string
  created_at: string
  finished_at?: string | null
  passes: number
  pass_statuses?: (string | null)[]
  pass_labels?: (string | null)[]
  repair_turns: number
  models?: Record<string, string>
  est_cost_usd?: number | null
  exported_files?: string[]
  exported_bytes?: number
}

export interface RunIndex {
  schema_version: string
  generated_at: string
  note?: string
  runs: RunIndexEntry[]
}

export interface SelectionCandidate {
  frames: number
  mean_area_px: number
  mean_confidence: number | null
}

export interface Selection {
  rule: string
  selected?: string | null
  candidates?: Record<string, SelectionCandidate>
}

export interface SamMeta {
  concept: string
  request_id: string
  response_id: string
  cached: boolean
  frames_processed: number
  raw_path: string
  object_id_selected: string | null
  selection: Selection
  frames_tracked: number
  coverage_total: number
}

export interface OpenLoop {
  tool?: string
  args?: Record<string, unknown>
  result?: unknown
  mcp_is_error?: boolean
  note?: string
}

export interface PassRecord {
  index: number
  label: string
  project_tree_sha256: string | null
  clip_path: string
  clip_sha256: string
  frames_dir: string
  frame_count: number
  capture: Record<string, unknown>
  open_loop: OpenLoop
  sam: Record<string, SamMeta>
  tracks_path: string
  verification_path: string
  verification_status: VerificationStatus
  t_fail: number | null
  max_residual: number | null
  overlay_path: string | null
  overlay_sha256: string | null
  overlay_info: Record<string, unknown>
  truth_hidden_path: string | null
}

export interface Patch {
  path: string
  find: string
  replace: string
  reason: string
  ts?: string
  turn_patch_index?: number
  diff?: string
}

export interface AntiCheat {
  prompt_sha256?: string
  banned_terms_found?: string[]
  banned_terms_checked?: number
  mentions_source_filenames?: boolean
}

export interface RepairTurnRecord {
  turn: number
  model: string
  escalated: boolean
  request_ids: string[]
  response_ids: string[]
  tool_calls: number
  tool_call_names: string[]
  patches: Patch[]
  prompt_path: string
  transcript_path: string
  diff_path: string | null
  diff_sha256: string | null
  outcome_text: string
  anti_cheat: AntiCheat
  est_cost_usd: number | null
}

export interface Baseline {
  path?: string
  tree_sha256?: string
  tree_sha256_after_run?: string
  unchanged?: boolean
  files?: number
}

export interface Workspace {
  name?: string
  path?: string
  staged_at?: string
  staged_tree_sha256?: string
  baseline_tree_sha256?: string
  baseline_match_at_stage?: boolean
  final_tree_sha256?: string
  modified_during_run?: boolean
  files?: number
}

export interface SpendByModel {
  calls: number
  cached: number
  est_cost_usd: number
}

export interface Spend {
  calls?: number
  est_cost_usd?: number
  by_model?: Record<string, SpendByModel>
}

export interface RunManifest {
  schema_version: string
  run_id: string
  kind: string
  created_at: string
  finished_at: string | null
  status: string
  final_verdict: string | null
  verdict_basis: string
  models: Record<string, string>
  baseline: Baseline
  workspace: Workspace
  contract_path: string | null
  contract_sha256: string | null
  rule_sha256: string | null
  passes: PassRecord[]
  repair_turns: RepairTurnRecord[]
  spend: Spend
  request_ids: string[]
  files: Record<string, string>
  anti_cheat: Record<string, unknown>
  environment: Record<string, unknown>
  notes: string[]
}

export interface CompiledBy {
  model?: string
  request_id?: string
  response_id?: string
  created_at?: string
  prompt_version?: string
  attempt?: number
  raw_output?: string
}

export interface SensoryContract {
  schema_version: string
  contract_id: string
  objective: string
  scene_brief: string
  concept_vocabulary: string[]
  statement: string
  mover_concept: string
  barrier_concept: string
  expected_pass_behaviour: string
  expected_fail_signature: string
  rule: {
    family: string
    mover_edge: string
    barrier_edge: string
    definition: string
    threshold_px: number
    persistence_frames: number
  }
  coverage: {
    critical_window: [number, number]
    min_window_coverage: number
    min_total_coverage: number
  }
  frame_count: number
  fps: number
  frame_size: [number, number]
  compiled_by: CompiledBy | null
  frozen_sha256: string | null
}

export interface TrackPoint {
  frame: number
  x1: number
  y1: number
  x2: number
  y2: number
  cx: number
  cy: number
  bottom: number
  confidence: number | null
  vx: number | null
  vy: number | null
  has_mask: boolean
}

export interface Track {
  concept: string
  object_id: string | null
  frame_count: number
  frame_size: [number, number]
  coverage_total: number
  selection: Selection
  points: TrackPoint[]
}

export interface Tracks {
  mover: Track
  barrier: Track
}

export interface Coverage {
  mover_total: number
  barrier_total: number
  both_total: number
  mover_window: number
  barrier_window: number
  both_window: number
  critical_window: [number, number]
  min_window_coverage: number
  min_total_coverage: number
}

export interface EvidenceSide {
  cx: number
  cy: number
  bottom: number
  vx: number | null
  vy: number | null
}

export interface EvidenceRow {
  frame: number
  E_px: number | null
  mover: EvidenceSide | null
  barrier: EvidenceSide | null
}

export interface VerificationResult {
  status: VerificationStatus
  contract_id: string
  contract_sha256: string | null
  rule_sha256: string
  frame_count: number
  residual: (number | null)[]
  mover_bottom: (number | null)[]
  barrier_bottom: (number | null)[]
  t_fail: number | null
  violation_run: number[] | null
  max_residual: number | null
  max_residual_frame: number | null
  margin_px: number | null
  coverage: Partial<Coverage>
  /** The approach gate: a PASS needs the mover to have come this close. Absent in older bundles. */
  approach?: {
    mover_body_px: number | null
    approach_body_heights: number
    required_max_E_px: number | null
    max_E_px: number | null
    exercised: boolean
  } | null
  evidence_rows: EvidenceRow[]
  reasons: string[]
}

export interface SamRaw {
  concept: string
  role: string
  model: string
  clip_sha256: string
  request_id: string
  response_id: string
  cached: boolean
  frames_processed: number
  metadata: Record<string, string>
  raw_text: string
}

export interface ToolSpec {
  type: string
  name: string
  description: string
  parameters: unknown
}

export interface PromptJson {
  turn: number
  model: string
  instructions: string
  user: string
  tools: ToolSpec[]
  prompt_sha256: string
  banned_terms_checked: string[]
  banned_terms_found: string[]
  mentions_source_filenames: boolean
}

export interface Usage {
  input_tokens?: number
  output_tokens?: number
  total_tokens?: number
  input_tokens_details?: { cached_tokens?: number }
  output_tokens_details?: { reasoning_tokens?: number }
  video_frames_processed?: number
}

export interface AssistantItem {
  type: 'assistant'
  text: string
  calls: { name: string; arguments: string }[]
  response_id?: string
  request_id?: string
  status?: string
  usage?: Usage
}

export interface ToolItem {
  type: 'tool'
  name: string
  arguments: unknown
  call_id: string
  output: unknown
}

export type TranscriptItem = AssistantItem | ToolItem

export interface ApiCall {
  ts: string
  purpose: string
  endpoint: string
  model: string | null
  request_id: string
  response_id?: string
  http: number
  latency_s: number
  est_cost_usd: number
  cumulative_est_cost_usd?: number
  cached: boolean
  bytes?: number
  response_status?: string
  usage?: Usage
}

/** Engine ground truth, normalised from either on-disk format (see lib/load.ts normalizeTruth). */
export interface TruthRow {
  frame: number
  tick: number | null
  x: number
  y: number
  z: number
  vx: number
  vy: number
  vz: number
}

export interface TruthHidden {
  note: string
  format: 'closed_loop_rows' | 'clip_frames' | 'unknown'
  rows: TruthRow[]
}

export interface FetchedFile {
  path: string
  bytes: number
  /** sha256 computed in the browser over the bytes that were fetched; null when WebCrypto is unavailable. */
  sha256: string | null
  manifest_sha256: string | null
  match: boolean | null
}

export interface LoadedPass {
  record: PassRecord
  tracks: Tracks | null
  verification: VerificationResult | null
  sam: Record<string, SamRaw>
  truth: TruthHidden | null
  clipUrl: string
  overlayUrl: string | null
}

export interface LoadedTurn {
  record: RepairTurnRecord
  prompt: PromptJson | null
  transcript: TranscriptItem[]
  patches: Patch[]
  diff: string | null
}

export interface LoadedRun {
  id: string
  baseUrl: string
  manifest: RunManifest
  contract: SensoryContract | null
  apiCalls: ApiCall[]
  passes: LoadedPass[]
  turns: LoadedTurn[]
  fetched: FetchedFile[]
  warnings: string[]
}
