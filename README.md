# KINETIC-ORACLE (ProprioSAM)

**Closed-loop visual verification and bounded repair for tool-using agents, built on Meta Model API (SAM 3.1 + Muse Spark).**
Meta Global AI Developer Hackathon 2026 · Indie track · *Push the Frontier*.

Tool-using agents treat `{"status": "ok"}` as proof that the world changed the way they intended. It isn't. KINETIC-ORACLE
adds an independent *proprioception* layer: the action is rendered, **SAM 3.1** tracks the objects that matter, a **frozen
deterministic residual** decides PASS / FAIL / INCONCLUSIVE from numbers alone, and when it fails, **Muse Spark** diagnoses
the cause blind — from the measured evidence and a handful of inspection tools — patches the scene through the same tool
interface, and the whole measurement runs again. The model never gets to declare success.

## The demonstration: "The agent that believed its tool"
A Godot game action — *walk forward; the low hurdle must stop you* — is issued through a Godot MCP server. The tool returns
OK. The rendered clip shows the player walking straight through the hurdle. KINETIC-ORACLE catches it at frame 60 of 80,
hands Muse Spark the numbers, Muse finds the collision-layer mismatch with its own tool calls and patches one line, and the
re-captured clip passes under the identical contract.

| | Pass 1 (open loop) | Pass 2 (after Muse repair) |
|---|---|---|
| MCP tool said | OK | OK |
| SAM 3.1 + frozen residual | **FAIL** at frame 60, max E = +235 px | **PASS**, max E = −13 px |
| Reference bundle | `runs/run_20261030-122149_3091ef/` (15 Meta request ids, $0.124, baseline hash unchanged) | |

Full numbers, repeat trials, the true-negative scene, perturbations and the ablation against open-loop trust and a
static-screenshot VLM check: `docs/EVALUATION_REPORT.md`.

## Run it
```bash
# one-time
python3.12 -m venv .venv && .venv/bin/pip install -e '.[dev]'
export MODEL_API_KEY=...            # Meta Model API key; read from the environment only
# live closed loop on a fresh copy of the defective scene (needs the local Godot MCP server; ~2 min, ≈$0.15)
.venv/bin/python -m scripts.run_hurdle_loop
# offline replay of any bundle: recomputes every verdict from the stored SAM wire text, checks every hash, $0
.venv/bin/python -m scripts.replay_run --run-dir runs/run_20261030-122149_3091ef
# tests (unit + anti-cheat audit of the latest closed-loop bundle)
.venv/bin/pytest -q
# evaluation report and ablation baselines; demo proof clip; dashboard
.venv/bin/python -m scripts.run_evaluation
.venv/bin/python -m scripts.build_demo_video
cd web && npm install && npm run dev
```

## How it works
`docs/ARCHITECTURE_PROVENANCE.md` has the dataflow and the honesty rules enforced in code; `docs/RUN_BUNDLE_SPEC.md`
documents the offline-replayable bundle; `docs/ENVIRONMENT_AUDIT.md` and `docs/BUILD_STATE.md` record how it was built.

- `propriosam/meta_client.py` — Meta Model API client (bearer auth from env, request-id + usage log, spend cap, SAM cache)
- `propriosam/vision_tracker.py` — SAM 3.1 wire parser, tracks, coverage, mask decoding (Meta's `meta-sam-parser`), overlays
- `propriosam/sensory_contract.py` — Muse-compiled, frozen, falsifiable contract (structured output)
- `propriosam/verifier.py` — the frozen residual rule; the only place a verdict is made
- `propriosam/mcp_adapter.py` — fresh working copy + hash check; tick-locked capture; Muse's allowlisted tool surface
- `propriosam/diagnosis.py` — anti-cheat-screened evidence → Muse tool loop (Responses API, native function tools)
- `propriosam/repair_orchestrator.py` — the state machine; `propriosam/artifacts.py` — immutable bundles

## Architecture Provenance: Hackathon Work vs. Existing Infrastructure
Hackathon period: October 26 – November 4, 2026.
Pre-existing infrastructure: KINETIC-ORACLE uses an existing, independently developed Godot MCP server and associated test fixtures as its simulation and tool-execution environment. These predate the hackathon and are disclosed as supporting infrastructure. They are not claimed as new hackathon contributions.
New hackathon contributions: SAM 3.1 integration and temporal tracking; visual-state measurements and falsifiable sensory contracts; independent residual evaluation; Muse-powered diagnosis and bounded repair; closed-loop orchestration; reproducible run artifacts; interactive diagnostic interface; associated tests.

## Honesty notes
Every verdict in this repository comes from `verifier.py` over SAM 3.1 tracks under a contract frozen before measurement.
Tool statuses and model text are recorded but never consulted. Hidden engine ground truth is stored for evaluation only
and never shown to any model. Numbers that could not be verified are labelled as such. Limitations are listed in the
evaluation report.
