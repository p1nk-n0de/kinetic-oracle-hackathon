"""Deterministic tree hashes of the Godot baselines (sorted relative paths +
bytes, `.godot/` editor cache excluded). Used by the audit doc and by the
anti-cheat tests to prove the originals were never mutated."""
import hashlib, json, os, sys

STUDIO = os.path.expanduser("~/Projects/godot-studio")
BASELINES = {
    "defect_fixture": f"{STUDIO}/tests/fixtures/pg_defect_hurdle",
    "known_good_scene": f"{STUDIO}/example_game/proving_ground",
}
SKIP_DIRS = (".godot",)


def tree_hash(root: str) -> tuple[str, int]:
    h, n = hashlib.sha256(), 0
    for r, ds, fs in sorted(os.walk(root)):
        ds[:] = sorted(d for d in ds if d not in SKIP_DIRS)
        for f in sorted(fs):
            fp = os.path.join(r, f)
            h.update(os.path.relpath(fp, root).encode()); h.update(b"\0")
            with open(fp, "rb") as fh:
                h.update(fh.read())
            h.update(b"\0"); n += 1
    return h.hexdigest(), n


def file_hash(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


if __name__ == "__main__":
    out = {}
    for k, p in BASELINES.items():
        hh, n = tree_hash(p)
        out[k] = {"path": p, "realpath": os.path.realpath(p), "tree_sha256": hh, "files": n}
    out["defect_fixture"]["arena_layout_gd_sha256"] = file_hash(f"{BASELINES['defect_fixture']}/scripts/arena_layout.gd")
    print(json.dumps(out, indent=1) if "--json" in sys.argv else
          "\n".join(f"{k}: tree_sha256={v['tree_sha256']} files={v['files']}" for k, v in out.items())
          + f"\narena_layout.gd sha256={out['defect_fixture']['arena_layout_gd_sha256']}")
