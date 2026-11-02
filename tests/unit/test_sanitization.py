"""This public copy's redactions (docs/SANITIZATION.md) are confined to identity metadata.

Checked here, from the repository alone: the ledger matches the files; only redactable file kinds differ from their
recorded hashes; markers sit only in tool results, never in model-authored transcript items; every prompt hash
recomputes from the published prompt text, so the text Muse received is unchanged; tampering is still caught.
That each redacted file equals its original apart from the markers needs the private originals and is not checked here."""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from propriosam.artifacts import RUNS_DIR, SANITIZABLE_NAMES, load_ledger, load_manifest, sha256_file, verify_bundle_hashes
from scripts.build_sanitization_ledger import build

REPO = RUNS_DIR.parent
WEB_RUNS = REPO / "web" / "public" / "runs"
LEDGER = load_ledger()
BUNDLES = sorted(p.parent for p in RUNS_DIR.glob("run_*/run_manifest.json"))
HERO = "run_20261030-140019_79d646"


def test_ledger_is_current():
    assert build() == LEDGER
    assert (WEB_RUNS / "SANITIZATION_LEDGER.json").read_text() == (RUNS_DIR / "SANITIZATION_LEDGER.json").read_text()


def test_ledger_entries_name_redactable_files_and_both_hashes():
    n = 0
    for run_id, entry in LEDGER["runs"].items():
        m = load_manifest(RUNS_DIR / run_id)
        for rel, e in entry.get("files", {}).items():
            assert Path(rel).name in SANITIZABLE_NAMES, rel
            assert e["recorded_sha256"] == m.files[rel] != e["public_sha256"]
            for root in (RUNS_DIR, WEB_RUNS):  # the dashboard copy, where exported, is the same file
                if (root / run_id / rel).exists():
                    assert sha256_file(root / run_id / rel) == e["public_sha256"]
            n += 1
    assert n


@pytest.mark.parametrize("run_dir", BUNDLES, ids=[b.name for b in BUNDLES])
def test_everything_else_is_byte_original(run_dir: Path):
    r = verify_bundle_hashes(run_dir)
    assert r["ok"] and not r["changed"] and not r["missing"]
    assert all(Path(k).name in SANITIZABLE_NAMES for k in r["sanitized"])


def test_markers_only_in_tool_results():
    for run_id, entry in LEDGER["runs"].items():
        for rel in entry.get("files", {}):
            if rel.endswith("transcript.json"):
                for item in json.loads((RUNS_DIR / run_id / rel).read_text()):
                    rest = {k: v for k, v in item.items() if k != "output"}
                    assert "<redacted:" not in json.dumps(rest)
                    assert item["type"] == "tool" or "<redacted:" not in json.dumps(item)


def test_prompt_text_is_what_muse_received(tmp_path: Path):
    """prompt_sha256 = sha256(instructions + user + json.dumps(tool specs)), the specs being those of the code at the
    commit the run recorded. It recomputes from the published prompt.json, whose banned-term list is redacted."""
    if shutil.which("git") is None or not (REPO / ".git").exists():
        pytest.skip("needs the git history")
    specs: dict[str, str] = {}
    prompts = sorted(RUNS_DIR.glob("run_*/repair_turn_*/prompt.json"))
    for pj in prompts:
        commit = load_manifest(pj.parent.parent).environment["git"]["commit"]
        if commit not in specs:
            d = tmp_path / commit
            d.mkdir()
            tar = subprocess.run(["git", "-C", str(REPO), "archive", commit, "propriosam", "scenarios"], capture_output=True, check=True)
            subprocess.run(["tar", "-x", "-C", str(d)], input=tar.stdout, check=True)
            out = subprocess.run([sys.executable, "-c", "import json; from propriosam.diagnosis import TOOL_SPECS; print(json.dumps(TOOL_SPECS))"],
                                 cwd=d, capture_output=True, text=True, check=True)
            specs[commit] = out.stdout.rstrip("\n")
        p = json.loads(pj.read_text())
        assert hashlib.sha256((p["instructions"] + p["user"] + specs[commit]).encode()).hexdigest() == p["prompt_sha256"], pj
    assert prompts


def test_tampering_with_a_redacted_file_is_caught(tmp_path: Path):
    run_id, entry = next((k, v) for k, v in LEDGER["runs"].items() if v.get("files"))
    rel = next(iter(entry["files"]))
    d = tmp_path / run_id
    shutil.copytree(RUNS_DIR / run_id, d)
    (d / rel).write_text((d / rel).read_text().replace("<redacted:", "<edited:", 1))
    r = verify_bundle_hashes(d)
    assert not r["ok"] and rel in r["changed"]


def test_ledger_cannot_excuse_a_replay_input(tmp_path: Path):
    d = tmp_path / HERO
    shutil.copytree(RUNS_DIR / HERO, d)
    rel = "pass1/verification.json"
    (d / rel).write_text((d / rel).read_text() + " ")
    forged = copy.deepcopy(LEDGER)
    forged["runs"][HERO].setdefault("files", {})[rel] = {"recorded_sha256": load_manifest(d).files[rel], "public_sha256": sha256_file(d / rel)}
    r = verify_bundle_hashes(d, ledger=forged)
    assert not r["ok"] and r["changed"] == [rel]
