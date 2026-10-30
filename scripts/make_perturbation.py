"""Build the evaluation's scene variants from the hurdle fixture, by script, into
runs/_baselines/<name>/ (gitignored; reproducible from here). The original fixture
is only read. Each variant is a *baseline* for a closed-loop run.

  known_good_capsule     same scene, hurdle on the default world layer (true-negative twin)
  hurdle_layer4          a different wrong layer: same symptom, different value
  hurdle_shape_disabled  different root cause: right layer, collision shape disabled in the builder
  hurdle_two_faults      both faults at once: wrong layer AND disabled shape
  hurdle_collision_exception  a third root cause, in the player script
  hurdle_three_faults    all three, in three files: more than one bounded repair turn can fix
  robot_hurdle_layer2    the real robot build with the hurdle on the wrong layer"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from propriosam.artifacts import RUNS_DIR, tree_sha256
from scenarios.godot_hurdle import scenario as S

LAYOUT, BUILDER, PLAYER = "scripts/arena_layout.gd", "scripts/arena_builder.gd", "scripts/player.gd"
LAYER2 = '"kind": "hurdle", "layer": 2}'
NO_LAYER = '"kind": "hurdle"}'
LAYER4 = '"kind": "hurdle", "layer": 4}'
SHAPE = "\tshape.shape = bs\n"
SHAPE_OFF = SHAPE + '\tshape.disabled = kind == "hurdle"\n'
RESET = "\tfacing_yaw_deg = 0.0\n\tvisual.rotation.y = 0.0\n"
EXCEPTION = RESET + ('\tfor block in get_tree().get_nodes_in_group("arena_block"):\n'
                     '\t\tif block.name == "Hurdle":\n\t\t\tadd_collision_exception_with(block)\n')

VARIANTS = {
    "known_good_capsule": [(LAYOUT, LAYER2, NO_LAYER)],
    "hurdle_layer4": [(LAYOUT, LAYER2, LAYER4)],
    "hurdle_shape_disabled": [(LAYOUT, LAYER2, NO_LAYER), (BUILDER, SHAPE, SHAPE_OFF)],
    "hurdle_two_faults": [(BUILDER, SHAPE, SHAPE_OFF)],
    "hurdle_collision_exception": [(LAYOUT, LAYER2, NO_LAYER), (PLAYER, RESET, EXCEPTION)],
    "hurdle_three_faults": [(BUILDER, SHAPE, SHAPE_OFF), (PLAYER, RESET, EXCEPTION)],
    "robot_hurdle_layer2": [(LAYOUT, NO_LAYER, LAYER2)],
}
ROBOT_BASED = ("robot_hurdle_layer2",)


def build(name: str) -> Path:
    dst = RUNS_DIR / "_baselines" / name
    if dst.exists():
        shutil.rmtree(dst)
    base = S.KNOWN_GOOD_BASELINE if name in ROBOT_BASED else S.DEFECT_BASELINE
    shutil.copytree(base, dst, ignore=shutil.ignore_patterns("build"))
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
