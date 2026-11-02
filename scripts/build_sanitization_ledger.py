"""Build or check runs/SANITIZATION_LEDGER.json, the published record of which bundle files in this public release
differ from the hash recorded when the run wrote them, and why.

Every entry is an identity redaction: a `<redacted:...>` marker (docs/SANITIZATION.md) in a file kind that may carry
one (`artifacts.SANITIZABLE_NAMES`). Replay inputs are never covered: SAM output, tracks, verifications, contracts,
clips, overlays, hidden truth, API call logs, patches and diffs must match their recorded hashes byte for byte. The
recorded hashes are left as the runs wrote them; they are the hashes of the private originals.

  python -m scripts.build_sanitization_ledger          # write runs/SANITIZATION_LEDGER.json
  python -m scripts.build_sanitization_ledger --check  # exit 1 if the committed ledger is stale"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from propriosam.artifacts import LEDGER_PATH, RUNS_DIR, SANITIZABLE_NAMES, hash_bundle_files, load_manifest  # noqa: E402

MARKER = re.compile(r"<redacted:[a-z]+>")
MARKERS = {"<redacted:studio>": "name of the author's private Godot studio (pre-existing tooling, not part of the entry)",
           "<redacted:volume>": "label of a local external drive"}
NOTE = ("Files listed under `files` are published with identity strings replaced by the markers above. recorded_sha256 "
        "is the hash the run wrote into run_manifest.json, left unchanged: it is the hash of the private original. "
        "public_sha256 is the hash of the file in this repository. Markers sit only in tool results, MCP log previews "
        "and banned-term lists: no prompt text, model-authored text or replay input was changed. Every "
        "run_manifest.json also carries the rewritten id of the commit that produced the run (environment.git.commit); "
        "manifests are not in their own hash lists. See docs/SANITIZATION.md.")


def _locations(obj, path=""):
    """JSON paths of every string that carries a marker."""
    if isinstance(obj, str):
        if MARKER.search(obj):
            yield path or "."
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _locations(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _locations(v, f"{path}[{i}]")


def _describe(rel: str, text: str) -> list[str]:
    if rel.endswith(".jsonl"):
        out = []
        for n, line in enumerate(text.splitlines(), 1):
            if MARKER.search(line):
                rec = json.loads(line)
                out += [f"line {n} ({rec.get('tool')}): {p.lstrip('.')}" for p in _locations(rec)]
        return out
    data = json.loads(text)
    if rel.endswith("transcript.json"):
        return [f"[{i}] {it.get('type')} {it.get('name', '')}: {p.lstrip('.')}" for i, it in enumerate(data) for p in _locations(it)]
    return [p.lstrip(".") for p in _locations(data)]


def _counts(text: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for m in MARKER.findall(text):
        out[m] = out.get(m, 0) + 1
    return dict(sorted(out.items()))


def build() -> dict:
    runs = {}
    for mp in sorted(RUNS_DIR.glob("*/run_manifest.json")):
        run_dir = mp.parent
        m = load_manifest(run_dir)
        now = hash_bundle_files(run_dir)
        files = {}
        for rel, recorded in sorted(m.files.items()):
            if rel not in now or now[rel] == recorded:
                continue
            if Path(rel).name not in SANITIZABLE_NAMES:
                raise SystemExit(f"{m.run_id}/{rel}: differs from its recorded hash and may not be redacted")
            text = (run_dir / rel).read_text()
            if not MARKER.search(text):
                raise SystemExit(f"{m.run_id}/{rel}: differs from its recorded hash but carries no redaction marker")
            files[rel] = {"recorded_sha256": recorded, "public_sha256": now[rel], "markers": _counts(text),
                          "locations": _describe(rel, text)}
        entry: dict = {"files": files} if files else {}
        mtext = mp.read_text()
        if MARKER.search(mtext):
            entry["run_manifest.json"] = {"markers": _counts(mtext), "locations": _describe("run_manifest.json", mtext)}
        if entry:
            runs[m.run_id] = entry
    return {"schema_version": "1.0", "note": NOTE, "markers": MARKERS, "sanitizable_file_names": list(SANITIZABLE_NAMES),
            "runs": runs}


def main(argv: list[str] | None = None) -> int:
    text = json.dumps(build(), indent=1, sort_keys=True) + "\n"
    if "--check" in (sys.argv[1:] if argv is None else argv):
        ok = LEDGER_PATH.exists() and LEDGER_PATH.read_text() == text
        print(f"{LEDGER_PATH.relative_to(REPO_ROOT)}: {'current' if ok else 'STALE'}")
        return 0 if ok else 1
    LEDGER_PATH.write_text(text)
    print(f"wrote {LEDGER_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
