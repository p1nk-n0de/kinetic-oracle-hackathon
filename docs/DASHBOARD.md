# Telemetry dashboard (`web/`) and offline replay (`scripts/replay_run.py`)

Both tools read **run bundles** (`runs/<run_id>/`, schema in `docs/RUN_BUNDLE_SPEC.md`) and nothing else. Neither
calls any model or any network service; the dashboard is a static site, the replay is a CLI. Every verdict either
tool shows is captioned the same way: *from the verifier over SAM 3.1 tracks; tool status and model text are never
consulted*.

## Run the dashboard

```bash
cd web
npm install          # or `npm ci` for the locked versions
npm run dev          # http://localhost:5173
npm run build        # type-checks (tsc -b) and writes web/dist/ — must finish with zero TypeScript errors
npm run preview      # serves web/dist/ on http://localhost:4173
```

Stack: React 19, TypeScript, Vite, Tailwind CSS 4 (dark theme only). Charts are plain SVG; no chart library.
`vite.config.ts` sets `base: './'`, so `web/dist/` can be served from any sub-path or opened through any static file
server. The app loads `runs/index.json` relative to the page, then one bundle at a time.

Keyboard: `space` play/pause · `←`/`→` step one frame (`shift` = 5) · `Home`/`End`.

## Export bundles for the dashboard

```bash
python -m scripts.export_bundle_for_web                       # every bundle under runs/  (stdlib only)
python -m scripts.export_bundle_for_web --run-dir runs/<id>   # one bundle (repeatable)
python -m scripts.export_bundle_for_web --clean               # also drop exported runs that no longer exist
```

This copies, per bundle, into `web/public/runs/<run_id>/`: `run_manifest.json`, `contract.json`, `api_calls.jsonl`,
`pass*/clip.mp4`, `pass*/overlay.mp4`, `pass*/tracks.json`, `pass*/verification.json`, `pass*/sam/*.json`,
`pass*/truth_hidden.json` (when present) and `repair_turn_*/{prompt.json,transcript.json,patches.json,diff.patch}`,
and rewrites `web/public/runs/index.json` (run id, kind, status, final_verdict, created_at, pass count, repair turns,
spend, exported file list). Raw `frames/`, the staged `workspace/` and `mcp_calls.jsonl` are not exported. The exported
copies are committed, so a fresh clone builds a working site with zero configuration. Re-run the export after a new
bundle lands in `runs/`, then commit `web/public/runs/`.

## What each panel shows

**Header.** Run picker (from `index.json`), kind, status, duration, pass/turn counts, estimated spend, and the final
verdict of the last pass with its caption. For `closed_loop` bundles the manifest's `final_verdict` is shown next to
it; for `clip_evaluation` bundles the manifest field is a per-label summary string, so the badge is the last pass.

**Split-screen player.** Left: pass 1 (`closed_loop`: "The agent that believed its tool: MCP said OK"); right: the last
pass ("After Muse repair via Godot MCP"). `clip_evaluation` bundles show pass 1 / pass 2 with their own labels. One
scrubber drives both videos; a seek sets `video.currentTime = (frame + 0.5) / fps` on each, playback runs the native
decoders with the second video re-synchronised to the first whenever it drifts more than ¾ of a frame. A canvas over
each video redraws, from `tracks.json`, the mover box (green), the barrier box (magenta), both **bottom edges** (the
quantity the contract measures), the centroids and an `E(t)` gauge between the two bottom edges. Toggle between
`overlay.mp4` (masks/boxes/HUD burned in by the pipeline) and `clip.mp4` (what SAM 3.1 received). Under each video: the
frame readout, `E(t)`, both bottom-edge values and the verifier state at that frame; then the **open-loop MCP result**
badge (what the agent's tool said) beside the **verifier verdict** badge. They are never merged.

**Residual E(t).** One line per pass (pass 1 orange, pass 2 blue, fixed order), `null` frames drawn as gaps, the
contract threshold (dashed), the crossing zone above it, the critical window (shaded), each pass's `t_fail` marker and
violation run, the labelled maximum of each series, and a cursor locked to the player. Hovering the chart scrubs the
player while paused; dragging scrubs while playing. Below the axis: per-pass **tracked strips** for mover and barrier
(the coverage picture frame by frame). Right: **coverage bars** per concept vs the gates (`min_total_coverage`,
`min_window_coverage`) and the verifier's reasons. A collapsible table lists `E`, mover bottom and barrier bottom for
every frame and pass.

**Sensory contract.** The frozen instance: falsifiable statement, objective, expected pass/fail behaviour, scene brief,
concept vocabulary, rule family and parameters (`threshold_px`, `persistence_frames`), coverage gates, clip geometry,
`frozen_sha256` compared with the manifest's `contract_sha256`, `rule_sha256` of the verifier source, and the compiler
record (model, request/response ids, raw structured output).

**Blind diagnosis.** Per repair turn: model, tool-call and patch counts, estimated cost, the **banned-term screen**
result (terms checked, terms found, whether source filenames were mentioned, prompt sha256 cross-checked against the
manifest), the **exact evidence prompt** Muse received (`prompt.json → user`), the system instructions and allowlisted
tool specs, the **tool-call transcript** as a timeline (each Muse response with request id and token usage, each tool
result expandable), the patches (`find → replace` with the model's stated reason), the unified diff, the model's
closing text labelled as model text, and the **outcome**: the verifier's verdict on the pass captured after the turn.

**Provenance.** Models used; every Meta request from `api_calls.jsonl` (purpose, model, request id, HTTP status,
latency, usage, estimated cost) with a check that the ids match `manifest.request_ids`; **bundle file hashes** from the
manifest with a status per entry — JSON files the page fetched are re-hashed in the browser with WebCrypto and marked
*verified* or *MISMATCH* (or *redacted copy* when `SANITIZATION_LEDGER.json` names both hashes, see
`docs/RUN_BUNDLE_SPEC.md`), media can be re-verified on demand, raw frames and the workspace are marked *not
distributed*; baseline/workspace tree hashes with the **baseline unchanged** and **copy matched baseline at stage**
flags; the spend meter by model; the environment record. At the bottom, clearly fenced: **Hidden ground truth
(evaluation only, never shown to any model)** — the engine's player `z` per frame from `truth_hidden.json` (both on-disk
formats are read), one line per pass, with the player-synchronised cursor.

## Offline replay (CLI)

```bash
.venv/bin/python -m scripts.replay_run --run-dir runs/<run_id>          # audit table, exit 0 only if everything matches
.venv/bin/python -m scripts.replay_run --run-dir runs/<run_id> --json   # machine-readable report
.venv/bin/pytest -m "not live" tests/unit                               # includes a replay of every committed bundle
```

The replay recomputes every bundle file hash (raw `frames/` and the gitignored `workspace/` tree are optional when
absent, never when changed), checks the contract is still frozen and matches the manifest, compares `rule_sha256()` of
the current verifier source with the bundle (a mismatch is a warning naming the edited functions; verdict equality is
still required), then re-parses the raw SAM 3.1 text of every pass, rebuilds the tracks, re-runs the frozen verifier and
asserts equality with the stored `tracks.json` and `verification.json` (status, `t_fail`, residual series, coverage,
violation run, max residual). It prints a turn-by-turn audit table and a verdict line labelled by its source.
