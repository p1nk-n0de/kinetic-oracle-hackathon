# Demo script (3 minutes)

The 3-minute video is the primary judging artifact. Everything shown below is from real runs. Hero bundle: `run_20261030-140019_79d646`.
Open the dashboard with `cd web && npm run dev`, then `http://localhost:5173/#run=run_20261030-140019_79d646`.

| Time | On screen | Say (in your own words) |
|---|---|---|
| 0:00–0:20 | Pass 1 raw clip: the player walks straight through the yellow bar. Dashboard badge: `MCP tool said OK` | "This agent told a game to walk into a wall. The tool said OK. The player walked through it. Agents believe their tools, and tools only report that a call succeeded, not what happened." |
| 0:20–0:45 | Residual chart, E(t) crossing the threshold, `t_fail` marker at frame 60; scrub the player to frame 60 | "KINETIC-ORACLE watches instead. SAM 3.1 tracks the player and the barrier through all 80 frames. A rule frozen before the run measures one number per frame, and that number decides. Here it says the player crossed at frame 60." |
| 0:45–1:10 | Contract panel, then the Diagnosis panel showing the prompt: numbers, no file names | "Muse Spark wrote the falsifiable contract from the objective. When it fails, Muse gets only the measurements and a few inspection tools. No hints, no ground truth, and every prompt is screened and hashed." |
| 1:10–1:45 | Proof clip `runs/kinetic_oracle_demo_proof.mp4`, stop on the three panels at about frame 65: Spark's claim above `VERIFIER: FAIL` | "Muse Spark patches the game and says it's fixed. Read its claim. Now read the verifier. Same failure, same frame. The model doesn't get to declare success. The evidence goes back, the loop escalates to Muse Wonder, it finds the fault Spark didn't fix, and now the player stops at the bar. PASS, from the numbers alone." |
| 1:45–2:15 | Hidden-truth chart, then the frozen-game clip from `run_20261030-134044_f95522` pass 2 | "We tested this harder than we planned to. In one run Muse's patch called a method that doesn't exist and froze the game at spawn. Every tool said OK, and a plain 'did it cross?' check would have passed. The verifier refused. And our own harness failed once: an input was silently lost, the player stopped short, and our verifier passed it. The hidden-truth audit caught that, so we added a gate: a pass must prove the action actually happened." |
| 2:15–2:40 | Evaluation report: 40 passes, 39 match, 1 abstained, 0 wrong. Terminal: `python -m scripts.replay_run --run-dir runs/run_20261030-140019_79d646`, "REPLAY OK" in under a second | "Across 21 runs and 40 measured passes, no verdict contradicted the engine's own record. Any judge can replay every verdict offline from the raw SAM output, for free." |
| 2:40–3:00 | Architecture line from the README, then the provenance note | "Self-healing is only worth trusting if something independent checks it. SAM 3.1 gives agents that sense. The Godot tooling predates this hackathon and is disclosed; everything else was built this week." |

## Ground rules for the edit
- Do not say the system is accurate at any rate. n is small, and `docs/EVALUATION_REPORT.md` says so.
- If you mention screenshots: they work if you pick the right frame (the report has the numbers). The point is not having to know when to look.
- Say that the three-fault hero run came from a one-patch-per-turn setting, and that most runs fixed it in one turn. The report states the sampling.
