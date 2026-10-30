"""Copy run bundles into the dashboard's static data directory (stdlib only).

  python -m scripts.export_bundle_for_web                      # every bundle under runs/
  python -m scripts.export_bundle_for_web --run-dir runs/<id>  # one bundle (repeatable)
  python -m scripts.export_bundle_for_web --clean              # also delete exported runs that no longer exist

Copies, per bundle, into web/public/runs/<run_id>/:
  run_manifest.json, contract.json, api_calls.jsonl,
  pass*/clip.mp4, pass*/overlay.mp4, pass*/tracks.json, pass*/verification.json, pass*/sam/*.json,
  pass*/truth_hidden.json (if present),
  repair_turn_*/prompt.json | transcript.json | patches.json | diff.patch
and writes web/public/runs/index.json listing every exported run (id, kind, status, final_verdict, created_at, ...).
Raw frames/, workspace/ and mcp_calls.jsonl are not exported (gitignored or too large for a static site)."""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = REPO_ROOT / "runs"
WEB_RUNS_DIR = REPO_ROOT / "web" / "public" / "runs"

TOP_LEVEL = ("run_manifest.json", "contract.json", "api_calls.jsonl")
PASS_FILES = ("clip.mp4", "overlay.mp4", "tracks.json", "verification.json", "truth_hidden.json")
PASS_GLOBS = ("sam/*.json",)
REPAIR_FILES = ("prompt.json", "transcript.json", "patches.json", "diff.patch")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def bundle_files(run_dir: Path) -> list[Path]:
    """Relative paths of the files the dashboard needs, in deterministic order."""
    out: list[Path] = []
    for name in TOP_LEVEL:
        if (run_dir / name).exists():
            out.append(Path(name))
    for pass_dir in sorted(p for p in run_dir.glob("pass*") if p.is_dir()):
        for name in PASS_FILES:
            if (pass_dir / name).exists():
                out.append((pass_dir / name).relative_to(run_dir))
        for pat in PASS_GLOBS:
            for f in sorted(glob.glob(str(pass_dir / pat))):
                out.append(Path(f).relative_to(run_dir))
    for turn_dir in sorted(p for p in run_dir.glob("repair_turn_*") if p.is_dir()):
        for name in REPAIR_FILES:
            if (turn_dir / name).exists():
                out.append((turn_dir / name).relative_to(run_dir))
    return out


def copy_if_changed(src: Path, dst: Path) -> bool:
    """Copy unless an identical file is already there (keeps git diffs quiet). Returns True when written."""
    if dst.exists() and dst.stat().st_size == src.stat().st_size and sha256_file(dst) == sha256_file(src):
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def export_bundle(run_dir: Path, out_root: Path) -> dict:
    manifest = json.loads((run_dir / "run_manifest.json").read_text())
    run_id = manifest.get("run_id") or run_dir.name
    dest = out_root / run_id
    files = bundle_files(run_dir)
    written = 0
    total_bytes = 0
    for rel in files:
        written += copy_if_changed(run_dir / rel, dest / rel)
        total_bytes += (run_dir / rel).stat().st_size
    # Remove stale files from earlier exports of the same run.
    keep = {str(f) for f in files}
    for root, _dirs, names in os.walk(dest):
        for n in names:
            rel = str(Path(root, n).relative_to(dest))
            if rel not in keep:
                (dest / rel).unlink()
    passes = manifest.get("passes") or []
    entry = {
        "run_id": run_id,
        "kind": manifest.get("kind"),
        "status": manifest.get("status"),
        "final_verdict": manifest.get("final_verdict"),
        "verdict_basis": manifest.get("verdict_basis"),
        "created_at": manifest.get("created_at"),
        "finished_at": manifest.get("finished_at"),
        "passes": len(passes),
        "pass_statuses": [p.get("verification_status") for p in passes],
        "pass_labels": [p.get("label") for p in passes],
        "repair_turns": len(manifest.get("repair_turns") or []),
        "models": manifest.get("models") or {},
        "est_cost_usd": (manifest.get("spend") or {}).get("est_cost_usd"),
        "exported_files": [str(f) for f in files],
        "exported_bytes": total_bytes,
    }
    print(f"{run_id}: {len(files)} files ({total_bytes / 1e6:.2f} MB), {written} written -> {dest.relative_to(REPO_ROOT)}")
    return entry


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-dir", action="append", default=None, help="bundle to export (repeatable); default: all under runs/")
    ap.add_argument("--out", default=str(WEB_RUNS_DIR), help=f"destination root (default {WEB_RUNS_DIR.relative_to(REPO_ROOT)})")
    ap.add_argument("--clean", action="store_true", help="delete exported run directories that are not in this export")
    a = ap.parse_args(argv)
    out_root = Path(a.out)
    if a.run_dir:
        run_dirs = [Path(d) for d in a.run_dir]
    else:
        run_dirs = sorted(p.parent for p in RUNS_DIR.glob("*/run_manifest.json"))
    if not run_dirs:
        print("no bundles found", file=sys.stderr)
        return 1
    entries = []
    for d in run_dirs:
        if not (d / "run_manifest.json").exists():
            print(f"skip {d}: no run_manifest.json", file=sys.stderr)
            continue
        entries.append(export_bundle(d, out_root))
    if a.clean and out_root.exists():
        keep = {e["run_id"] for e in entries}
        for child in out_root.iterdir():
            if child.is_dir() and child.name not in keep:
                shutil.rmtree(child)
                print(f"removed stale export {child.name}")
    # Merge with runs already exported (so exporting one bundle does not drop the others from the index).
    index_path = out_root / "index.json"
    existing = {}
    if index_path.exists() and not a.clean:
        try:
            for e in json.loads(index_path.read_text()).get("runs", []):
                if (out_root / e["run_id"] / "run_manifest.json").exists():
                    existing[e["run_id"]] = e
        except (json.JSONDecodeError, KeyError, TypeError):
            existing = {}
    for e in entries:
        existing[e["run_id"]] = e
    runs = sorted(existing.values(), key=lambda e: (e.get("created_at") or "", e["run_id"]), reverse=True)
    index = {"schema_version": "1.0", "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "note": "Static export of run bundles for the dashboard. Verdicts come only from the verifier over SAM 3.1 tracks; "
                     "tool status and model text are never consulted.",
             "runs": runs}
    out_root.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(index, indent=1, sort_keys=True) + "\n")
    print(f"index: {len(runs)} run(s) -> {index_path.relative_to(REPO_ROOT) if index_path.is_relative_to(REPO_ROOT) else index_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
