"""Offline replay of every committed run bundle (no API, no Godot, no network).

Positive: each bundle under runs/ replays with exit 0 — hashes match and every stored verdict is reproduced from raw
SAM 3.1 text. Negative: tampered copies of a bundle are rejected."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from propriosam.artifacts import RUNS_DIR
from scripts.replay_run import VERDICT_BASIS, main, render_report, replay

REPO_ROOT = Path(__file__).resolve().parents[2]
BUNDLES = sorted(p.parent for p in RUNS_DIR.glob("*/run_manifest.json"))


@pytest.fixture(params=BUNDLES, ids=[b.name for b in BUNDLES])
def bundle(request) -> Path:
    return request.param


def test_at_least_one_bundle_is_committed():
    assert BUNDLES, "expected run bundles under runs/"


def test_replay_reproduces_every_committed_bundle(bundle: Path):
    rep = replay(bundle)
    assert rep["ok"], json.dumps({k: rep[k] for k in ("hashes", "contract", "checks", "warnings")}, indent=1, default=str)
    assert rep["hashes"]["ok"] and not rep["hashes"]["missing_required"] and not rep["hashes"]["changed"]
    assert rep["contract"]["frozen_intact"] and rep["contract"]["matches_manifest"]
    assert rep["passes"] and all(p["ok"] for p in rep["passes"])
    for p in rep["passes"]:
        assert p["recomputed"]["status"] == p["stored"]["status"] == p["manifest"]["verification_status"]
        assert p["recomputed"]["t_fail"] == p["stored"]["t_fail"] == p["manifest"]["t_fail"]
    assert rep["elapsed_s"] < 2.0


def test_audit_table_labels_verdicts_by_source(bundle: Path):
    text = render_report(replay(bundle))
    assert "REPLAY OK" in text and VERDICT_BASIS in text
    assert "[4] PASSES" in text and "[5] REPAIR TURNS" in text and "[6] SPEND" in text
    for status in ("FAIL", "PASS"):
        assert status in text  # both committed bundles go FAIL -> PASS


def test_cli_exit_code_and_json(bundle: Path):
    assert main(["--run-dir", str(bundle)]) == 0
    proc = subprocess.run([sys.executable, "-m", "scripts.replay_run", "--run-dir", str(bundle), "--json"],
                          cwd=REPO_ROOT, capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    rep = json.loads(proc.stdout)
    assert rep["ok"] is True and rep["run_id"] == bundle.name


def test_cli_rejects_missing_bundle(tmp_path: Path):
    assert main(["--run-dir", str(tmp_path)]) == 2


def _copy_bundle(src: Path, dst: Path) -> Path:
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("frames", "workspace"))
    return dst


def test_tampered_verdict_is_detected(tmp_path: Path):
    d = _copy_bundle(BUNDLES[0], tmp_path / BUNDLES[0].name)
    ver = d / "pass1" / "verification.json"
    stored = json.loads(ver.read_text())
    stored["status"] = "PASS" if stored["status"] != "PASS" else "FAIL"
    stored["t_fail"] = None
    ver.write_text(json.dumps(stored))
    rep = replay(d)
    assert not rep["ok"]
    assert not rep["hashes"]["ok"] and "pass1/verification.json" in rep["hashes"]["changed"]
    assert not rep["passes"][0]["ok"] and any("verification.json differs" in m for m in rep["passes"][0]["mismatches"])
    assert main(["--run-dir", str(d)]) == 1


def test_tampered_raw_sam_text_changes_the_recomputed_verdict(tmp_path: Path):
    d = _copy_bundle(BUNDLES[0], tmp_path / BUNDLES[0].name)
    sam_path = d / "pass1" / "sam" / "mover.json"
    sam = json.loads(sam_path.read_text())
    # drop every mover line from frame 40 on: the stored FAIL/PASS can no longer be reproduced from the evidence
    sam["raw_text"] = "\n".join(l for l in sam["raw_text"].splitlines() if int(l.split("f>")[0].lstrip("<")) < 40)
    sam_path.write_text(json.dumps(sam))
    rep = replay(d)
    assert not rep["ok"] and not rep["passes"][0]["ok"]
    assert rep["passes"][0]["recomputed"]["status"] != rep["passes"][0]["stored"]["status"] or \
        rep["passes"][0]["recomputed"]["t_fail"] != rep["passes"][0]["stored"]["t_fail"]


def test_tampered_contract_breaks_the_frozen_hash(tmp_path: Path):
    d = _copy_bundle(BUNDLES[0], tmp_path / BUNDLES[0].name)
    cpath = d / "contract.json"
    c = json.loads(cpath.read_text())
    c["rule"]["threshold_px"] = 19
    cpath.write_text(json.dumps(c))
    rep = replay(d)
    assert not rep["ok"] and not rep["contract"]["frozen_intact"] and "contract.json" in rep["hashes"]["changed"]


def test_missing_required_file_fails_but_missing_frames_do_not(tmp_path: Path):
    d = _copy_bundle(BUNDLES[0], tmp_path / BUNDLES[0].name)
    assert replay(d)["ok"]  # frames/ (and workspace/) were not copied: optional
    (d / "pass1" / "clip.mp4").unlink()
    rep = replay(d)
    assert not rep["ok"] and rep["hashes"]["missing_required"] == ["pass1/clip.mp4"]
