# BUILD STATE — KINETIC-ORACLE (ProprioSAM)

Deadline: Wed 4 Nov 2026 21:00 ET = **Thu 5 Nov 02:00 UTC**. Budget cap for the build: $40 Meta API. Spent so far: about $4.20
(final evidence set $3.05, evaluation $0.25, superseded runs and probes about $0.90).

## Gate status
| Gate | Status | Evidence |
|---|---|---|
| Phase 0 audit | **DONE** | `docs/ENVIRONMENT_AUDIT.md` |
| P0 closed loop | **DONE** | 21 real bundles in `runs/`. Hero run `run_20261030-140019_79d646`: FAIL@60 → Spark's patch → FAIL@60 (repair rejected) → Wonder's patch → PASS |
| P1 CLI, tests, dashboard | **DONE** | `scripts/replay_run.py`, `tests/` (unit + anti-cheat e2e), `web/` (built by a cloud session on a separate branch, reviewed and merged here) |
| P2 evaluation, docs, demo clip | **DONE** | `docs/EVALUATION_REPORT.md`, `runs/evaluation_summary.json`, `docs/ARCHITECTURE_PROVENANCE.md`, `runs/kinetic_oracle_demo_proof.mp4`, `docs/DEMO_SCRIPT.md` |

## What the evidence shows
- Defective scene: 3/3 FAIL at frame 60, repaired on turn 1, PASS. Variants: a different wrong layer, a different root cause, two faults, three faults, the robot build with the fault.
- Known-good twin and the real robot build: PASS with no repair attempted. Robot build under a contract whose concept is not in the scene: INCONCLUSIVE, no repair.
- Three-fault scene at one patch per turn, 10 trials: 8 solved in one turn; 1 repair rejected by the verifier and recovered by Wonder; 1 repair broke the game and the verifier refused to pass it.
- Hidden-truth audit over 40 passes: 39 match the engine, 1 abstained, 0 wrong.

## Findings that changed the system (keep these in the demo story)
1. **Vacuous pass.** A run passed because the held input was silently lost at frame 38 and the robot never reached the hurdle. Caught by the hidden-truth audit. Fix: approach gate in the verifier, input re-asserted every step, real regression fixture `tests/fixtures/dropped_input_walk`.
2. **Broken repair.** Spark called `remove_collision_exception_from`, which does not exist. The game froze at spawn while every tool said OK and the model said the contract held. Verifier: INCONCLUSIVE. Fix: INCONCLUSIVE after a repair continues the bounded loop, and Muse gained a runtime-errors tool.
3. **Hashing bug.** `sorted(os.walk())` defeated directory pruning. Found by the cloud session's review of `artifacts.py`.

## Locked decisions (do not re-derive)
1. Runtime models: `muse-spark-1.3` Standard via `POST /v1/responses` with native function tools, replaying prior output items + `function_call_output`. `muse-wonder-1.0` from turn 2. SAM via `/v1/files` + `/v1/responses`, non-streaming, one concept per call, cached by `(clip_sha256, prompt, model)`.
2. `max_output_tokens ≥ 1500` on every Muse call (reasoning tokens count against it). Contract compile uses strict structured output.
3. Working copy: `runs/<run_id>/workspace/hurdle_scene/`, tree hash must equal the baseline before pass 1. The Godot MCP server runs with `GODOT_STUDIO_EXTRA_ROOT=<runs dir>`. Never launch a baseline in place.
4. Muse's tools: `inspect_scene`, `inspect_physics`, `get_runtime_errors`, `drive`, `list_source_files`, `read_source`, `patch_source`. Only `scripts/`, `scenes/`, `project.godot` are readable. At most 2 patches per turn (run parameter) and 3 turns.
5. Frozen residual: `E(t) = y_bottom(barrier) − y_bottom(mover)`; VIOLATION when `E(t) > threshold_px` for `persistence_frames` consecutive tracked frames. PASS also needs coverage gates and the approach gate. The rule family is library code; Muse compiles the contract instance.
6. Capture: tick-locked, 80 frames, every 3 ticks, 960×540, 20 fps, faststart, input re-asserted each step, hidden truth saved for evaluation only, 30 s timeout, session always stopped.
7. Claude Code is the development harness only; the product never calls Anthropic.

## Open items for the entrant
- Confirm the new-work rule in the participant guide (behind the Cerebral Valley login). The provenance disclosure is written on the assumption that disclosed existing tools are acceptable.
- Before making the repo public, clean the history: see the handoff report.
- Record the 3-minute video from `docs/DEMO_SCRIPT.md`, and submit on the Cerebral Valley platform.
