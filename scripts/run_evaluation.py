"""Honest multi-case evaluation and ablation baselines.

Reads the closed-loop bundles on disk, runs two cheap live checks (the
static-screenshot VLM baseline and a coverage-honesty perturbation of the
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
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from propriosam import vision_tracker as vt
from propriosam.artifacts import RUNS_DIR, load_manifest, new_run_id, write_json
from propriosam.meta_client import SPARK, MetaClient, utc_now
from propriosam.sensory_contract import SensoryContract
from propriosam.verifier import rule_sha256, verify
from scenarios.godot_hurdle import scenario as S

REPORT = Path(__file__).resolve().parents[1] / "docs" / "EVALUATION_REPORT.md"
VLM_REPEATS = 3
HURDLE_CENTRE_Z, REACHED_Z = -12.0, -11.0  # engine coordinates, used only by the hidden-truth audit
CASE_ORDER = ("case1", "case2a", "case2b", "case2c", "case3a", "case3b", "case3c", "case3d", "case3e", "case3f")
CASE_TITLES = {
    "case1": "Case 1: defective scene, full closed loop (independent trials)",
    "case2a": "Case 2a: known-good twin of the capsule scene (true negative)",
    "case2b": "Case 2b: real robot build under a robot contract (generalisation, true negative)",
    "case2c": "Case 2c: real robot build under the capsule contract (sensing honesty)",
    "case3a": "Case 3a: a different wrong layer",
    "case3b": "Case 3b: a different root cause (collision shape disabled in the builder)",
    "case3c": "Case 3c: two simultaneous faults",
    "case3d": "Case 3d: three faults in three files, two patches per turn",
    "case3e": "Case 3e: the real robot build with the hurdle on the wrong layer",
    "case3f": "Case 3f: the same three faults, bounded to one patch per turn, so one turn cannot be enough",
}


def _dur(m) -> float | None:
    try:
        return round((datetime.fromisoformat(m.finished_at) - datetime.fromisoformat(m.created_at)).total_seconds(), 1)
    except Exception:
        return None


def _e(v) -> str:
    return "n/a" if v is None else f"{v:+.0f} px"


def truth_audit(d: Path, m) -> list[dict]:
    """Compare each verdict with what the engine says happened. Evaluation only: the verifier never reads this."""
    rows = []
    for p in m.passes:
        z = [r["player"]["global_position"]["z"] for r in json.loads((d / p.truth_hidden_path).read_text())["rows"]]
        crossed, reached = min(z) < HURDLE_CENTRE_Z, min(z) <= REACHED_Z
        implied = "FAIL" if crossed else ("PASS" if reached else "INCONCLUSIVE")
        v = p.verification_status
        outcome = "match" if v == implied else ("abstained" if v == "INCONCLUSIVE" else "WRONG")
        rows.append({"pass": p.index, "verifier": v, "engine_final_z": round(z[-1], 2), "engine_min_z": round(min(z), 2),
                     "engine_crossed_hurdle": crossed, "engine_reached_hurdle": reached, "engine_implied_verdict": implied, "outcome": outcome})
    return rows


def _trial_row(d: Path, m) -> dict:
    p1, pl = m.passes[0], m.passes[-1]
    v1 = json.loads((d / p1.verification_path).read_text())
    return {"run_id": m.run_id, "label": (m.notes or [""])[0], "status": m.status, "baseline": m.baseline.get("path"),
            "contract_id": (json.loads((d / m.contract_path).read_text())["contract_id"]),
            "mover_concept": json.loads((d / m.contract_path).read_text())["mover_concept"],
            "pass1": {"status": p1.verification_status, "t_fail": p1.t_fail, "max_E_px": p1.max_residual,
                      "coverage_window": v1["coverage"].get("both_window"), "reasons": v1["reasons"]},
            "passes": [{"index": p.index, "status": p.verification_status, "t_fail": p.t_fail, "max_E_px": p.max_residual} for p in m.passes],
            "repair_turns": [{"turn": t.turn, "model": t.model, "tool_calls": t.tool_calls, "patches": len(t.patches),
                              "patch_paths": [p["path"] for p in t.patches], "reasons": [p.get("reason", "") for p in t.patches],
                              "banned_terms_found": t.anti_cheat.get("banned_terms_found"), "est_cost_usd": t.est_cost_usd}
                             for t in m.repair_turns],
            "final": {"status": pl.verification_status, "t_fail": pl.t_fail, "max_E_px": pl.max_residual, "pass_index": pl.index},
            "truth_audit": truth_audit(d, m), "final_verdict": m.final_verdict, "baseline_unchanged": m.baseline.get("unchanged"),
            "copy_matched_baseline_at_stage": m.workspace.get("baseline_match_at_stage"),
            "request_ids": len(m.request_ids), "est_cost_usd": m.spend.get("est_cost_usd"), "duration_s": _dur(m)}


def collect() -> tuple[dict, list[str]]:
    cases: dict[str, list] = {c: [] for c in CASE_ORDER}
    skipped = []
    current_rule = rule_sha256()
    for d in sorted(RUNS_DIR.glob("run_*")):
        if not (d / "run_manifest.json").exists():
            continue
        m = load_manifest(d)
        if m.kind != "closed_loop" or not m.passes:
            continue
        if m.rule_sha256 != current_rule:
            skipped.append(f"{m.run_id}: rule hash differs from the current verifier")
            continue
        label = (m.notes or [""])[0]
        key = label.split(":")[0].split(" ")[0]
        if key in cases:
            cases[key].append(_trial_row(d, m))
        else:
            skipped.append(f"{m.run_id}: unlabelled ({label!r})")
    return cases, skipped


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
    checks = [(m.passes[0], 40, "early frame, defective scene"), (m.passes[0], 79, "last frame, defective scene"),
              (m.passes[-1], 40, "early frame, repaired scene"), (m.passes[-1], 79, "last frame, repaired scene")]
    for rec, frame, why in checks:
        png = _frame_png(bundle, rec, frame, tmp)
        img = base64.b64encode(png.read_bytes()).decode()
        answers, texts, ids = [], [], []
        for _ in range(VLM_REPEATS):
            resp = client.muse(SPARK, [{"role": "user", "content": [
                {"type": "input_text", "text": VLM_PROMPT.format(objective=S.OBJECTIVE)},
                {"type": "input_image", "image_url": f"data:image/png;base64,{img}"}]}],
                reasoning_effort="medium", max_output_tokens=3000, purpose="baseline_vlm_screenshot")
            text = client.output_text(resp).strip()
            first = text.splitlines()[0].strip().upper() if text else ""
            answers.append(next((k for k in ("PASS", "FAIL", "UNSURE") if k in first), "UNPARSED"))
            texts.append(text[:400]); ids.append(resp.get("_request_id"))
        reference = rec.verification_status
        rows.append({"pass_index": rec.index, "frame": frame, "why": why, "answers": dict(Counter(answers)),
                     "correct": answers.count(reference), "repeats": VLM_REPEATS, "reference_verdict_for_pass": reference,
                     "sample_text": texts[0], "request_ids": ids})
    return rows


def coverage_honesty(client: MetaClient, bundle: Path, m) -> dict:
    """Perturb the contract by hand so the mover is a phrase SAM cannot find in this scene.
    The verifier must answer INCONCLUSIVE, never PASS."""
    contract = SensoryContract.model_validate_json((bundle / m.contract_path).read_text())
    variant = contract.model_copy(update={"contract_id": contract.contract_id + "-perturbed-mover", "mover_concept": "blue capsule",
                                          "compiled_by": {"note": "MANUAL PERTURBATION for the coverage-honesty check; not Muse-compiled"},
                                          "frozen_sha256": None}).freeze()
    clip = bundle / m.passes[0].clip_path
    mov = client.sam_track_video(clip, variant.mover_concept)
    bar = client.sam_track_video(clip, variant.barrier_concept)
    tm = vt.build_track(variant.mover_concept, vt.parse_sam_text(mov.raw_text), variant.frame_count, tuple(variant.frame_size))
    tb = vt.build_track(variant.barrier_concept, vt.parse_sam_text(bar.raw_text), variant.frame_count, tuple(variant.frame_size))
    r = verify(variant, tm, tb)
    return {"perturbation": "mover_concept 'capsule' -> 'blue capsule' (a phrase SAM 3.1 returns nothing for in this scene)",
            "clip": m.passes[0].clip_path, "mover_frames_tracked": len(tm.points), "barrier_frames_tracked": len(tb.points),
            "verdict": r.status.value, "reasons": r.reasons, "expected": "INCONCLUSIVE (never PASS)",
            "honest": r.status.value == "INCONCLUSIVE", "sam_request_ids": [mov.request_id, bar.request_id], "sam_cached": [mov.cached, bar.cached]}


def write_report(summary: dict) -> None:
    c = summary["cases"]
    L = ["# Evaluation report: KINETIC-ORACLE (ProprioSAM)", "",
         f"Generated {summary['generated_at']} from the bundles under `runs/`, all produced by the same verifier "
         f"(rule hash `{summary['rule_sha256'][:12]}`). Every verdict below is the frozen verifier's decision over SAM 3.1 tracks. "
         "MCP tool status and model text are recorded but never consulted. Engine ground truth exists in each bundle "
         "(`truth_hidden.json`) for evaluation only and was never shown to any model.", ""]
    for key in CASE_ORDER:
        rows = c.get(key) or []
        L += [f"## {CASE_TITLES[key]}", ""]
        if not rows:
            L += ["No bundle recorded.", ""]
            continue
        L += ["| run | passes | repair turns | final verdict | baseline unchanged | cost | wall time |", "|---|---|---|---|---|---|---|"]
        for r in rows:
            passes = " → ".join(f"{p['status']}" + (f"@{p['t_fail']}" if p["t_fail"] is not None else "") + f" (max E {_e(p['max_E_px'])})" for p in r["passes"])
            rep = "; ".join(f"T{t['turn']} {t['model']}: {t['tool_calls']} calls, {t['patches']} patch" + (f" in {', '.join(sorted(set(t['patch_paths'])))}" if t["patch_paths"] else "") for t in r["repair_turns"]) or "none"
            L.append(f"| `{r['run_id']}` | {passes} | {rep} | **{r['final_verdict']}** | {r['baseline_unchanged']} | ${r['est_cost_usd']:.3f} | {r['duration_s']} s |")
        L.append("")
        for r in rows:
            for t in r["repair_turns"]:
                for why in t["reasons"]:
                    L.append(f"- `{r['run_id'][-6:]}` T{t['turn']} ({t['model']}) stated reason: {why[:220]}")
        if key in ("case2c",):
            L.append("")
            L.append("The contract's concept does not exist in this build, so SAM 3.1 returned no track. Verifier reasons: " + "; ".join(rows[0]["pass1"]["reasons"]) + ". No repair was attempted on a sensing failure.")
        L.append("")
    audit = [(r["run_id"], key, a) for key in CASE_ORDER for r in (c.get(key) or []) for a in r["truth_audit"]]
    tally = Counter(a["outcome"] for _, _, a in audit)
    L += ["## Hidden-truth audit", "",
          "After the runs, each verdict is compared with the engine's own record of where the player went. The verifier and "
          "Muse never see this data. A verdict is a match if it agrees with the engine, abstained if the verifier said "
          "INCONCLUSIVE, and WRONG if it said PASS or FAIL against the engine.", "",
          f"**{tally.get('match', 0)} match, {tally.get('abstained', 0)} abstained, {tally.get('WRONG', 0)} wrong** over {len(audit)} passes.", "",
          "| case | run | pass | verifier | engine: furthest z, crossed hurdle | outcome |", "|---|---|---|---|---|---|"]
    for run_id, key, a in audit:
        L.append(f"| {key} | `{run_id[-6:]}` | {a['pass']} | {a['verifier']} | {a['engine_min_z']}, {a['engine_crossed_hurdle']} | {a['outcome']} |")
    L += ["", "### The vacuous pass this audit caught", "",
          "An earlier run on the robot build returned PASS. The audit showed the robot had stopped at z = -7.13, about 4.3 m short "
          "of the hurdle at frame 38 of 80. The held forward input was lost mid-walk, and no tool reported an error: exactly the "
          "failure class this project exists to expose, and it happened to our own harness. The rule 'must not cross' was true "
          "only because the robot never got there.", "",
          "Two fixes followed. The verifier gained an approach gate: a PASS now requires the mover to come within one body height "
          "of the barrier, otherwise the contract was not exercised and the verdict is INCONCLUSIVE. The capture recipe now "
          "re-asserts the held input every step. That run's real SAM output is kept as a regression test "
          "(`tests/fixtures/dropped_input_walk`, `test_real_dropped_input_run_no_longer_passes`). All bundles in this report were "
          "regenerated after the fix.", ""]
    ch = summary.get("coverage_honesty")
    if ch:
        L += ["## Coverage honesty (manual contract perturbation)", "",
              f"{ch['perturbation']}: mover tracked in {ch['mover_frames_tracked']} frames, barrier in {ch['barrier_frames_tracked']}. "
              f"Verifier: **{ch['verdict']}** ({'; '.join(ch['reasons'])}). Expected {ch['expected']}.", ""]
    L += ["## Ablation: why temporal SAM 3.1 tracking matters", "", f"Reference bundle: `{summary['reference_bundle']}`.", "",
          "| method | what it looks at | answer | matches the verifier? |", "|---|---|---|---|"]
    ol = summary["open_loop_trust"]
    L.append(f"| (a) Open-loop tool trust | the MCP result of the walk action on the defective scene: `{ol['mcp_result'][:80]}` | {ol['implied_verdict']} | {ol['correct']} |")
    for v in summary.get("vlm_screenshot_baseline", []):
        L.append(f"| (b) Static screenshot VLM ({SPARK}) | {v['why']} (frame {v['frame']}) | {v['answers']} over {v['repeats']} calls | {v['correct']}/{v['repeats']} (verifier: {v['reference_verdict_for_pass']}) |")
    ko = summary["kinetic_oracle"]
    L.append(f"| (c) KINETIC-ORACLE | 80-frame SAM 3.1 tracks + frozen residual | FAIL at frame {ko['t_fail']}, repaired, then {ko['final']} | the verifier itself |")
    L += ["", "## Limitations", "",
          "- One scene family and one defect family (the hurdle fails to collide), with a few variations. n is small: this shows the mechanism, not a rate.",
          "- The residual is specific to this chase camera: it compares the barrier's bottom edge with the player's feet. Other camera rigs need other invariants.",
          "- SAM concept phrases are scene-calibrated. `capsule` works and `blue capsule` returns nothing. The verifier reports that as INCONCLUSIVE and never guesses.",
          "- On the capsule scene the repaired margin is small (about 12 to 13 px) compared with box jitter (about 4 px).",
          "- The approach gate is a screen-space heuristic (one body height), not a measured distance.",
          "- Muse's prompts are blind by construction (screened and hashed per turn), but the scene source documents the normal layer convention, which a competent reader uses, as a human engineer would.",
          "- The Godot MCP server and the test scenes predate the hackathon and are disclosed as supporting infrastructure (`docs/ARCHITECTURE_PROVENANCE.md`)."]
    if summary.get("skipped"):
        L += ["", "Bundles excluded from this report: " + "; ".join(summary["skipped"])]
    REPORT.write_text("\n".join(L) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-live", action="store_true", help="only aggregate bundles; no API calls")
    ap.add_argument("--reference", default=None, help="run_id of the bundle used for the ablation baselines")
    a = ap.parse_args()
    cases, skipped = collect()
    trials = [r for r in cases["case1"] if r["final_verdict"] == "PASS"]
    if not trials:
        print("no successful closed-loop trial found"); return 1
    ref_id = a.reference or trials[0]["run_id"]
    bundle = RUNS_DIR / ref_id
    m = load_manifest(bundle)
    prior_path = RUNS_DIR / "evaluation_summary.json"
    summary = {"generated_at": utc_now(), "rule_sha256": rule_sha256(), "cases": cases, "skipped": skipped, "reference_bundle": ref_id,
               "open_loop_trust": {"mcp_result": json.dumps(m.passes[0].open_loop.get("result")), "mcp_is_error": m.passes[0].open_loop.get("mcp_is_error"),
                                   "implied_verdict": "PASS (the tool reported no error)", "correct": "no" if m.passes[0].verification_status == "FAIL" else "n/a"},
               "kinetic_oracle": {"t_fail": m.passes[0].t_fail, "final": m.final_verdict, "turns": len(m.repair_turns)}}
    if not a.skip_live:
        eval_dir = RUNS_DIR / new_run_id("eval")
        client = MetaClient(eval_dir, budget_usd=3.0)
        summary["vlm_screenshot_baseline"] = vlm_baseline(client, bundle, m, eval_dir / "frames")
        summary["coverage_honesty"] = coverage_honesty(client, bundle, m)
        summary["live_spend"] = {k: v for k, v in client.spend_summary().items() if k != "request_ids"}
        summary["live_log_dir"] = eval_dir.name
    elif prior_path.exists():
        prior = json.loads(prior_path.read_text())
        for k in ("vlm_screenshot_baseline", "coverage_honesty", "live_spend", "live_log_dir"):
            if k in prior:
                summary[k] = prior[k]
    write_json(prior_path, summary)
    write_report(summary)
    print({k: len(v) for k, v in cases.items()}, "skipped:", len(skipped))
    for v in summary.get("vlm_screenshot_baseline", []):
        print(f"VLM {v['why']}: {v['answers']} (verifier {v['reference_verdict_for_pass']})")
    if summary.get("coverage_honesty"):
        print("coverage honesty:", summary["coverage_honesty"]["verdict"], "honest =", summary["coverage_honesty"]["honest"])
    print("wrote", prior_path, "and", REPORT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
