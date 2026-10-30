"""Closed-loop state machine.

stage copy -> compile contract -> [capture -> SAM -> verify] -> if FAIL:
diagnose/repair (turn k <= max, Wonder escalation after a failed Spark turn)
-> relaunch -> [capture -> SAM -> verify] ... -> manifest.

Only the verifier's status moves the machine. INCONCLUSIVE stops the loop
(it is a sensing problem, not a scene fault). Everything is written to
runs/<run_id>/ even when a step raises."""
from __future__ import annotations

import platform
import traceback
from pathlib import Path

from . import __version__
from .artifacts import RUNS_DIR, RunManifest, git_state, new_run_id, save_manifest, tree_sha256, write_json
from .diagnosis import diagnose_and_repair
from .evaluation import track_and_verify
from .mcp_adapter import DiagnosisTools, GodotStudio, capture_clip, stage_working_copy
from .meta_client import SAM_MODEL, SPARK, WONDER, MetaClient, utc_now
from .sensory_contract import compile_contract
from .verifier import VerificationStatus, rule_sha256


async def run_closed_loop(*, baseline: Path, scenario, run_id: str | None = None, max_repair_turns: int = 3,
                          model: str = SPARK, escalation_model: str | None = WONDER, budget_usd: float = 40.0,
                          capture_timeout_s: float = 30.0, use_contract_cache: bool = True, verbose: bool = True,
                          label: str = "") -> Path:
    S = scenario
    run_id = run_id or new_run_id("run")
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    log = (lambda *a: print(*a, flush=True)) if verbose else (lambda *a: None)
    client = MetaClient(run_dir, budget_usd=budget_usd)
    m = RunManifest(run_id=run_id, kind="closed_loop", created_at=utc_now(),
                    models={"contract": model, "diagnosis": model, "escalation": escalation_model, "sam": SAM_MODEL},
                    environment={"propriosam": __version__, "python": platform.python_version(), "host": platform.platform(),
                                 "git": git_state()},
                    anti_cheat={"banned_terms": list(S.BANNED_PROMPT_TERMS), "turns": []},
                    notes=[label] if label else [])
    base_sha, base_n = tree_sha256(baseline)
    m.baseline = {"path": str(baseline), "tree_sha256": base_sha, "files": base_n}
    result = None
    try:
        ws = stage_working_copy(baseline, run_dir / "workspace")
        m.workspace = ws
        if not ws["baseline_match_at_stage"]:
            raise RuntimeError("staged working copy does not hash-match the baseline")
        ws_path = Path(ws["path"])
        log(f"[stage] {ws_path.name} tree={ws['staged_tree_sha256'][:12]} == baseline {base_sha[:12]}")

        contract = compile_contract(client, objective=S.OBJECTIVE, scene_brief=S.SCENE_BRIEF, vocabulary=S.CONCEPT_VOCABULARY,
                                    frame_count=S.FRAME_COUNT, fps=S.FPS, frame_size=S.FRAME_SIZE, model=model,
                                    use_cache=use_contract_cache)
        write_json(run_dir / "contract.json", contract)
        m.contract_path, m.contract_sha256, m.rule_sha256 = "contract.json", contract.frozen_sha256, rule_sha256()
        log(f"[contract] {contract.contract_id} mover='{contract.mover_concept}' barrier='{contract.barrier_concept}' "
            f"thr={contract.rule.threshold_px} persist={contract.rule.persistence_frames} window={contract.coverage.critical_window}")

        async with GodotStudio(extra_root=RUNS_DIR, log_path=run_dir / "mcp_calls.jsonl") as studio:
            audit = await studio.call("godot_environment_audit")
            m.environment["godot"] = audit.get("godot")
            pass_i = 1
            cap = await capture_clip(studio, ws_path, run_dir / f"pass{pass_i}", label=f"{run_id}-pass{pass_i}",
                                     frame_count=S.FRAME_COUNT, every_ticks=S.CAPTURE_EVERY_TICKS, settle_ticks=S.SETTLE_TICKS,
                                     sidestep_ticks=S.SIDESTEP_TICKS, fps=S.FPS, timeout_s=capture_timeout_s)
            log(f"[pass{pass_i}] captured {cap['capture']['frame_count']} frames in {cap['capture']['duration_s']}s; tool said: {str(cap['open_loop'].get('result'))[:80]}")
            rec, result, _ = track_and_verify(client, run_dir / f"pass{pass_i}", index=pass_i, label="open-loop (before repair)",
                                              clip_mp4=cap["clip"], frames_dir=cap["frames_dir"], contract=contract,
                                              capture=cap["capture"], open_loop=cap["open_loop"], truth_hidden=cap["truth_hidden"],
                                              project_tree_sha256=tree_sha256(ws_path)[0],
                                              overlay_title=f"Pass {pass_i}: the agent's tool said OK — SAM 3.1 under contract {contract.contract_id}")
            m.passes.append(rec)
            log(f"[pass{pass_i}] verifier: {result.status.value} t_fail={result.t_fail} maxE={result.max_residual} cov={result.coverage.get('both_window')}")

            previous_turns: list[dict] = []
            turn = 0
            while result.status == VerificationStatus.FAIL and turn < max_repair_turns:
                turn += 1
                mdl = model if turn == 1 or not escalation_model else escalation_model
                tools = DiagnosisTools(studio, ws_path, S, run_dir / f"repair_turn_{turn}")
                log(f"[turn {turn}] diagnosis by {mdl}")
                rt = await diagnose_and_repair(client, tools, contract=contract, result=result, open_loop=rec.open_loop,
                                               previous_turns=previous_turns, scenario=S, model=mdl, turn=turn,
                                               turn_dir=run_dir / f"repair_turn_{turn}", verbose=verbose)
                m.repair_turns.append(rt)
                m.anti_cheat["turns"].append({"turn": turn, **rt.anti_cheat})
                log(f"[turn {turn}] {rt.tool_calls} tool calls, {len(rt.patches)} patch(es), est ${rt.est_cost_usd}")
                if not rt.patches:
                    m.notes.append(f"turn {turn}: no patch applied")
                    previous_turns.append({"turn": turn, "model": mdl, "patches": [], "result_after": "no patch applied"})
                    continue
                pass_i += 1
                cap = await capture_clip(studio, ws_path, run_dir / f"pass{pass_i}", label=f"{run_id}-pass{pass_i}",
                                         frame_count=S.FRAME_COUNT, every_ticks=S.CAPTURE_EVERY_TICKS, settle_ticks=S.SETTLE_TICKS,
                                         sidestep_ticks=S.SIDESTEP_TICKS, fps=S.FPS, timeout_s=capture_timeout_s)
                rec, result, _ = track_and_verify(client, run_dir / f"pass{pass_i}", index=pass_i, label=f"after repair turn {turn}",
                                                  clip_mp4=cap["clip"], frames_dir=cap["frames_dir"], contract=contract,
                                                  capture=cap["capture"], open_loop=cap["open_loop"], truth_hidden=cap["truth_hidden"],
                                                  project_tree_sha256=tree_sha256(ws_path)[0],
                                                  overlay_title=f"Pass {pass_i}: after {mdl} repair (turn {turn}) — SAM 3.1 re-verification")
                m.passes.append(rec)
                log(f"[pass{pass_i}] verifier: {result.status.value} t_fail={result.t_fail} maxE={result.max_residual} cov={result.coverage.get('both_window')}")
                previous_turns.append({"turn": turn, "model": mdl, "patches": rt.patches,
                                       "result_after": f"status={result.status.value} t_fail={result.t_fail} max_E={result.max_residual}"})
        m.final_verdict = result.status.value
        m.status = "COMPLETE"
        if result.status == VerificationStatus.INCONCLUSIVE:
            m.notes.append("INCONCLUSIVE: sensing coverage gate unmet; no repair attempted on this basis")
    except Exception as e:
        m.status = "ERROR"
        m.final_verdict = result.status.value if result is not None else None
        m.notes.append(f"{type(e).__name__}: {e}")
        (run_dir / "error_traceback.txt").write_text(traceback.format_exc())
        log(f"[error] {type(e).__name__}: {e}")
    finally:
        after_sha, _ = tree_sha256(baseline)
        m.baseline["tree_sha256_after_run"] = after_sha
        m.baseline["unchanged"] = after_sha == base_sha
        if m.workspace.get("path") and Path(m.workspace["path"]).exists():
            m.workspace["final_tree_sha256"] = tree_sha256(m.workspace["path"])[0]
            m.workspace["modified_during_run"] = m.workspace["final_tree_sha256"] != m.workspace.get("staged_tree_sha256")
        m.spend = client.spend_summary()
        m.request_ids = m.spend.pop("request_ids", [])
        m.finished_at = utc_now()
        save_manifest(run_dir, m)
        log(f"[done] {run_id} status={m.status} verdict={m.final_verdict} passes={len(m.passes)} turns={len(m.repair_turns)} "
            f"est_cost=${m.spend['est_cost_usd']:.3f} baseline_unchanged={m.baseline['unchanged']}")
    return run_dir
