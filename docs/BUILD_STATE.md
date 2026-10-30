# BUILD STATE — KINETIC-ORACLE (ProprioSAM)

Deadline: Wed 4 Nov 2026 21:00 ET = **Thu 5 Nov 02:00 UTC**. Budget cap for the build: $40 Meta API.

## Gate status
| Gate | Status | Evidence |
|---|---|---|
| Phase 0 audit | **DONE 2026-10-30** | `docs/ENVIRONMENT_AUDIT.md`, `docs/prior_evidence/2026-10-30/` |
| P0 closed loop | not started | — |
| P1 CLI + tests + dashboard | not started | — |
| P2 evaluation + docs + demo video | not started | — |

## Decisions locked in Phase 0 (do not re-derive)
1. **Runtime models**: `muse-spark-1.3` Standard via `POST /v1/responses` with native function tools (replay prior output items + `function_call_output`). `muse-wonder-1.0` only as escalation after a failed repair turn. SAM via `/v1/files` + `/v1/responses` (`sam-3.1`), non-streaming, one concept per call, cached by `(clip_sha256, prompt, model)`.
2. **`max_output_tokens ≥ 1500`** on every Muse call (reasoning tokens count). Contract compile uses structured output (`text.format` json_schema strict).
3. **Working copy**: `shutil.copytree` of the fixture → `runs/<run_id>/workspace/hurdle_scene/` (neutral name), tree-hash must equal the baseline before Pass 1. Spawn the Godot MCP server with `GODOT_STUDIO_EXTRA_ROOT=<abs path of runs/>` so that path is launchable. Patches applied by our adapter (find/replace + unified diff in `repair_trace.jsonl`); `.godot/` excluded from hashes.
4. **Muse tool surface (allowlist)**: `inspect_scene(node_path?)`, `inspect_physics(node_path)`, `drive(steps)` (real inputs, returns Player watch digest), `list_source_files()`, `read_source(rel_path)`, `patch_source(rel_path, find, replace, reason)`. Only `scripts/*.gd`, `scenes/*.tscn`, `project.godot` are listable/readable. Never expose `*.md`, `scenarios/`, `oracle.yaml`, absolute paths, truth.json, or the verifier's hidden data. One offscreen session per diagnosis turn, stopped in `finally`.
5. **Frozen residual** (verifier library, declared before any clip is scored): `E(t) = y2(barrier) − y2(mover)`; VIOLATION when `E(t) > threshold_px` for `persistence_frames` consecutive tracked frames; coverage gates → `INCONCLUSIVE` (never PASS) when mover or barrier coverage in the critical window `[45,70]` < 0.9 or overall < 0.6. Muse compiles the contract instance (mover="capsule", barrier="yellow bar", thresholds, window, falsifiable statement) from the objective + camera description; the geometry code never changes per run. Barrier track = highest-confidence/largest id (the far pressure plate also matches "yellow bar").
6. **Capture** = the proven tick-locked recipe (80 frames, every 3 ticks, 960×540, 20 fps MP4 faststart) with hidden `truth.json` saved for evaluation only. Hard 30 s timeout on the capture phase; session always stopped.
7. **Open-loop lie** = the `drive`/walk step's MCP result (`ok`) recorded in the manifest next to the Pass 1 FAIL.
8. Claude Code is a dev harness only; the product never calls Anthropic. Anti-cheat banned strings in outgoing Muse prompts: `defect`, `defective`, `pg_defect`, `DEFECT_FIXTURE`, `collision_layer`, `collision_mask`, `layer 2`, `"layer": 2`, `arena_layout`, `hurdle_blocks_walking`, `truth.json`, any absolute fixture path, any diff.

## Next actions (P0, in order)
1. `propriosam/meta_client.py` — bearer client (urllib), request-id + usage logging to `runs/<id>/api_calls.jsonl`, spend meter with $40 abort, SAM upload/track with SHA-256 cache, Muse `respond()` with tool loop helper, structured-output helper, image helper.
2. `propriosam/vision_tracker.py` — parse SAM lines (regex) → per-frame boxes/centroids/velocities, mask raster via `meta_sam_parser.decode_mask_to_raster`, coverage metrics, overlay MP4 writer (PIL + ffmpeg).
3. `propriosam/sensory_contract.py` + `verifier.py` — Pydantic contract, frozen rule, `VerificationResult{status, residual[], t_fail, coverage, evidence}`.
4. `propriosam/mcp_adapter.py` — MCP stdio client to the Godot server, working-copy staging + hash check, capture recipe, allowlisted tools, patch/diff.
5. `propriosam/diagnosis.py` + `repair_orchestrator.py` + `artifacts.py` — evidence formatter (anti-cheat filter), Muse tool loop (max 3 repair turns, Wonder escalation), manifest writer.
6. `scripts/run_hurdle_loop.py` → real run → `runs/<run_id>/run_manifest.json`; then update this file.

## Spend log
- 2026-10-30 pre-build tests + probes: ≈ $1.12 (not counted against the $40 build cap).
