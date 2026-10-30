"""Hashing and bundle integrity, on SYNTHETIC_UNIT_TEST_FIXTURE trees."""
from __future__ import annotations

from pathlib import Path

from propriosam.artifacts import RunManifest, hash_bundle_files, save_manifest, tree_sha256, verify_bundle_hashes


def _tree(root: Path) -> Path:
    for rel, body in {"a.txt": "a", "sub/b.txt": "b", ".godot/cache.bin": "c", "sub/.godot/x": "d"}.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(body)
    return root


def test_tree_hash_really_excludes_the_editor_cache(tmp_path):
    t = _tree(tmp_path / "scene")
    before, n = tree_sha256(t)
    assert n == 2
    (t / ".godot/cache.bin").write_text("changed by launching the game")
    (t / ".godot/new_file").write_text("x")
    assert tree_sha256(t)[0] == before


def test_tree_hash_sees_source_changes_and_renames(tmp_path):
    t = _tree(tmp_path / "scene")
    before = tree_sha256(t)[0]
    (t / "sub/b.txt").write_text("B")
    changed = tree_sha256(t)[0]
    assert changed != before
    (t / "sub/b.txt").rename(t / "sub/c.txt")
    assert tree_sha256(t)[0] != changed


def test_bundle_hashes_skip_workspace_and_editor_cache(tmp_path):
    run = tmp_path / "run"
    _tree(run / "workspace/scene")
    (run / "pass1/frames").mkdir(parents=True)
    (run / "pass1/clip.mp4").write_text("clip")
    (run / "pass1/frames/f_000.png").write_text("frame")
    (run / "pass1/.godot").mkdir()
    (run / "pass1/.godot/x").write_text("x")
    files = hash_bundle_files(run)
    assert sorted(files) == ["pass1/clip.mp4", "pass1/frames/f_000.png"]


def test_verify_detects_tampering_and_treats_frames_as_optional(tmp_path):
    run = tmp_path / "run"
    (run / "pass1/frames").mkdir(parents=True)
    (run / "pass1/clip.mp4").write_text("clip")
    (run / "pass1/frames/f_000.png").write_text("frame")
    save_manifest(run, RunManifest(run_id="r", kind="closed_loop", created_at="t"))
    assert verify_bundle_hashes(run)["ok"]
    (run / "pass1/frames/f_000.png").unlink()
    res = verify_bundle_hashes(run)
    assert res["ok"] and res["missing_optional_frames"] == 1
    (run / "pass1/clip.mp4").write_text("tampered")
    res = verify_bundle_hashes(run)
    assert not res["ok"] and res["changed"] == ["pass1/clip.mp4"]
