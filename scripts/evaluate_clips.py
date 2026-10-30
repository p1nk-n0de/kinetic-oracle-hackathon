"""Evaluate pre-captured clips through the real sensory pipeline (Muse-compiled
contract -> SAM 3.1 -> frozen verifier -> overlays) and write a run bundle of
kind `clip_evaluation`. No Godot and no repair: this exercises the measurement
half end to end and gives the dashboard real data before the closed loop runs.

  MODEL_API_KEY=... .venv/bin/python -m scripts.evaluate_clips \
      --clip docs/prior_evidence/2026-10-30/clips/defect.mp4:before_repair \
      --clip docs/prior_evidence/2026-10-30/clips/repaired.mp4:after_repair"""
from __future__ import annotations

import argparse
import platform
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from propriosam import __version__
from propriosam.artifacts import RUNS_DIR, RunManifest, new_run_id, save_manifest, write_json
from propriosam.evaluation import track_and_verify
from propriosam.meta_client import SAM_MODEL, SPARK, MetaClient, utc_now
from propriosam.sensory_contract import compile_contract
from propriosam.verifier import rule_sha256
from scenarios.godot_hurdle import scenario as S


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clip", action="append", required=True, help="path.mp4:label (frames dir = path without .mp4)")
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--budget-usd", type=float, default=5.0)
    a = ap.parse_args()
    run_id = a.run_id or new_run_id("cliprun")
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    client = MetaClient(run_dir, budget_usd=a.budget_usd)
    m = RunManifest(run_id=run_id, kind="clip_evaluation", created_at=utc_now(),
                    models={"contract": SPARK, "sam": SAM_MODEL},
                    environment={"propriosam": __version__, "python": platform.python_version(), "host": platform.platform()},
                    notes=["Clips were captured earlier by the same tick-locked Godot recipe; this run re-tracks and "
                           "re-verifies them live. truth_hidden.json is ground truth for evaluation only and is never "
                           "shown to any model."])
    try:
        contract = compile_contract(client, objective=S.OBJECTIVE, scene_brief=S.SCENE_BRIEF, vocabulary=S.CONCEPT_VOCABULARY,
                                    frame_count=S.FRAME_COUNT, fps=S.FPS, frame_size=S.FRAME_SIZE)
        write_json(run_dir / "contract.json", contract)
        m.contract_path, m.contract_sha256, m.rule_sha256 = "contract.json", contract.frozen_sha256, rule_sha256()
        print(f"contract {contract.contract_id}: mover='{contract.mover_concept}' barrier='{contract.barrier_concept}' "
              f"thr={contract.rule.threshold_px}px persist={contract.rule.persistence_frames} window={contract.coverage.critical_window} "
              f"| {contract.statement}")
        for i, spec in enumerate(a.clip, start=1):
            path, _, label = spec.partition(":")
            clip = Path(path)
            frames = clip.with_suffix("")
            truth = frames / "truth.json"
            rec, res, _ = track_and_verify(client, run_dir / f"pass{i}", index=i, label=label or clip.stem, clip_mp4=clip,
                                           frames_dir=frames, contract=contract, truth_hidden=truth if truth.exists() else None,
                                           overlay_title=f"{label or clip.stem} — SAM 3.1 tracks under contract {contract.contract_id}")
            m.passes.append(rec)
            print(f"pass{i} {rec.label}: {res.status.value} t_fail={res.t_fail} max_E={res.max_residual} coverage={res.coverage['both_window']:.2f} "
                  f"sam_ids={[v['request_id'] for v in rec.sam.values()]} overlay masks={rec.overlay_info.get('masks_drawn')}")
        m.status = "COMPLETE"
        m.final_verdict = " / ".join(f"{p.label}={p.verification_status}" for p in m.passes)
    except Exception as e:  # keep the partial bundle, record the failure honestly
        m.status, m.final_verdict = "ERROR", f"{type(e).__name__}: {e}"
        print("ERROR:", e)
    m.spend = client.spend_summary()
    m.request_ids = m.spend.pop("request_ids", [])
    m.finished_at = utc_now()
    save_manifest(run_dir, m)
    print(f"bundle: {run_dir}  status={m.status}  est_cost=${m.spend['est_cost_usd']:.4f}")
    return 0 if m.status == "COMPLETE" else 1


if __name__ == "__main__":
    sys.exit(main())
