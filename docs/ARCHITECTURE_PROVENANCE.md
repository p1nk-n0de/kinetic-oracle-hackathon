# Architecture and provenance

## Architecture Provenance: Hackathon Work vs. Existing Infrastructure
Hackathon period: October 26 – November 4, 2026.
Pre-existing infrastructure: KINETIC-ORACLE uses an existing, independently developed Godot MCP server and associated test fixtures as its simulation and tool-execution environment. These predate the hackathon and are disclosed as supporting infrastructure. They are not claimed as new hackathon contributions.
New hackathon contributions: SAM 3.1 integration and temporal tracking; visual-state measurements and falsifiable sensory contracts; independent residual evaluation; Muse-powered diagnosis and bounded repair; closed-loop orchestration; reproducible run artifacts; interactive diagnostic interface; associated tests.

## What exactly is pre-existing
| Component | Where | Role in KINETIC-ORACLE |
|---|---|---|
| Godot MCP server (`godot-studio-mcp`, 22 tools) | `~/Projects/godot-studio` (separate repo, not included here) | Launches the game off-screen, delivers real input, steps physics ticks, captures real rendered frames, reads node/physics state. Used through the allowlisted bridge in `propriosam/mcp_adapter.py`. |
| Hurdle test scene + deliberately defective fixture | same repo (`example_game/proving_ground`, `tests/fixtures/pg_defect_hurdle`) | The system under test. Its tree hashes are recorded in every bundle and re-checked after each run. |
| Godot 4.6.2, ffmpeg, Python toolchain | this Mac | Runtime. |

Everything under `propriosam/`, `scenarios/`, `scripts/`, `tests/`, `web/` and `docs/` in this repository was written during the hackathon window, by Claude Code under the entrant's direction (see the git history, which starts 2026-10-30).

## Dataflow
```
User objective + scene brief ──Muse Spark (structured output)──▶ frozen SensoryContract (hashed)
                                                                        │
Godot MCP: stage fresh copy ─▶ walk forward (tool says OK) ─▶ 80 real frames ─▶ clip.mp4
                                                                        │
SAM 3.1 (/v1/files + /v1/responses, one concept per call, content-addressed cache) ─▶ tracks: 'capsule', 'yellow bar'
                                                                        │
verifier.py: E(t) = y_bottom(barrier) − y_bottom(mover); VIOLATION = E > thr for k consecutive tracked frames
   ─▶ PASS | FAIL (t_fail) | INCONCLUSIVE (coverage gate) | ERROR
                                                                        │ FAIL
Muse Spark (Responses API, native function tools) sees ONLY: objective, contract, tool's OK, measured rows,
   and 6 allowlisted tools (inspect_scene, inspect_physics, drive, list_source_files, read_source, patch_source)
   ─▶ patch on the working copy ─▶ relaunch ─▶ re-capture ─▶ SAM ─▶ verifier again (≤ 3 turns; Wonder after a failed Spark turn)
                                                                        │
runs/<run_id>/: manifest, contract, passes, repair turns, api_calls.jsonl (request ids), sha256 of every file
```

## Honesty rules enforced in code
- **Verdict source**: only `propriosam/verifier.py` sets PASS/FAIL/INCONCLUSIVE; `RunManifest.verdict_basis` states this; the orchestrator never reads tool status or model text to decide.
- **Frozen before measurement**: the contract is hashed when compiled (`frozen_sha256`), the rule source is hashed (`rule_sha256`), both are recorded per run; `check_frozen()` fails on tampering.
- **Coverage honesty**: missing tracks → INCONCLUSIVE, never PASS (`tests/unit/test_verifier.py`).
- **No vacuous pass**: a PASS needs the mover to have come within one body height of the barrier, otherwise the contract was not exercised → INCONCLUSIVE. Added after the hidden-truth audit caught a real run that passed only because its input was lost and the player never reached the hurdle; that run's SAM output is a regression fixture (`tests/fixtures/dropped_input_walk`).
- **Bounded repair**: at most 2 patches per turn and 3 turns, enforced in code (`MAX_PATCHES_PER_TURN`, `max_repair_turns`). A repair the verifier rejects is fed back as measured evidence; the model never declares success.
- **Actuation is re-asserted**: the capture re-sends the held input before every step, so a silently lost press cannot persist.
- **Hidden-truth audit**: after the runs, every verdict is compared with the engine's own record (`docs/EVALUATION_REPORT.md`). Evaluation only; nothing in the loop reads it.
- **Blind diagnosis**: every outgoing Muse prompt is screened against `BANNED_PROMPT_TERMS`, hashed, and stored in `repair_turn_N/prompt.json`; the turn-1 prompt names no source file; Muse's tool surface cannot read `*.md`, scenario files or any absolute path (`tests/integration/test_anti_cheat_e2e.py`).
- **Baseline integrity**: the original project's tree hash is recorded before and after every run; the staged copy must hash-match the baseline before pass 1.
- **No fabrication**: raw SAM wire text and every Meta request id are stored; `scripts/replay_run.py` recomputes every verdict offline from that text.
- **Hidden truth stays hidden**: `truth_hidden.json` (engine positions) is written for evaluation and never read by the verifier or sent to any model.
- **Model separation**: the development agent (Claude Code) wrote the software; every runtime contract compilation, segmentation, diagnosis and repair in a bundle was executed by Meta models through `https://api.meta.ai/v1`.

## Known limitations
See `docs/EVALUATION_REPORT.md` → Limitations.
