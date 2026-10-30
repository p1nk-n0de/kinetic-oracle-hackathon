"""Honest multi-case evaluation and ablation baselines.

Reads the closed-loop bundles already on disk, runs two cheap live checks
(the static-screenshot VLM baseline and a coverage-honesty perturbation of the
contract), and writes runs/evaluation_summary.json + docs/EVALUATION_REPORT.md.
Nothing here changes a verdict: every number is copied from a bundle or
measured live and labelled by its source.

  MODEL_API_KEY=... .venv/bin/python -m scripts.run_evaluation [--skip-live]"""
from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from propriosam import vision_tracker as vt
from propriosam.artifacts import RUNS_DIR, load_manifest, new_run_id, write_json
from propriosam.meta_client import SPARK, MetaClient, utc_now
from propriosam.sensory_contract import SensoryContract
from propriosam.verifier import verify
from scenarios.godot_hurdle import scenario as S

REPORT = Path(__file__).resolve().parents[1] / "docs" / "EVALUATION_REPORT.md"


def _dur(m) -> float | None:
    try:
        return round((datetime.fromisoformat(m.finished_at) - datetime.fromisoformat(m.created_at)).total_seconds(), 1)
    except Exception:
        return None


def _trial_row(d: Path, m) -> dict:
    p1, pl = m.passes[0], m.passes[-1]
    return {"run_id": m.run_id, "label": (m.notes or [""])[0], "status": m.status, "baseline": m.baseline.get("path"),
            "pass1": {"status": p1.verification_status, "t_fail": p1.t_fail, "max_E_px": p1.max_residual,
                      "coverage_window": json.loads((d / p1.verification_path).read_text())["coverage"].get("both_window")},
            "repair_turns": [{"turn": t.turn, "model": t.model, "tool_calls": t.tool_calls, "patches": len(t.patches),
                              "patch": (t.patches[0]["path"] + ": " + t.patches[0]["replace"][-40:]) if t.patches else None,
                              "banned_terms_found": t.anti_cheat.get("banned_terms_found"), "est_cost_usd": t.est_cost_usd}
                             for t in m.repair_turns],
            "final": {"status": pl.verification_status, "t_fail": pl.t_fail, "max_E_px": pl.max_residual, "pass_index": pl.index},
            "final_verdict": m.final_verdict, "baseline_unchanged": m.baseline.get("unchanged"),
            "copy_matched_baseline_at_stage": m.workspace.get("baseline_match_at_stage"),
            "request_ids": len(m.request_ids), "est_cost_usd": m.spend.get("est_cost_usd"), "duration_s": _dur(m)}


def collect() -> dict:
    cases = {"case1_defective_scene_closed_loop": [], "case2_known_good_true_negative": [], "case3_perturbed_defect": [], "other": []}
    for d in sorted(RUNS_DIR.glob("run_*")):
        if not (d / "run_manifest.json").exists():
            continue
        m = load_manifest(d)
        if m.kind != "closed_loop" or not m.passes:
            continue
        b = m.baseline.get("path", "")
        row = _trial_row(d, m)
        if b == str(S.DEFECT_BASELINE):
            cases["case1_defective_scene_closed_loop"].append(row)
        elif b == str(S.KNOWN_GOOD_BASELINE):
            cases["case2_known_good_true_negative"].append(row)
        elif "_baselines" in b:
            cases["case3_perturbed_defect"].append(row)
        else:
            cases["other"].append(row)
    return cases


def _frame_png(bundle: Path, pass_rec, frame: int, tmp: Path) -> Path:
    p = bundle / pass_rec.frames_dir / f"f_{frame:03d}.png"
    if p.exists():
        return p
    tmp.mkdir(parents=True, exist_ok=True)
    out = tmp / f"{pass_rec.index}_{frame:03d}.png"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(bundle / pass_rec.clip_path), "-vf", f"select=eq(n\\,{frame})",
                    "-vframes", "1", str(out)], check=True)
    return out


VLM_PROMPT = ("You are checking whether a game action succeeded. Objective: {objective}\n"
              "Here is ONE screenshot taken after the agent's action (the agent's tool reported success). Based only on this "
              "image, was the objective met? First line: exactly one of PASS, FAIL, UNSURE. Second line: one sentence of reasoning.")


def vlm_baseline(client: MetaClient, bundle: Path, m, tmp: Path) -> list[dict]:
    rows = []
    checks = [(m.passes[0], 40, "mid-approach frame of the open-loop pass"), (m.passes[0], 79, "final frame of the open-loop pass"),
              (m.passes[-1], 79, "final frame of the repaired pass")]
    for rec, frame, why in checks:
        png = _frame_png(bundle, rec, frame, tmp)
        img = base64.b64encode(png.read_bytes()).decode()
        resp = client.muse(SPARK, [{"role": "user", "content": [
            {"type": "input_text", "text": VLM_PROMPT.format(objective=S.OBJECTIVE)},
            {"type": "input_image", "image_url": f"data:image/png;base64,{img}"}]}],
            reasoning_effort="medium", max_output_tokens=3000, purpose="baseline_vlm_screenshot")
        text = client.output_text(resp).strip()
        first = text.splitlines()[0].strip().upper() if text else ""
        answer = next((k for k in ("PASS", "FAIL", "UNSURE") if k in first), "UNPARSED")
        truth = rec.verification_status  # the verifier's verdict for that pass, as the reference
        rows.append({"pass_index": rec.index, "frame": frame, "why": why, "vlm_answer": answer, "vlm_text": text[:600],
                     "verifier_verdict_for_pass": truth, "agrees_with_verifier": answer == truth,
                     "request_id": resp.get("_request_id"), "response_id": resp.get("id")})
    return rows


def coverage_honesty(client: MetaClient, bundle: Path, m) -> dict:
    """Perturb the contract (manually, documented) so the mover concept is one SAM cannot find in this scene.
    The verifier must answer INCONCLUSIVE, never PASS."""
    contract = SensoryContract.model_validate_json((bundle / m.contract_path).read_text())
    variant = contract.model_copy(update={"contract_id": contract.contract_id + "-perturbed-mover", "mover_concept": "robot",
                                          "compiled_by": {"note": "MANUAL PERTURBATION for the coverage-honesty check; not Muse-compiled"},
                                          "frozen_sha256": None}).freeze()
    clip = bundle / m.passes[0].clip_path
    mov = client.sam_track_video(clip, variant.mover_concept)
    bar = client.sam_track_video(clip, variant.barrier_concept)
    tm = vt.build_track(variant.mover_concept, vt.parse_sam_text(mov.raw_text), variant.frame_count, tuple(variant.frame_size))
    tb = vt.build_track(variant.barrier_concept, vt.parse_sam_text(bar.raw_text), variant.frame_count, tuple(variant.frame_size))
    r = verify(variant, tm, tb)
    return {"perturbation": "mover_concept 'capsule' -> 'robot' (a phrase SAM 3.1 does not match in this scene)",
            "clip": m.passes[0].clip_path, "mover_frames_tracked": len(tm.points), "barrier_frames_tracked": len(tb.points),
            "verdict": r.status.value, "reasons": r.reasons, "expected": "INCONCLUSIVE or ERROR (never PASS)",
            "honest": r.status.value in ("INCONCLUSIVE", "ERROR"),
            "sam_request_ids": [mov.request_id, bar.request_id], "sam_cached": [mov.cached, bar.cached]}


def write_report(summary: dict) -> None:
    c = summary["cases"]
    L = ["# Evaluation report — KINETIC-ORACLE (ProprioSAM)", "",
         f"Generated {summary['generated_at']} from bundles under `runs/`. Every verdict below is the frozen verifier's "
         "decision over SAM 3.1 tracks; MCP tool status and model text are recorded but never consulted. Hidden engine "
         "ground truth exists in each bundle (`truth_hidden.json`) for evaluation only and was never shown to any model.", "",
         "## Case 1 — defective scene, full closed loop (independent trials)", "",
         "| run | pass 1 | repair | final | baseline unchanged | cost | wall time |", "|---|---|---|---|---|---|---|"]
    for r in c["case1_defective_scene_closed_loop"]:
        rep = "; ".join(f"T{t['turn']} {t['model']} {t['tool_calls']} calls → {t['patches']} patch" for t in r["repair_turns"]) or "none"
        L.append(f"| `{r['run_id']}` | {r['pass1']['status']} @ {r['pass1']['t_fail']} (max E {r['pass1']['max_E_px']:+.0f} px) | {rep} | "
                 f"**{r['final_verdict']}** (pass {r['final']['pass_index']}, max E {r['final']['max_E_px']:+.0f} px) | {r['baseline_unchanged']} | ${r['est_cost_usd']:.3f} | {r['duration_s']} s |")
    n1 = len(c["case1_defective_scene_closed_loop"])
    ok1 = sum(1 for r in c["case1_defective_scene_closed_loop"] if r["final_verdict"] == "PASS" and r["pass1"]["status"] == "FAIL")
    L += ["", f"FAIL→PASS in **{ok1}/{n1}** trials. Banned-term screen found nothing in any outgoing Muse prompt: "
              f"{all(not t['banned_terms_found'] for r in c['case1_defective_scene_closed_loop'] for t in r['repair_turns'])}.", "",
          "## Case 2 — known-good scene (true-negative check)", "",
          "| run | pass 1 | repair turns | final |", "|---|---|---|---|"]
    for r in c["case2_known_good_true_negative"]:
        L.append(f"| `{r['run_id']}` | {r['pass1']['status']} (max E {r['pass1']['max_E_px']:+.0f} px, window coverage {r['pass1']['coverage_window']}) | {len(r['repair_turns'])} | **{r['final_verdict']}** |")
    L += ["", "## Case 3 — perturbations", "", "### 3a. Different wrong layer (hurdle declared on layer 4)", "",
          "| run | pass 1 | repair | final |", "|---|---|---|---|"]
    for r in c["case3_perturbed_defect"]:
        rep = "; ".join(f"T{t['turn']} {t['model']} {t['tool_calls']} calls → {t['patch']}" for t in r["repair_turns"]) or "none"
        L.append(f"| `{r['run_id']}` | {r['pass1']['status']} @ {r['pass1']['t_fail']} | {rep} | **{r['final_verdict']}** |")
    ch = summary.get("coverage_honesty")
    if ch:
        L += ["", "### 3b. Coverage honesty (manual contract perturbation)", "",
              f"{ch['perturbation']}: mover tracked in {ch['mover_frames_tracked']} frames, barrier in {ch['barrier_frames_tracked']} → "
              f"verifier **{ch['verdict']}** ({'; '.join(ch['reasons'])}). Expected {ch['expected']}: honest = {ch['honest']}."]
    L += ["", "## Ablation — why temporal SAM 3.1 tracking matters", "",
          "Reference bundle: `" + summary["reference_bundle"] + "`.", "",
          "| method | what it looks at | verdict on the defective scene | correct? |", "|---|---|---|---|"]
    ol = summary["open_loop_trust"]
    L.append(f"| (a) Open-loop tool trust | the MCP result of the walk action: `{ol['mcp_result']}` | {ol['implied_verdict']} | {ol['correct']} |")
    for v in summary.get("vlm_screenshot_baseline", []):
        L.append(f"| (b) Static screenshot VLM ({SPARK}) | {v['why']} (frame {v['frame']}) | {v['vlm_answer']} — “{v['vlm_text'].splitlines()[-1][:140] if v['vlm_text'] else ''}” | "
                 f"{'yes' if v['agrees_with_verifier'] else 'no'} (verifier says {v['verifier_verdict_for_pass']}) |")
    ko = summary["kinetic_oracle"]
    L.append(f"| (c) KINETIC-ORACLE | 80-frame SAM 3.1 tracks + frozen residual | FAIL at frame {ko['t_fail']} → repaired → {ko['final']} | yes |")
    L += ["", "## Limitations (stated plainly)", "",
          "- One scene, one defect family (collision layer/mask mismatch) and one perturbation of it; n is small.",
          "- The residual rule is specific to a chase camera: it measures the barrier's bottom edge against the player's feet. Other camera rigs need other invariants from the same frozen library pattern.",
          "- SAM concept phrases are scene-calibrated (`capsule`, `yellow bar`); other phrasings return nothing, which the verifier reports as INCONCLUSIVE rather than guessing.",
          "- The repaired-scene margin is small (≈13 px) relative to box jitter (≈4 px).",
          "- Muse's diagnosis prompt is blind by construction (screened and hashed per turn), but the scene's source documents the normal layer convention, which a competent reader uses — as a human engineer would.",
          "- The Godot MCP server and fixtures pre-date the hackathon and are disclosed as supporting infrastructure (see `docs/ARCHITECTURE_PROVENANCE.md`)."]
    REPORT.write_text("\n".join(L) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-live", action="store_true", help="only aggregate bundles; no API calls")
    ap.add_argument("--reference", default=None, help="run_id of the bundle used for the ablation baselines")
    a = ap.parse_args()
    cases = collect()
    trials = [r for r in cases["case1_defective_scene_closed_loop"] if r["final_verdict"] == "PASS"]
    if not trials:
        print("no successful closed-loop trial found"); return 1
    ref_id = a.reference or trials[0]["run_id"]
    bundle = RUNS_DIR / ref_id
    m = load_manifest(bundle)
    summary = {"generated_at": utc_now(), "cases": cases, "reference_bundle": ref_id,
               "open_loop_trust": {"mcp_result": json.dumps(m.passes[0].open_loop.get("result")), "mcp_is_error": m.passes[0].open_loop.get("mcp_is_error"),
                                   "implied_verdict": "PASS (no error returned)", "correct": "no" if m.passes[0].verification_status == "FAIL" else "n/a"},
               "kinetic_oracle": {"t_fail": m.passes[0].t_fail, "final": m.final_verdict, "turns": len(m.repair_turns)}}
    if not a.skip_live:
        eval_dir = RUNS_DIR / new_run_id("eval")
        client = MetaClient(eval_dir, budget_usd=3.0)
        summary["vlm_screenshot_baseline"] = vlm_baseline(client, bundle, m, eval_dir / "frames")
        summary["coverage_honesty"] = coverage_honesty(client, bundle, m)
        summary["live_spend"] = client.spend_summary()
        summary["live_log_dir"] = str(eval_dir.relative_to(RUNS_DIR.parent))
    write_json(RUNS_DIR / "evaluation_summary.json", summary)
    write_report(summary)
    print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in cases.items()}))
    for v in summary.get("vlm_screenshot_baseline", []):
        print(f"VLM frame {v['frame']} pass{v['pass_index']}: {v['vlm_answer']} (verifier {v['verifier_verdict_for_pass']}) {v['request_id']}")
    if summary.get("coverage_honesty"):
        print("coverage honesty:", summary["coverage_honesty"]["verdict"], "honest =", summary["coverage_honesty"]["honest"])
    print("wrote", RUNS_DIR / "evaluation_summary.json", "and", REPORT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
