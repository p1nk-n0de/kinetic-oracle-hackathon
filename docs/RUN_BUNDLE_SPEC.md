# Run bundle specification (`runs/<run_id>/`)

A run bundle is the complete, offline-replayable record of one KINETIC-ORACLE execution. Pydantic models live in
`propriosam/artifacts.py` (`RunManifest`, `PassRecord`, `RepairTurnRecord`). All paths inside the manifest are
relative to the bundle directory. Example bundle: `runs/cliprun_20261030-121544_36e61f/` (kind `clip_evaluation`).

```
run_manifest.json        RunManifest (written last; `files` = sha256 of every other file in the bundle)
api_calls.jsonl          one line per Meta API call: purpose, endpoint, model, request_id, response_id, usage, est_cost_usd
mcp_calls.jsonl          one line per Godot MCP call (closed_loop runs only)
contract.json            frozen SensoryContract (frozen_sha256 covers everything except compiled_by)
passN/
  clip.mp4               80 frames, 960x540, 20 fps, H.264 faststart — what SAM 3.1 received
  frames/f_000.png …     raw frames (NOT in git; hashed in the manifest; absence is reported, not failed)
  sam/mover.json         {concept, role, request_id, response_id, cached, frames_processed, metadata, raw_text}
  sam/barrier.json       raw_text is SAM's exact wire output (one `<Nf>` line per frame)
  tracks.json            {mover: Track, barrier: Track} — per-frame box, centroid, bottom edge, vx, vy, selection rationale
  verification.json      VerificationResult: status, residual[80] (E(t) px or null), t_fail, violation_run, coverage, evidence_rows, reasons
  overlay.mp4            masks + boxes + centroids + HUD (frame, E(t), status) burned in
  open_loop.json         (inside PassRecord.open_loop) the MCP tool result the agent trusted
  truth_hidden.json      engine ground truth per frame — evaluation only, never shown to any model
repair_turn_N/
  prompt.json            exactly what Muse saw: instructions, user evidence, tool specs, prompt_sha256, banned-term screen
  transcript.json        ordered assistant texts / tool calls / tool outputs with request ids
  patches.json           [{path, find, replace, reason, diff}]
  diff.patch             unified diff of all patches in the turn
  tool_calls.json        adapter-side log of every allowlisted tool call
workspace/hurdle_scene/  staged Godot project (NOT in git; tree hash recorded at stage, after run)
```

## RunManifest fields a viewer needs
| field | meaning |
|---|---|
| `kind` | `closed_loop` (capture + repair) or `clip_evaluation` (pre-captured clips) |
| `status` | `COMPLETE` or `ERROR` (a partial bundle is still written) |
| `final_verdict` | last pass verification status: `PASS` / `FAIL` / `INCONCLUSIVE` / `ERROR` |
| `verdict_basis` | fixed sentence: verdict comes only from the verifier over SAM tracks under the frozen contract |
| `baseline.tree_sha256`, `baseline.tree_sha256_after_run`, `baseline.unchanged` | proof the original project was never mutated |
| `workspace.staged_tree_sha256 == baseline.tree_sha256` | proof the copy was fresh and unmodified before pass 1 |
| `contract_sha256`, `rule_sha256` | frozen contract instance; hash of the verifier's rule source |
| `passes[]` | `PassRecord`: clip sha, SAM request ids per role, verification status, `t_fail`, `max_residual`, overlay path |
| `repair_turns[]` | `RepairTurnRecord`: model, request ids, tool call names, patches, diff sha, outcome text, anti-cheat screen |
| `spend` | `{calls, est_cost_usd, by_model}` at Meta's published prices |
| `request_ids[]` | every Meta `x-request-id` seen in the run |
| `files` | sha256 of every bundle file (replay verifier recomputes and compares) |

## Residual semantics (frozen; `propriosam/verifier.py`)
`E(t) = y_bottom(barrier, t) − y_bottom(mover, t)` in source pixels, y downward. `null` where either concept is
untracked. VIOLATION when `E(t) > threshold_px` for `persistence_frames` consecutive tracked frames; `t_fail` is the
first frame of that run. FAIL ⇐ violation; INCONCLUSIVE ⇐ no violation but a coverage gate unmet; PASS otherwise.

## Offline replay (what `scripts/replay_run.py` must do, no API spend)
1. Load the manifest; recompute sha256 of every present file and compare with `files` (frames are optional).
2. For each pass: parse `sam/*.json` `raw_text` with `propriosam.vision_tracker.parse_sam_text`, rebuild tracks with
   `build_track`, run `propriosam.verifier.verify` under `contract.json`, and assert the result equals
   `verification.json` (status, t_fail, residual series).
3. Print a turn-by-turn table: pass → status/t_fail/max E/coverage; repair turn → model, tool calls, patches, anti-cheat screen.
4. Exit 0 only if every hash matches and every recomputed verdict matches.
