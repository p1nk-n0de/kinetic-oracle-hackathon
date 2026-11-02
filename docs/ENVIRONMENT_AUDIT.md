# ENVIRONMENT AUDIT — Phase 0 (2026-10-30)

Machine: Apple M4 Pro, 24 GB, macOS (Darwin 27). All paths verified on disk today.

In this public copy the private studio's names are generic substitutes (`godot-studio`, `godot-studio-mcp`, `godot_studio`,
`GODOT_STUDIO_EXTRA_ROOT`; see `docs/SANITIZATION.md`). Point the code at a real copy with the `KO_*` variables in
`propriosam/local_config.py`, set in the untracked `scripts/env.local.sh`.

## 1. Existing infrastructure recovered (pre-dates the hackathon — disclosed, not claimed)

| Item | Location | Notes |
|---|---|---|
| Godot MCP server | `<godot-studio>` = `~/Projects/godot-studio` (separate repository, external volume must be mounted) | 22 tools, MCP protocol 2025-06-18, starts in 0.3 s. Launch: `uv run --directory ~/Projects/godot-studio godot-studio-mcp` |
| Allowed project roots | `configs/studio.toml` `[roots]` + env **`GODOT_STUDIO_EXTRA_ROOT`** (one extra root, `src/godot_studio/config.py:62`) | Set `GODOT_STUDIO_EXTRA_ROOT=~/Projects/kinetic-oracle/runs` on the spawned server so `runs/<run_id>/workspace/` is launchable |
| Godot binary | `/Applications/Godot.app/Contents/MacOS/Godot` 4.6.2.stable | Screenshots need a windowed process: launch with `offscreen=true` (window off-desktop), never headless |
| Defective fixture | `tests/fixtures/pg_defect_hurdle/` (45 files) | Hurdle declared on collision layer 2 in `scripts/arena_layout.gd:22`; player mask 1 → walks through |
| Real game build | `example_game/proving_ground/` (69 files) | A later build: the player is a robot model, not a capsule; hurdle on the default layer. Protected root (never write) |
| Today's repaired copy | `artifacts/working_copies/pg_defect_hurdle-repair-20261030-112402/` | Muse's own fix (removed `"layer": 2`) — used for the SAM evidence clip |
| Scenarios | `example_game/proving_ground/scenarios/{hurdle_blocks_walking,jump_clears_hurdle,reach_corridor}.yaml` | Reproduction recipe: settle 40 ticks, hold `move_left` 25, hold `move_forward` 240; fail = `Player.position[2] <= -11.7` |

Key MCP tools for the loop: `godot_launch_session(project, offscreen, label)`, `godot_time_control(session_id, action=pause|resume|step_ticks, ticks)`, `godot_send_input(session_id, action, mode=press|release|hold|tap, ticks, wait, observe)`, `godot_run_input_sequence(session_id, steps)`, `godot_capture_frame(session_id, label, max_width, return_image=False)` → `{path, game_tick, physics_frame, width, height}`, `godot_inspect_runtime(session_id, node_path, properties)`, `godot_inspect_physics(session_id, node_path, rays, overlaps)` → layer/mask/shapes/collisions, `godot_stop_session(session_id)`. Python client pattern: `scripts/mcp_client.py` in the studio (`mcp.client.stdio`).

### Anti-cheat leak audit of the fixture
Files that reveal the bug (must be invisible to Muse): `DEFECT_FIXTURE.md`, `scenarios/hurdle_blocks_walking.yaml` (description names the layer), `README.md` (scenario docs). `scripts/arena_layout.gd` only documents the normal convention ("solid → layer 1 (world)") and lists the Hurdle with `"layer": 2` — ordinary source, fair to read. Tool surface for Muse therefore exposes **only** `scripts/*.gd`, `scenes/*.tscn`, `project.godot`, plus live runtime/physics inspection. Working-copy paths given to Muse are relative; the absolute path must not contain "defect".

## 2. Prior proven evidence (pre-build tests, 2026-10-30; raw logs archived outside the repo, superseded by the final bundles in `runs/`)

**Muse Spark 3/3 repair (via Claude Code on Meta's Messages adapter).** Each run: `run_scenario` → launch → `inspect_runtime` / `inspect_physics` / read scripts → `apply_repair_copy` → `retest_repair`; verdict read from the retest JSON (fixed=true, regressions pass, baseline unchanged). 11–14 turns, 49–61 s, $0.14–0.19 each. Muse's patch: delete `, "layer": 2` from the Hurdle entry.
*Correction to the directive's wording:* the "inline-tools fallback" is **native tool calling with the full tool array sent inline** (what `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1` does, instead of deferred `tool_reference` loading). It is not a prompt-and-parse-JSON scheme. Direct API tool calling (below) is the same mechanism.

**SAM 3.1 discrimination.** Two clips (80 frames, 960×540, H.264, 20 fps, faststart) with per-frame ground truth (hidden, never shown to Muse).
- Capture recipe (tick-locked): pause → step 40 → press `move_left` → step 25 → release → press `move_forward` → 80 × (step 3 ticks, inspect Player, capture frame). Frame i ↔ tick 3·(i+1) after the walk starts.
- Frozen rule: `E(t) = bar.y2 − capsule.y2` (screen px, both bottom edges); VIOLATION = `E(t) > 0` for ≥ 3 consecutive frames; `t_fail` = first frame of that run.
- Results: defect → VIOLATION @ 59 (truth: z < −11.8 at frame 60, z < −12.0 at 61); repaired → no violation, max E = −13 px (margin 13–17 px after the stop). Identical across repeat calls.
- Coverage: text "capsule" 66/80 (frames 14–79) and 69/80; "yellow bar" 80/80 (two ids: id 0 = hurdle, id 1 = far pressure plate — choose by confidence/area); box prompt 77/80 (missing 0–2). Prompts that returned nothing: "robot", "blue capsule", "game character".

## 3. Meta Model API — verified wire facts (today, with the real key)

- Auth: `Authorization: Bearer $MODEL_API_KEY`; `/v1/models` lists `muse-wonder-1.0, muse-spark-1.3(-contributor), sam-3.1, muse-image-1.0, …`. Request ids: response `id` (`resp_…`) **and** header `x-request-id`. Rate headers `x-ratelimit-*`.
- **Responses API function calling works** (`tools:[{type:"function",name,description,parameters}]`, `tool_choice:"auto"`, `instructions`, `reasoning:{effort:"low"}`). Output items: `reasoning`, `message`, `function_call{call_id,name,arguments}`. Multi-turn by replaying all prior output items (including `reasoning`) + `{type:"function_call_output", call_id, output}` → HTTP 200.
- **Structured output works**: `text:{format:{type:"json_schema",name,schema,strict:true}}` → `output_text` holds the JSON. **Reasoning tokens count against `max_output_tokens`** (722 reasoning tokens for a trivial fill): use ≥ 1500, or the message comes back empty with `status: completed`.
- **Image input works**: `{type:"input_image", image_url:"data:image/png;base64,…"}` (needed for the static-screenshot VLM baseline).
- **SAM 3.1**: `POST /v1/files` multipart `purpose=user_data` → `id`; `POST /v1/responses {model:"sam-3.1", input:[{type:"message",role:"user",content:[{type:"input_text",text:"capsule"},{type:"input_video",file_id}]}], stream:false, metadata:{include_confidence:"true", mask_encoding:"one_bit"}}`. Output: one line per frame `<Nf>id<|box;x1..y2;w;h;c|><|mask;x=0;y=0;c=..;data=H,W,!<base85>|>,…` inside `output_text`; `usage.video_frames_processed`. One concept per request; box prompt syntax `<40f>1<|box;x1=;y1=;x2=;y2=;w=960;h=540|>`. 3–10 s per 80-frame clip; $0.20 / 1000 frames (50-frame minimum).
- Official parser installed: `meta-sam-parser 0.1.0` → `parse_responses_stream(async_events, video_segmentation_format())`, `SegmentationMask(encoding, payload, width, height)`, `decode_mask_to_raster(mask) -> bytes (H*W)`, `decode_mask_to_rle`. It consumes streaming events; for stored non-streaming text our regex parser covers boxes and the mask codec covers rasters.
- Messages adapter (Claude Code route) accepts `context_management`/`tool_reference` without 400s; Claude Code as a *dev/test* harness only — the product loop calls `/v1/responses` directly.

## 4. Toolchain

`uv 0.9.27`, project venv `.venv` (Python 3.12: mcp, pydantic, pillow, numpy, pytest, pyyaml, meta-sam-parser), `node v26.0.0`, `npm 11.12.1`, `ffmpeg` (Homebrew; **no `drawtext` filter** on this build — burn captions with PIL, composite with ffmpeg), Godot 4.6.2.

Credentials: `MODEL_API_KEY` is **not** exported in the shell. Key file: `~/.config/meta/model_api_key` (mode 600). Run everything as `MODEL_API_KEY="$(cat ~/.config/meta/model_api_key)" .venv/bin/python -m …` (or `source scripts/env.sh`). Code reads `os.environ` only. Spend today before the build: ≈ $1.10 (Muse tests + SAM) + ≈ $0.02 probes.

## 5. Baseline hashes (tree SHA-256, `.godot/` excluded; `scripts/hash_baselines.py`)

<!-- hashes appended by the commit step -->
defect_fixture: tree_sha256=5df008eb17045d95aed148ff8c5ff579be158a3bbf88e8fde9cec0a1e7d0e88d files=45
known_good_scene: tree_sha256=fc1c6174e310b3f7988fcd4d19096d64c3c5cbc8b1bf662b79e1b1cd03c2e29e files=69
arena_layout.gd sha256=c876e4d9afe20da28046f1ea0baf951e78684734cba9fdba3ce015ab34e03694
