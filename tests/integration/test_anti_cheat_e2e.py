"""Anti-cheat audit of the latest COMPLETE closed_loop bundle in runs/.

Asserts, from disk only (no API, no Godot):
  * the original baseline project was never mutated and the staged copy matched it before pass 1;
  * every outgoing Muse prompt passed the banned-term screen, and the turn-1 prompt names no source file;
  * no prompt or evidence contains hidden ground truth;
  * every Meta call carries a request id; pass clips are distinct;
  * pass 1 is FAIL with t_fail in the expected band, the final pass is PASS;
  * every stored verdict is reproduced by re-running the frozen verifier on the raw SAM text;
  * every bundle file still hashes as recorded."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from propriosam.artifacts import RUNS_DIR, load_manifest, tree_sha256, verify_bundle_hashes
from propriosam.sensory_contract import SensoryContract
from propriosam.verifier import verify
from propriosam.vision_tracker import build_track, parse_sam_text
from scenarios.godot_hurdle import scenario as S


def _latest_closed_loop() -> Path | None:
    cands = []
    for d in sorted(RUNS_DIR.glob("run_*")):
        mp = d / "run_manifest.json"
        if mp.exists():
            m = json.loads(mp.read_text())
            if m.get("kind") == "closed_loop" and m.get("status") == "COMPLETE" and m.get("repair_turns"):
                cands.append(d)
    return cands[-1] if cands else None


@pytest.fixture(scope="module")
def bundle():
    d = _latest_closed_loop()
    if d is None:
        pytest.skip("no COMPLETE closed_loop bundle with repair turns under runs/")
    return d, load_manifest(d)


def test_baseline_never_mutated(bundle):
    d, m = bundle
    assert m.baseline["unchanged"] is True
    assert m.workspace["baseline_match_at_stage"] is True
    assert m.workspace["staged_tree_sha256"] == m.baseline["tree_sha256"]
    if Path(m.baseline["path"]).exists():  # live re-check when the fixture is reachable
        assert tree_sha256(m.baseline["path"])[0] == m.baseline["tree_sha256"]


def test_prompts_are_blind(bundle):
    d, m = bundle
    assert m.repair_turns, "expected at least one repair turn"
    for rt in m.repair_turns:
        p = json.loads((d / rt.prompt_path).read_text())
        assert p["banned_terms_found"] == [], f"turn {rt.turn}: {p['banned_terms_found']}"
        blob = (p["instructions"] + p["user"] + json.dumps(p["tools"])).lower()
        for term in S.BANNED_PROMPT_TERMS:
            assert term.lower() not in blob, f"turn {rt.turn}: banned term {term!r} in outgoing prompt"
        assert "truth" not in blob
        assert "diff --git" not in blob and "@@ -" not in p["user"]
    turn1 = json.loads((d / m.repair_turns[0].prompt_path).read_text())
    assert ".gd" not in turn1["user"] and ".tscn" not in turn1["user"], "turn-1 prompt must not point at a source file"
    assert not turn1["mentions_source_filenames"]


def test_request_ids_and_distinct_clips(bundle):
    d, m = bundle
    assert m.request_ids and all(isinstance(r, str) and len(r) >= 8 for r in m.request_ids)
    for p in m.passes:
        for role, s in p.sam.items():
            assert s["request_id"], f"pass{p.index} {role} has no request id"
    for rt in m.repair_turns:
        assert rt.request_ids
    shas = [p.clip_sha256 for p in m.passes]
    assert len(set(shas)) == len(shas), "pass clips must differ"


def test_fail_then_pass(bundle):
    d, m = bundle
    first, last = m.passes[0], m.passes[-1]
    assert first.verification_status == "FAIL" and first.t_fail is not None and 50 <= first.t_fail <= 70
    assert last.verification_status == "PASS"
    assert m.final_verdict == "PASS"
    assert any(rt.patches for rt in m.repair_turns)
    assert m.workspace.get("modified_during_run") is True


def test_verdicts_reproduce_from_raw_sam_text(bundle):
    d, m = bundle
    contract = SensoryContract.model_validate_json((d / m.contract_path).read_text())
    assert contract.check_frozen() and contract.frozen_sha256 == m.contract_sha256
    for p in m.passes:
        stored = json.loads((d / p.verification_path).read_text())
        tracks = {}
        for role in ("mover", "barrier"):
            raw = json.loads((d / p.sam[role]["raw_path"]).read_text())["raw_text"]
            concept = contract.mover_concept if role == "mover" else contract.barrier_concept
            tracks[role] = build_track(concept, parse_sam_text(raw), contract.frame_count, tuple(contract.frame_size))
        r = verify(contract, tracks["mover"], tracks["barrier"])
        assert r.status.value == stored["status"] and r.t_fail == stored["t_fail"]
        assert r.residual == stored["residual"]


def test_bundle_hashes_intact(bundle):
    d, m = bundle
    res = verify_bundle_hashes(d)
    assert res["ok"], res
