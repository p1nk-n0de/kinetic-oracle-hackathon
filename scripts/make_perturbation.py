"""Create an honest perturbation baseline for the evaluation: a copy of the
hurdle scene whose Hurdle is declared on collision layer 4 instead of 2 (a
different wrong layer, same symptom). Written to runs/_baselines/ (gitignored);
reproducible from this script. The copy is a *baseline* for a closed-loop run;
the original fixture is only read."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from propriosam.artifacts import RUNS_DIR, tree_sha256
from scenarios.godot_hurdle import scenario as S

NAME = sys.argv[1] if len(sys.argv) > 1 else "hurdle_layer4"
FIND = '"kind": "hurdle", "layer": 2}'
REPLACE = '"kind": "hurdle", "layer": 4}'

dst = RUNS_DIR / "_baselines" / NAME
if dst.exists():
    shutil.rmtree(dst)
shutil.copytree(S.DEFECT_BASELINE, dst)
f = dst / "scripts/arena_layout.gd"
src = f.read_text()
assert src.count(FIND) == 1, "expected exactly one Hurdle entry to perturb"
f.write_text(src.replace(FIND, REPLACE))
print(f"perturbation baseline: {dst}  tree_sha256={tree_sha256(dst)[0]}  edit: {FIND!r} -> {REPLACE!r}")
