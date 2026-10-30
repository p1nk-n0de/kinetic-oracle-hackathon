# Evaluation report: KINETIC-ORACLE (ProprioSAM)

Generated 2026-10-30T14:12:09+00:00 from the bundles under `runs/`, all produced by the same verifier (rule hash `35dd508645d9`). Every verdict below is the frozen verifier's decision over SAM 3.1 tracks. MCP tool status and model text are recorded but never consulted. Engine ground truth exists in each bundle (`truth_hidden.json`) for evaluation only and was never shown to any model.

## Case 1: defective scene, full closed loop (independent trials)

| run | passes | repair turns | final verdict | baseline unchanged | cost | wall time |
|---|---|---|---|---|---|---|
| `run_20261030-132053_bf568b` | FAIL@60 (max E +236 px) → PASS (max E -12 px) | T1 muse-spark-1.3: 16 calls, 1 patch in scenes/player.tscn | **PASS** | True | $0.151 | 142.0 s |
| `run_20261030-132315_7c6e9b` | FAIL@60 (max E +234 px) → PASS (max E -12 px) | T1 muse-spark-1.3: 11 calls, 1 patch in scripts/arena_layout.gd | **PASS** | True | $0.143 | 107.0 s |
| `run_20261030-132503_349fe5` | FAIL@60 (max E +235 px) → PASS (max E -13 px) | T1 muse-spark-1.3: 17 calls, 1 patch in scripts/arena_layout.gd | **PASS** | True | $0.182 | 167.0 s |

- `bf568b` T1 (muse-spark-1.3) stated reason: Player mask=1 ignores Hurdle on layer 2, so move_and_slide never collides and the capsule walks through. Mask=3 scans both world(1) and hurdle(2) layers.
- `7c6e9b` T1 (muse-spark-1.3) stated reason: Hurdle on layer 2 is invisible to player mask 1, so no collision; restore to world layer 1.
- `349fe5` T1 (muse-spark-1.3) stated reason: Hurdle on layer 2 is invisible to player mask 1, so no collision; put it on world layer 1.

## Case 2a: known-good twin of the capsule scene (true negative)

| run | passes | repair turns | final verdict | baseline unchanged | cost | wall time |
|---|---|---|---|---|---|---|
| `run_20261030-132750_e09010` | PASS (max E -12 px) | none | **PASS** | True | $0.032 | 31.0 s |


## Case 2b: real robot build under a robot contract (generalisation, true negative)

| run | passes | repair turns | final verdict | baseline unchanged | cost | wall time |
|---|---|---|---|---|---|---|
| `run_20261030-132822_293587` | PASS (max E -33 px) | none | **PASS** | True | $0.059 | 58.0 s |


## Case 2c: real robot build under the capsule contract (sensing honesty)

| run | passes | repair turns | final verdict | baseline unchanged | cost | wall time |
|---|---|---|---|---|---|---|
| `run_20261030-132921_7fecb2` | INCONCLUSIVE (max E n/a) | none | **INCONCLUSIVE** | True | $0.032 | 31.0 s |


The contract's concept does not exist in this build, so SAM 3.1 returned no track. Verifier reasons: SAM 3.1 returned no track for mover concept 'capsule'; both-tracked coverage in window (20, 70) = 0.00 < 0.8; mover coverage 0.00 < 0.7. No repair was attempted on a sensing failure.

## Case 3a: a different wrong layer

| run | passes | repair turns | final verdict | baseline unchanged | cost | wall time |
|---|---|---|---|---|---|---|
| `run_20261030-132953_c0fc3b` | FAIL@60 (max E +237 px) → PASS (max E -13 px) | T1 muse-spark-1.3: 11 calls, 1 patch in scripts/arena_layout.gd | **PASS** | True | $0.138 | 101.0 s |

- `c0fc3b` T1 (muse-spark-1.3) stated reason: Hurdle on layer 4 is invisible to player mask=1, so no collision and player walks through. Put it on world layer 1.

## Case 3b: a different root cause (collision shape disabled in the builder)

| run | passes | repair turns | final verdict | baseline unchanged | cost | wall time |
|---|---|---|---|---|---|---|
| `run_20261030-133135_e86e1b` | FAIL@60 (max E +236 px) → PASS (max E -12 px) | T1 muse-spark-1.3: 11 calls, 1 patch in scripts/arena_builder.gd | **PASS** | True | $0.126 | 94.0 s |

- `e86e1b` T1 (muse-spark-1.3) stated reason: Hurdle CollisionShape was created disabled, so the yellow bar is visual-only and the player walks through it. Enable collision so the hurdle physically blocks walking.

## Case 3c: two simultaneous faults

| run | passes | repair turns | final verdict | baseline unchanged | cost | wall time |
|---|---|---|---|---|---|---|
| `run_20261030-133310_79a91f` | FAIL@60 (max E +236 px) → PASS (max E -13 px) | T1 muse-spark-1.3: 10 calls, 2 patch in scripts/arena_builder.gd, scripts/arena_layout.gd | **PASS** | True | $0.130 | 99.0 s |

- `79a91f` T1 (muse-spark-1.3) stated reason: Hurdle shape was created disabled so it had no collision; enable it so the bar physically blocks the player.
- `79a91f` T1 (muse-spark-1.3) stated reason: Hurdle was on layer 2 while player mask is 1, so no collision even when enabled; restore documented layer 1.

## Case 3d: three faults in three files, two patches per turn

| run | passes | repair turns | final verdict | baseline unchanged | cost | wall time |
|---|---|---|---|---|---|---|
| `run_20261030-133450_d73762` | FAIL@60 (max E +235 px) → PASS (max E -12 px) | T1 muse-spark-1.3: 14 calls, 2 patch in scripts/arena_builder.gd, scripts/player.gd | **PASS** | True | $0.158 | 119.0 s |

- `d73762` T1 (muse-spark-1.3) stated reason: Hurdle shape was disabled and placed on layer 2 while player mask is 1, so no collision. Force world layer 1 and enabled shape.
- `d73762` T1 (muse-spark-1.3) stated reason: reset_to_spawn added a collision exception for the Hurdle, letting player pass through. Remove it so hurdle collides.

## Case 3e: the real robot build with the hurdle on the wrong layer

| run | passes | repair turns | final verdict | baseline unchanged | cost | wall time |
|---|---|---|---|---|---|---|
| `run_20261030-133649_b146ca` | FAIL@62 (max E +223 px) → PASS (max E -32 px) | T1 muse-spark-1.3: 15 calls, 1 patch in scripts/arena_layout.gd | **PASS** | True | $0.151 | 137.0 s |

- `b146ca` T1 (muse-spark-1.3) stated reason: Hurdle on layer 2 never collides with player mask 1, so it is ghost; restore to default world layer 1.

## Case 3f: the same three faults, bounded to one patch per turn

| run | passes | repair turns | final verdict | baseline unchanged | cost | wall time |
|---|---|---|---|---|---|---|
| `run_20261030-134044_f95522` | FAIL@60 (max E +234 px) → INCONCLUSIVE (max E n/a) | T1 muse-spark-1.3: 12 calls, 1 patch in scripts/player.gd | **INCONCLUSIVE** | True | $0.151 | 107.0 s |
| `run_20261030-134338_9cf9f4` | FAIL@60 (max E +235 px) → PASS (max E -12 px) | T1 muse-spark-1.3: 11 calls, 1 patch in scripts/player.gd | **PASS** | True | $0.154 | 114.0 s |
| `run_20261030-134544_a2314f` | FAIL@60 (max E +235 px) → PASS (max E -12 px) | T1 muse-spark-1.3: 13 calls, 1 patch in scripts/player.gd | **PASS** | True | $0.151 | 112.0 s |
| `run_20261030-134737_d075ab` | FAIL@60 (max E +236 px) → PASS (max E -12 px) | T1 muse-spark-1.3: 12 calls, 1 patch in scripts/player.gd | **PASS** | True | $0.162 | 129.0 s |
| `run_20261030-134947_c31b06` | FAIL@60 (max E +235 px) → PASS (max E -13 px) | T1 muse-spark-1.3: 12 calls, 1 patch in scripts/player.gd | **PASS** | True | $0.149 | 129.0 s |
| `run_20261030-135231_674ad3` | FAIL@60 (max E +235 px) → PASS (max E -12 px) | T1 muse-spark-1.3: 12 calls, 1 patch in scripts/player.gd | **PASS** | True | $0.139 | 102.0 s |
| `run_20261030-135414_4556fe` | FAIL@60 (max E +234 px) → PASS (max E -12 px) | T1 muse-spark-1.3: 13 calls, 1 patch in scripts/player.gd | **PASS** | True | $0.165 | 136.0 s |
| `run_20261030-135631_cda0ab` | FAIL@60 (max E +237 px) → PASS (max E -12 px) | T1 muse-spark-1.3: 11 calls, 1 patch in scripts/player.gd | **PASS** | True | $0.130 | 110.0 s |
| `run_20261030-135822_cfbb17` | FAIL@60 (max E +235 px) → PASS (max E -12 px) | T1 muse-spark-1.3: 12 calls, 1 patch in scripts/player.gd | **PASS** | True | $0.137 | 116.0 s |
| `run_20261030-140019_79d646` | FAIL@60 (max E +235 px) → FAIL@60 (max E +236 px) → PASS (max E -13 px) | T1 muse-spark-1.3: 13 calls, 1 patch in scripts/arena_builder.gd; T2 muse-wonder-1.0: 15 calls, 1 patch in scripts/player.gd | **PASS** | True | $0.409 | 235.0 s |

- `f95522` T1 (muse-spark-1.3) stated reason: Hurdle collision is triple-disabled (layer 2 vs mask 1, shape.disabled, exception). Restoring solid contact at runtime so walking is blocked.
- `9cf9f4` T1 (muse-spark-1.3) stated reason: Hurdle shape is disabled + on layer 2 (player mask 1) + explicitly excepted, so no contact. Make reset enforce solid hurdle instead of ignoring it.
- `a2314f` T1 (muse-spark-1.3) stated reason: Hurdle had disabled shape + wrong layer + explicit player collision exception, letting the capsule pass through. Restore solid contact without moving/resizing the barrier.
- `d075ab` T1 (muse-spark-1.3) stated reason: Hurdle shape is disabled in builder, on wrong layer (2 vs player mask 1), plus player adds collision exception. Repair hurdle at spawn: clear exception, force layer 1, enable shape so walking is blocked.
- `c31b06` T1 (muse-spark-1.3) stated reason: Hurdle has no collision: shape disabled in builder, wrong layer (2 vs player mask 1), plus explicit add_collision_exception_with(Hurdle). Replace exception with enforcement of solid layer-1 collision so walking forward i
- `674ad3` T1 (muse-spark-1.3) stated reason: Hurdle collision was disabled three ways: shape.disabled, layer 2 vs mask 1, plus explicit exception. Re-enable solid contact so walking is stopped.
- `4556fe` T1 (muse-spark-1.3) stated reason: Hurdle was non-collidable (disabled shape, layer 2 vs player mask 1, plus explicit collision exception) so player walked through. Restore solid blocking without moving/resizing barrier.
- `cda0ab` T1 (muse-spark-1.3) stated reason: Hurdle has no collision: layer 2 vs player mask 1, shape.disabled, plus exception. Enable and re-layer it and clear exception so walking is physically blocked.
- `cfbb17` T1 (muse-spark-1.3) stated reason: Hurdle has no collision: shape disabled, layer 2 vs player mask 1, plus player adds collision exception. Repair hurdle to solid layer-1 and clear exception on reset.
- `79d646` T1 (muse-spark-1.3) stated reason: Hurdle shape was disabled and placed on layer 2 while player mask is 1, so no contact possible; force solid world-layer collision.
- `79d646` T2 (muse-wonder-1.0) stated reason: Remove the explicit collision exception that makes Player ignore Hurdle on every reset_to_spawn/start_run, so solid layer-1 hurdle (enabled after turn1) actually blocks capsule without jumping. Exception persisted after 

## How the one-patch case was sampled

Case 3f ran 10 times: one run, then 3 more, then up to 8 more with a stopping rule set in advance: stop at the first run that needs a second repair turn. All of them are in the table above. 8 were solved in a single turn, because Muse Spark put all three fixes into one patch; 1 needed a second turn; 1 ended INCONCLUSIVE. The counts show how often this happened in this sample, not a rate.

## The repair the verifier rejected

In `run_20261030-140019_79d646` Muse Spark patched scripts/arena_builder.gd and its closing text said the contract was satisfied:

> root cause: Hurdle body non-collidable (shape disabled + layer 2 vs player mask 1, plus player collision exception). patch: arena_builder.gd force layer 1 and shape.disabled=false for all blocks. why it satisfies the contract: solid 0.55m hurdle now blocks CharacterBody so E(t) stays ≤5px.

The game was relaunched and re-measured, and the verifier returned FAIL at frame 60 (max E +236 px). The model's claim changed nothing. The next turn escalated to muse-wonder-1.0, which found the remaining fault and patched scripts/player.gd. The verifier then returned PASS (max E -13 px). This is the run the demo is built on.

## The repair that broke the game

With only one patch available, Muse Spark put all three fixes into the player script and called `remove_collision_exception_from`, a method that does not exist. The script no longer loaded and the game froze at spawn: no HUD, player at z = 0, never moving. The patch tool reported success, the input tool reported success, and Muse's closing text said the contract was satisfied. A plain 'did it cross the hurdle?' check would have passed, because the player never moved. The verifier returned INCONCLUSIVE because SAM 3.1 could no longer find the capsule, and the engine's own record confirms the player never left spawn. The first run of this case is kept as recorded (`run_20261030-134044_f95522`); the loop then stopped on any INCONCLUSIVE. It now treats INCONCLUSIVE after a repair as 'repair not verified' and gives Muse another bounded turn, and Muse gained a runtime-errors tool.

## Hidden-truth audit

After the runs, each verdict is compared with the engine's own record of where the player went. The verifier and Muse never see this data. A verdict is a match if it agrees with the engine, abstained if the verifier said INCONCLUSIVE, and WRONG if it said PASS or FAIL against the engine.

**39 match, 1 abstained, 0 wrong** over 40 passes.

| case | run | pass | verifier | engine: furthest z, crossed hurdle | outcome |
|---|---|---|---|---|---|
| case1 | `bf568b` | 1 | FAIL | -15.77, True | match |
| case1 | `bf568b` | 2 | PASS | -11.4, False | match |
| case1 | `7c6e9b` | 1 | FAIL | -15.77, True | match |
| case1 | `7c6e9b` | 2 | PASS | -11.4, False | match |
| case1 | `349fe5` | 1 | FAIL | -15.77, True | match |
| case1 | `349fe5` | 2 | PASS | -11.4, False | match |
| case2a | `e09010` | 1 | PASS | -11.4, False | match |
| case2b | `293587` | 1 | PASS | -11.4, False | match |
| case2c | `7fecb2` | 1 | INCONCLUSIVE | -11.4, False | abstained |
| case3a | `c0fc3b` | 1 | FAIL | -15.77, True | match |
| case3a | `c0fc3b` | 2 | PASS | -11.4, False | match |
| case3b | `e86e1b` | 1 | FAIL | -15.77, True | match |
| case3b | `e86e1b` | 2 | PASS | -11.4, False | match |
| case3c | `79a91f` | 1 | FAIL | -15.77, True | match |
| case3c | `79a91f` | 2 | PASS | -11.4, False | match |
| case3d | `d73762` | 1 | FAIL | -15.77, True | match |
| case3d | `d73762` | 2 | PASS | -11.4, False | match |
| case3e | `b146ca` | 1 | FAIL | -15.77, True | match |
| case3e | `b146ca` | 2 | PASS | -11.4, False | match |
| case3f | `f95522` | 1 | FAIL | -15.77, True | match |
| case3f | `f95522` | 2 | INCONCLUSIVE | 0.0, False | match |
| case3f | `9cf9f4` | 1 | FAIL | -15.77, True | match |
| case3f | `9cf9f4` | 2 | PASS | -11.4, False | match |
| case3f | `a2314f` | 1 | FAIL | -15.77, True | match |
| case3f | `a2314f` | 2 | PASS | -11.4, False | match |
| case3f | `d075ab` | 1 | FAIL | -15.77, True | match |
| case3f | `d075ab` | 2 | PASS | -11.4, False | match |
| case3f | `c31b06` | 1 | FAIL | -15.77, True | match |
| case3f | `c31b06` | 2 | PASS | -11.4, False | match |
| case3f | `674ad3` | 1 | FAIL | -15.77, True | match |
| case3f | `674ad3` | 2 | PASS | -11.4, False | match |
| case3f | `4556fe` | 1 | FAIL | -15.77, True | match |
| case3f | `4556fe` | 2 | PASS | -11.4, False | match |
| case3f | `cda0ab` | 1 | FAIL | -15.77, True | match |
| case3f | `cda0ab` | 2 | PASS | -11.4, False | match |
| case3f | `cfbb17` | 1 | FAIL | -15.77, True | match |
| case3f | `cfbb17` | 2 | PASS | -11.4, False | match |
| case3f | `79d646` | 1 | FAIL | -15.77, True | match |
| case3f | `79d646` | 2 | FAIL | -15.77, True | match |
| case3f | `79d646` | 3 | PASS | -11.4, False | match |

### The vacuous pass this audit caught

An earlier run on the robot build returned PASS. The audit showed the robot had stopped at z = -7.13, about 4.3 m short of the hurdle at frame 38 of 80. The held forward input was lost mid-walk, and no tool reported an error: exactly the failure class this project exists to expose, and it happened to our own harness. The rule 'must not cross' was true only because the robot never got there.

Two fixes followed. The verifier gained an approach gate: a PASS now requires the mover to come within one body height of the barrier, otherwise the contract was not exercised and the verdict is INCONCLUSIVE. The capture recipe now re-asserts the held input every step. That run's real SAM output is kept as a regression test (`tests/fixtures/dropped_input_walk`, `test_real_dropped_input_run_no_longer_passes`). All bundles in this report were regenerated after the fix.

## Coverage honesty (manual contract perturbation)

mover_concept 'capsule' -> 'blue capsule' (a phrase SAM 3.1 returns nothing for in this scene): mover tracked in 0 frames, barrier in 80. Verifier: **INCONCLUSIVE** (SAM 3.1 returned no track for mover concept 'blue capsule'; both-tracked coverage in window (20, 70) = 0.00 < 0.8; mover coverage 0.00 < 0.7). Expected INCONCLUSIVE (never PASS).

## Ablation: why temporal SAM 3.1 tracking matters

Reference bundle: `run_20261030-140019_79d646`.

| method | what it looks at | answer | matches the verifier? |
|---|---|---|---|
| (a) Open-loop tool trust | the MCP result of the walk action on the defective scene: `{"input": {"action": "move_forward", "mode": "press", "ms": 0, "ticks": 30}, "re` | PASS (the tool reported no error) | no |
| (b) Static screenshot VLM (muse-spark-1.3) | early frame, defective scene (frame 40) | {'PASS': 2, 'UNPARSED': 1} over 3 calls | 0/3 (verifier: FAIL) |
| (b) Static screenshot VLM (muse-spark-1.3) | last frame, defective scene (frame 79) | {'FAIL': 3} over 3 calls | 3/3 (verifier: FAIL) |
| (b) Static screenshot VLM (muse-spark-1.3) | early frame, repaired scene (frame 40) | {'PASS': 1, 'UNPARSED': 1, 'UNSURE': 1} over 3 calls | 1/3 (verifier: PASS) |
| (b) Static screenshot VLM (muse-spark-1.3) | last frame, repaired scene (frame 79) | {'PASS': 3} over 3 calls | 3/3 (verifier: PASS) |
| (b) Static screenshot VLM (muse-spark-1.3) | last frame, game frozen by a broken repair (frame 79) | {'FAIL': 3} over 3 calls | 3/3 (verifier: INCONCLUSIVE) |
| (c) KINETIC-ORACLE | 80-frame SAM 3.1 tracks + frozen residual | FAIL at frame 60, repaired, then PASS | the verifier itself |

A static screenshot is not useless: shown the right frame, the model can get this scene right, and the table says how often it did. The difference is that a screenshot needs someone to know when to look, gives no measured quantity to re-check, and has no notion of an action that never happened. The temporal track gives a frame-accurate, replayable number.

## Limitations

- One scene family and one defect family (the hurdle fails to collide), with a few variations. The numbers show the mechanism, not a rate.
- Muse's repairs pass the visual contract but are not reviewed for code quality. Some are blunt: one forces layer 1 on every block.
- The residual is specific to this chase camera: it compares the barrier's bottom edge with the player's feet. Other camera rigs need other invariants.
- SAM concept phrases are scene-calibrated. `capsule` works and `blue capsule` returns nothing. The verifier reports that as INCONCLUSIVE and never guesses.
- On the capsule scene the repaired margin is small (about 12 to 13 px) compared with box jitter (about 4 px).
- The approach gate is a screen-space heuristic (one body height), not a measured distance.
- Muse's prompts are blind by construction (screened and hashed per turn), but the scene source documents the normal layer convention, which a competent reader uses, as a human engineer would.
- The Godot MCP server and the test scenes predate the hackathon and are disclosed as supporting infrastructure (`docs/ARCHITECTURE_PROVENANCE.md`).
