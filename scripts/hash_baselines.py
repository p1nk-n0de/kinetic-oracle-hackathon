"""Deterministic tree hashes of the Godot baselines (sorted relative paths +
bytes, `.godot/` editor cache excluded), using the same function every run
bundle uses. For the audit doc and to prove the originals were never mutated."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from propriosam.artifacts import sha256_file, tree_sha256
from scenarios.godot_hurdle import scenario as S

BASELINES = {"defect_fixture": S.DEFECT_BASELINE, "known_good_scene": S.KNOWN_GOOD_BASELINE}

if __name__ == "__main__":
    out = {}
    for k, p in BASELINES.items():
        hh, n = tree_sha256(p)
        out[k] = {"tree_sha256": hh, "files": n}
    out["defect_fixture"]["arena_layout_gd_sha256"] = sha256_file(S.DEFECT_BASELINE / "scripts/arena_layout.gd")
    if "--json" in sys.argv:
        print(json.dumps(out, indent=1))
    else:
        for k, v in out.items():
            print(f"{k}: tree_sha256={v['tree_sha256']} files={v['files']}")
        print(f"arena_layout.gd sha256={out['defect_fixture']['arena_layout_gd_sha256']}")
