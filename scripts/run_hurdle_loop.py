"""Run the live closed loop on a fresh copy of the Godot hurdle scene.

  source scripts/env.sh && .venv/bin/python -m scripts.run_hurdle_loop            # defective baseline, up to 3 repair turns
  .venv/bin/python -m scripts.run_hurdle_loop --known-good --max-turns 0          # true-negative check
Exit code: 0 PASS, 2 FAIL/INCONCLUSIVE, 1 ERROR."""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from propriosam.artifacts import load_manifest
from propriosam.meta_client import SPARK, WONDER
from propriosam.repair_orchestrator import run_closed_loop
from scenarios.godot_hurdle import scenario as S


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", default=None, help="Godot project to copy (default: the hurdle scene under test)")
    ap.add_argument("--known-good", action="store_true", help="use the known-good scene instead")
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--max-turns", type=int, default=3)
    ap.add_argument("--model", default=SPARK)
    ap.add_argument("--escalation", default=WONDER, help="model for turns >= 2, or 'none'")
    ap.add_argument("--budget-usd", type=float, default=40.0)
    ap.add_argument("--capture-timeout", type=float, default=30.0)
    ap.add_argument("--no-contract-cache", action="store_true")
    ap.add_argument("--label", default="")
    a = ap.parse_args()
    baseline = Path(a.baseline) if a.baseline else (S.KNOWN_GOOD_BASELINE if a.known_good else S.DEFECT_BASELINE)
    run_dir = asyncio.run(run_closed_loop(
        baseline=baseline, scenario=S, run_id=a.run_id, max_repair_turns=a.max_turns, model=a.model,
        escalation_model=None if a.escalation == "none" else a.escalation, budget_usd=a.budget_usd,
        capture_timeout_s=a.capture_timeout, use_contract_cache=not a.no_contract_cache, label=a.label))
    m = load_manifest(run_dir)
    print(f"bundle: {run_dir}")
    if m.status != "COMPLETE":
        return 1
    return 0 if m.final_verdict == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
