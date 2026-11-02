# KINETIC-ORACLE (ProprioSAM)

**Closed-loop visual verification and bounded repair for tool-using agents, built on Meta Model API (SAM 3.1, Muse Spark, Muse Wonder).**
Meta Global AI Developer Hackathon 2026 · Indie track · *Push the Frontier*.

Tool-using agents treat `{"status": "ok"}` as proof that the world changed the way they intended. It isn't. KINETIC-ORACLE
adds an independent *proprioception* layer. The action is rendered, **SAM 3.1** tracks the objects that matter, and a **frozen
deterministic residual** decides PASS, FAIL or INCONCLUSIVE from numbers alone. When it fails, **Muse** diagnoses the cause
blind, from the measurements and a handful of inspection tools, and patches the scene. Then everything is measured again.
The model never gets to declare success.

## What was built during the hackathon
The hackathon ran 26 Oct – 4 Nov 2026. The system, its tests and all 21 runs were written and run on **30 Oct 2026**: the
development history runs from 12:03 to 14:15 UTC that day, and all 21 runs carry that date in their ids and manifests. Later
commits add no runs and do not touch the verifier, the tracker, the contract compiler or the repair loop's logic: release
preparation (30 Oct), this provenance section (2 Nov), the sanitisation of this public copy (2 Nov, `docs/SANITIZATION.md`) and the
licence files (2 Nov).
The demo video was rendered from these run bundles on 2 Nov 2026.

| Component | Status | Evidence |
|---|---|---|
| SAM 3.1 integration and per-frame tracking (`propriosam/meta_client.py`, `propriosam/vision_tracker.py`) | **Built during the hackathon** | git history, 30 Oct |
| Muse Spark contract compiler: objective to frozen, hashed contract (`propriosam/sensory_contract.py`) | **Built during the hackathon** | git history, 30 Oct |
| Residual verifier with coverage and approach gates (`propriosam/verifier.py`) | **Built during the hackathon** | git history, 30 Oct |
| Muse Spark → Muse Wonder blind diagnosis and bounded repair loop (`propriosam/diagnosis.py`, `propriosam/repair_orchestrator.py`) | **Built during the hackathon** | git history, 30 Oct |
| Godot adapter: working-copy staging, tick-locked capture, Muse's 7-tool allowlist (`propriosam/mcp_adapter.py`) | **Built during the hackathon**. It drives the pre-existing server below. | git history, 30 Oct |
| 21 closed-loop runs, evaluation, hidden-truth audit (`runs/`, `docs/EVALUATION_REPORT.md`) | **Run during the hackathon** | run ids and manifests, 30 Oct |
| Offline replay verifier, 306 tests, telemetry dashboard (`scripts/replay_run.py`, `tests/`, `web/`) | **Built during the hackathon** | git history, 30 Oct |
| Demo video | **Made during the hackathon** | rendered 2 Nov from the run bundles |
| Public-copy sanitisation: configurable studio location, redaction ledger and its checks, 27 tests (`propriosam/local_config.py`, `scripts/build_sanitization_ledger.py`, `tests/unit/test_sanitization.py`) | **Made during the hackathon**, after the runs | git history, 2 Nov |
| The Godot test game (Proving Ground, with its deliberate-defect fixture) | **Pre-existing**: the system under test | separate private repository, committed 23 Oct 2026, unchanged since the event began |
| The Godot MCP server that launches, drives and captures the game | **Pre-existing**: test infrastructure | same repository, committed 23 Oct 2026, unchanged since the event began |

Also not new work: the Godot 4.6.2 engine, Meta's `meta-sam-parser`, and the open-source libraries listed in `pyproject.toml` and
`web/package.json`. The run bundles contain excerpts of the pre-existing game's source, which Muse read through its tools, and
footage of the game. Both are evidence of the checks, not part of the entry. The software was written with Claude Code; every
model call at runtime is a Meta model.

## The demonstration: "The agent that believed its tool"
A Godot action, *walk forward; the low hurdle must stop you*, goes through a Godot MCP server. The tool returns OK. The
rendered clip shows the player walking straight through the hurdle.

From the real run `runs/run_20261030-140019_79d646/`:

| Pass | What happened | Verifier (SAM 3.1 + frozen residual) |
|---|---|---|
| 1 | The MCP tool said OK | **FAIL** at frame 60, max E = +235 px |
| 2 | Muse Spark patched the scene and said *"solid 0.55m hurdle now blocks CharacterBody so E(t) stays ≤5px"* | **FAIL** at frame 60, max E = +236 px. The repair is rejected on the numbers. |
| 3 | The loop escalated to Muse Wonder, which found the remaining fault | **PASS**, max E = −13 px, full tracking coverage in the critical window |

28 Meta request ids, about $0.41, baseline hash unchanged, replayable offline with zero API calls.

## What the evaluation found
21 real closed-loop runs, 40 measured passes. Full tables, sampling and limitations are in `docs/EVALUATION_REPORT.md`.

- **Defective scene, 3 trials:** FAIL at frame 60, repaired, PASS, every time. Also repaired: a different wrong layer, a different root cause, two faults, three faults, and the fault on the real robot build.
- **No false alarms:** the known-good scene and the real robot build passed with no repair attempted.
- **Hidden-truth audit:** 39 verdicts match the engine's own record, 1 abstained, 0 wrong. No model and no part of the loop ever sees that record.

The two best results are failures it caught:

- **A repair that broke the game.** With one patch available, Muse called a method that does not exist. The game froze at spawn. The patch tool said OK, the input tool said OK, and Muse said the contract held. A plain "did it cross the hurdle?" check would have passed, because the player never moved. The verifier refused.
- **Our own harness.** In one run the held input was silently lost and the robot stopped 4 m short of the hurdle, and our verifier passed it: "it did not cross" was true only because it never got there. The hidden-truth audit caught that. A PASS must now prove the action happened, and that run's real SAM output is a regression test.

## Run it
```bash
# one-time
python3.12 -m venv .venv && .venv/bin/pip install -e '.[dev]'
export MODEL_API_KEY=...            # Meta Model API key; read from the environment only

# offline, free, no Godot: recompute every verdict from the stored SAM wire text and check every hash
.venv/bin/python -m scripts.replay_run --run-dir runs/run_20261030-140019_79d646

# tests: unit, replay, and the anti-cheat audit of every bundle
.venv/bin/pytest -q

# dashboard over the exported bundles
cd web && npm install && npm run dev

# live closed loop on a fresh copy of the defective scene (needs the Godot MCP server below; about 2 minutes, about $0.15)
.venv/bin/python -m scripts.run_hurdle_loop

# regenerate the evaluation report and the proof clip
.venv/bin/python -m scripts.run_evaluation --reference run_20261030-140019_79d646
.venv/bin/python -m scripts.build_demo_video
```
The live loop needs the separate Godot MCP server and scenes (see provenance below); set their location in the untracked
`scripts/env.local.sh` (variables in `propriosam/local_config.py`). Replay, tests and the dashboard do not.

## How it works
`docs/ARCHITECTURE_PROVENANCE.md` has the dataflow and the honesty rules enforced in code. `docs/RUN_BUNDLE_SPEC.md` documents
the replayable bundle. `docs/DASHBOARD.md` covers the telemetry UI.

- `propriosam/meta_client.py`: Meta Model API client (bearer auth from the environment, request-id and usage log, spend cap, SAM cache)
- `propriosam/vision_tracker.py`: SAM 3.1 wire parser, tracks, coverage, mask decoding with Meta's `meta-sam-parser`, overlays
- `propriosam/sensory_contract.py`: Muse-compiled, frozen, falsifiable contract (structured output)
- `propriosam/verifier.py`: the frozen residual rule, the coverage gates and the approach gate; the only place a verdict is made
- `propriosam/mcp_adapter.py`: fresh working copy with hash check, tick-locked capture, Muse's allowlisted tools
- `propriosam/diagnosis.py`: screened evidence, then the Muse tool loop (Responses API, native function tools)
- `propriosam/repair_orchestrator.py`: the state machine
- `propriosam/artifacts.py`: immutable bundles
- `web/`: React 19 telemetry dashboard over exported bundles

## Architecture Provenance: Hackathon Work vs. Existing Infrastructure
Hackathon period: October 26 – November 4, 2026.
Pre-existing infrastructure: KINETIC-ORACLE uses an existing, independently developed Godot MCP server and associated test fixtures as its simulation and tool-execution environment. These predate the hackathon and are disclosed as supporting infrastructure. They are not claimed as new hackathon contributions.
New hackathon contributions: SAM 3.1 integration and temporal tracking; visual-state measurements and falsifiable sensory contracts; independent residual evaluation; Muse-powered diagnosis and bounded repair; closed-loop orchestration; reproducible run artifacts; interactive diagnostic interface; associated tests.

## Honesty notes
Every verdict in this repository comes from `propriosam/verifier.py` over SAM 3.1 tracks under a contract frozen before
measurement. Tool statuses and model text are recorded but never consulted. Hidden engine ground truth is stored for evaluation
only and is never shown to any model. This is one scene family with a small number of runs: it shows the mechanism, not a rate.
Limitations are listed in the evaluation report. This public copy is sanitised: identity metadata and the names of private
tooling were replaced throughout its history, and 42 recorded files carry visible `<redacted:…>` markers. No verdict, measurement,
model decision or replay input changed. What changed, what did not, and which checks need the private originals:
`docs/SANITIZATION.md`.

## License
- **Code, tests and documentation:** MIT. See `LICENSE`.
- **Run evidence and media:** `runs/`, `web/public/runs/`, `tests/fixtures/` and the demo video are covered by
  `EVIDENCE_AND_MEDIA.md`, not by the MIT licence. You may review, replay, verify, quote and redistribute them unmodified.
  They include outputs of Meta models, which the author holds under the Meta Model API Terms of Service, and recordings and
  source excerpts of a pre-existing test game that is not part of the entry.
- **Dependencies and services:** see `THIRD_PARTY_NOTICES.md`. This project uses Meta's SAM Materials (SAM 3.1 and
  `meta-sam-parser`). `meta-sam-parser` is under Meta's SAM License, which is not an open-source licence.
