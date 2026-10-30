"""Immutable run bundles: `runs/<run_id>/run_manifest.json` plus hashed files.

Bundle layout (also documented in docs/RUN_BUNDLE_SPEC.md):
  run_manifest.json          this model, written last
  api_calls.jsonl            every Meta API call (request ids, usage, est cost)
  contract.json              frozen SensoryContract
  passN/clip.mp4, frames/, sam/<concept>.json, tracks.json, verification.json,
        overlay.mp4, open_loop.json, truth_hidden.json (never shown to Muse)
  repair_turn_N/prompt.json, transcript.json, patches.json, diff.patch
  workspace/                 staged Godot project (gitignored; hashed)"""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = REPO_ROOT / "runs"
HASH_SKIP_DIRS = (".godot",)


def new_run_id(prefix: str = "run") -> str:
    return f"{prefix}_{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}_{uuid.uuid4().hex[:6]}"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def tree_sha256(root: str | Path, skip_dirs: tuple[str, ...] = HASH_SKIP_DIRS) -> tuple[str, int]:
    """Deterministic hash over sorted relative paths and bytes; `.godot/` excluded."""
    root = Path(root)
    h, n = hashlib.sha256(), 0
    for r, ds, fs in sorted(os.walk(root)):
        ds[:] = sorted(d for d in ds if d not in skip_dirs)
        for f in sorted(fs):
            fp = Path(r) / f
            h.update(str(fp.relative_to(root)).encode()); h.update(b"\0")
            with open(fp, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    h.update(chunk)
            h.update(b"\0"); n += 1
    return h.hexdigest(), n


def _default(o: Any):
    if isinstance(o, BaseModel):
        return o.model_dump(mode="json")
    if isinstance(o, Path):
        return str(o)
    if hasattr(o, "__dict__"):
        return o.__dict__
    raise TypeError(f"not serialisable: {type(o)}")


def _scrub_pairs() -> list[tuple[str, str]]:
    studio = Path("~/Projects/godot-studio").expanduser()
    pairs = [(str(REPO_ROOT), "<repo>")]
    pairs += [(p, "<godot-studio>") for p in sorted({os.path.realpath(studio), str(studio)}, key=len, reverse=True)]
    pairs.append((str(Path.home()), "~"))
    return pairs


_PAIRS = _scrub_pairs()


def scrub(o: Any) -> Any:
    """Replace machine-specific path prefixes, so bundles and what Muse sees carry no local paths."""
    if isinstance(o, str):
        for a, b in _PAIRS:
            o = o.replace(a, b)
        return o
    if isinstance(o, dict):
        return {scrub(k) if isinstance(k, str) else k: scrub(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [scrub(x) for x in o]
    return o


def unscrub(s: str) -> str:
    return str(Path(s.replace("<repo>", str(REPO_ROOT)).replace("<godot-studio>", "~/Projects/godot-studio")).expanduser())


def write_json(path: str | Path, obj: Any) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    plain = json.loads(json.dumps(obj, default=_default))
    path.write_text(json.dumps(scrub(plain), indent=1, sort_keys=True))
    return path


def read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text())


class PassRecord(BaseModel):
    index: int
    label: str
    project_tree_sha256: str | None = None
    clip_path: str
    clip_sha256: str
    frames_dir: str
    frame_count: int
    capture: dict = Field(default_factory=dict)
    open_loop: dict = Field(default_factory=dict)
    sam: dict = Field(default_factory=dict)
    tracks_path: str
    verification_path: str
    verification_status: str
    t_fail: int | None = None
    max_residual: float | None = None
    overlay_path: str | None = None
    overlay_sha256: str | None = None
    overlay_info: dict = Field(default_factory=dict)
    truth_hidden_path: str | None = None


class RepairTurnRecord(BaseModel):
    turn: int
    model: str
    escalated: bool = False
    request_ids: list[str] = Field(default_factory=list)
    response_ids: list[str] = Field(default_factory=list)
    tool_calls: int = 0
    tool_call_names: list[str] = Field(default_factory=list)
    patches: list[dict] = Field(default_factory=list)
    prompt_path: str
    transcript_path: str
    diff_path: str | None = None
    diff_sha256: str | None = None
    outcome_text: str = ""
    anti_cheat: dict = Field(default_factory=dict)
    est_cost_usd: float | None = None


class RunManifest(BaseModel):
    schema_version: str = "1.0"
    run_id: str
    kind: str  # closed_loop | clip_evaluation
    created_at: str
    finished_at: str | None = None
    status: str = "RUNNING"
    final_verdict: str | None = None
    verdict_basis: str = ("Verdict comes only from verifier.verify over SAM 3.1 tracks under the frozen contract; "
                          "MCP tool statuses and model text are recorded but never consulted.")
    models: dict = Field(default_factory=dict)
    baseline: dict = Field(default_factory=dict)
    workspace: dict = Field(default_factory=dict)
    contract_path: str | None = None
    contract_sha256: str | None = None
    rule_sha256: str | None = None
    passes: list[PassRecord] = Field(default_factory=list)
    repair_turns: list[RepairTurnRecord] = Field(default_factory=list)
    spend: dict = Field(default_factory=dict)
    request_ids: list[str] = Field(default_factory=list)
    files: dict[str, str] = Field(default_factory=dict)
    anti_cheat: dict = Field(default_factory=dict)
    environment: dict = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


def hash_bundle_files(run_dir: Path, skip=("workspace", "run_manifest.json")) -> dict[str, str]:
    out: dict[str, str] = {}
    for r, ds, fs in sorted(os.walk(run_dir)):
        ds[:] = sorted(d for d in ds if d not in skip and d not in HASH_SKIP_DIRS)
        for f in sorted(fs):
            if f in skip:
                continue
            fp = Path(r) / f
            out[str(fp.relative_to(run_dir))] = sha256_file(fp)
    return out


def save_manifest(run_dir: str | Path, manifest: RunManifest) -> Path:
    run_dir = Path(run_dir)
    manifest.files = hash_bundle_files(run_dir)
    return write_json(run_dir / "run_manifest.json", manifest)


def load_manifest(run_dir: str | Path) -> RunManifest:
    return RunManifest.model_validate_json((Path(run_dir) / "run_manifest.json").read_text())


def verify_bundle_hashes(run_dir: str | Path) -> dict:
    run_dir = Path(run_dir)
    m = load_manifest(run_dir)
    now = hash_bundle_files(run_dir)
    # Raw frame PNGs are not distributed with the repo (gitignored); their absence is reported, not failed.
    optional = lambda k: "/frames/" in k  # noqa: E731
    missing = sorted(k for k in m.files if k not in now and not optional(k))
    missing_optional = sorted(k for k in m.files if k not in now and optional(k))
    changed = sorted(k for k in m.files if k in now and now[k] != m.files[k])
    extra = sorted(k for k in now if k not in m.files)
    return {"ok": not missing and not changed, "missing": missing, "missing_optional_frames": len(missing_optional),
            "changed": changed, "extra": extra, "checked": len(m.files)}
