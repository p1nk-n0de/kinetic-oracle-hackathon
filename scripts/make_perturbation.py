"""Build the evaluation's scene variants from the hurdle fixture, by script, into
runs/_baselines/<name>/ (gitignored; reproducible from here). The original fixture
is only read. Each variant is a *baseline* for a closed-loop run.

  known_good_capsule     same scene, hurdle on the default world layer (true-negative twin)
  hurdle_layer4          a different wrong layer: same symptom, different value
  hurdle_shape_disabled  different root cause: right layer, collision shape disabled in the builder
  hurdle_two_faults      both faults at once: wrong layer AND disabled shape"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from propriosam.artifacts import RUNS_DIR, tree_sha256
from scenarios.godot_hurdle import scenario as S

LAYOUT, BUILDER = "scripts/arena_layout.gd", "scripts/arena_builder.gd"
LAYER2 = '"kind": "hurdle", "layer": 2}'
NO_LAYER = '"kind": "hurdle"}'
LAYER4 = '"kind": "hurdle", "layer": 4}'
SHAPE = "\tshape.shape = bs\n"
SHAPE_OFF = SHAPE + '\tshape.disabled = kind == "hurdle"\n'

VARIANTS = {
    "known_good_capsule": [(LAYOUT, LAYER2, NO_LAYER)],
    "hurdle_layer4": [(LAYOUT, LAYER2, LAYER4)],
    "hurdle_shape_disabled": [(LAYOUT, LAYER2, NO_LAYER), (BUILDER, SHAPE, SHAPE_OFF)],
    "hurdle_two_faults": [(BUILDER, SHAPE, SHAPE_OFF)],
}


def build(name: str) -> Path:
    dst = RUNS_DIR / "_baselines" / name
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(S.DEFECT_BASELINE, dst)
    for rel, find, repl in VARIANTS[name]:
        f = dst / rel
        src = f.read_text()
        assert src.count(find) == 1, f"{name}: expected exactly one match of {find!r} in {rel}"
        f.write_text(src.replace(find, repl))
    print(f"{name}: tree_sha256={tree_sha256(dst)[0][:16]}  edits={len(VARIANTS[name])}")
    return dst


if __name__ == "__main__":
    for n in (sys.argv[1:] or VARIANTS):
        build(n)
