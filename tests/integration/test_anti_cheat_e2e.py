"""Anti-cheat audit of every COMPLETE closed_loop bundle in runs/, from disk only
(no API, no Godot):
  * the original baseline was never mutated; the staged copy matched it before pass 1;
  * every outgoing Muse prompt passed the banned-term screen; turn-1 names no source file;
  * no tool output Muse received leaks fixture notes or local paths;
  * every Meta call carries a request id; pass clips are distinct;
  * verdicts reproduce from the raw SAM text under the frozen contract;
  * every bundle file still hashes as recorded."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from propriosam.artifacts import RUNS_DIR, load_manifest, tree_sha256, unscrub, verify_bundle_hashes
from propriosam.sensory_contract import SensoryContract
from propriosam.verifier import verify
from propriosam.vision_tracker import build_track, parse_sam_text
from scenarios.godot_hurdle import scenario as S


def _bundles() -> list[Path]:
    out = []
    for d in sorted(RUNS_DIR.glob("run_*")):
        mp = d / "run_manifest.json"
        if mp.exists():
            m = json.loads(mp.read_text())
            if m.get("kind") == "closed_loop" and m.get("status") == "COMPLETE":
                out.append(d)
    return out


BUNDLES = _bundles()
REPAIRED = [d for d in BUNDLES if load_manifest(d).repair_turns]
each_bundle = pytest.mark.parametrize("d", BUNDLES, ids=lambda p: p.name)
each_repaired = pytest.mark.parametrize("d", REPAIRED, ids=lambda p: p.name)


@each_bundle
def test_baseline_never_mutated(d):
    m = load_manifest(d)
    assert m.baseline["unchanged"] is True
    assert m.workspace["baseline_match_at_stage"] is True
    assert m.workspace["staged_tree_sha256"] == m.baseline["tree_sha256"]
    local = Path(unscrub(m.baseline["path"]))
    if local.exists():  # live re-check when the fixture is reachable
        assert tree_sha256(local)[0] == m.baseline["tree_sha256"]


@each_repaired
def test_prompts_are_blind(d):
    m = load_manifest(d)
    for rt in m.repair_turns:
        p = json.loads((d / rt.prompt_path).read_text())
        assert p["banned_terms_found"] == [], f"turn {rt.turn}: {p['banned_terms_found']}"
        authored = p["user"].replace(p.get("own_history", ""), "")
        blob = (p["instructions"] + authored + json.dumps(p["tools"])).lower()
        for term in S.BANNED_PROMPT_TERMS:
            assert term.lower() not in blob, f"turn {rt.turn}: banned term {term!r} in outgoing prompt"
        assert "truth" not in blob and "diff --git" not in blob and "@@ -" not in authored
    turn1 = json.loads((d / m.repair_turns[0].prompt_path).read_text())
    assert ".gd" not in turn1["user"] and ".tscn" not in turn1["user"], "turn-1 prompt must not point at a source file"
    assert turn1["own_history"] == ""


@each_repaired
def test_tool_outputs_leak_nothing(d):
    m = load_manifest(d)
    for rt in m.repair_turns:
        tr = (d / rt.transcript_path).read_text()
        for term in ("defect", "/Volumes/", "/Users/", "truth_hidden", "DEFECT_FIXTURE"):
            assert term.lower() not in tr.lower(), f"turn {rt.turn}: {term!r} in Muse's transcript"


@each_repaired
def test_source_reads_stay_inside_the_allowlist(d):
    m = load_manifest(d)
    for rt in m.repair_turns:
        for c in json.loads((d / f"repair_turn_{rt.turn}" / "tool_calls.json").read_text()):
            if c["tool"] in ("read_source", "patch_source"):
                rel = c["args"].get("path", "")
                assert not rel.startswith("/") and ".." not in rel
                assert not rel.endswith((".md", ".yaml", ".json")), rel


@each_bundle
def test_request_ids_and_distinct_clips(d):
    m = load_manifest(d)
    assert m.request_ids and all(isinstance(r, str) and len(r) >= 8 for r in m.request_ids)
    for p in m.passes:
        for role, s in p.sam.items():
            assert s["request_id"], f"pass{p.index} {role} has no request id"
    for rt in m.repair_turns:
        assert rt.request_ids
    shas = [p.clip_sha256 for p in m.passes]
    assert len(set(shas)) == len(shas), "pass clips must differ"


@each_repaired
def test_repair_only_after_fail_and_verdict_is_the_last_pass(d):
    m = load_manifest(d)
    assert m.passes[0].verification_status == "FAIL"
    assert 50 <= m.passes[0].t_fail <= 70
    assert m.final_verdict == m.passes[-1].verification_status
    assert m.workspace.get("modified_during_run") is True


@each_bundle
def test_no_repair_without_a_failure(d):
    m = load_manifest(d)
    if m.passes[0].verification_status != "FAIL":
        assert not m.repair_turns and len(m.passes) == 1
        assert m.workspace.get("modified_during_run") is False


def test_at_least_one_fail_to_pass_bundle_exists():
    assert any(load_manifest(d).final_verdict == "PASS" for d in REPAIRED)


@each_bundle
def test_verdicts_reproduce_from_raw_sam_text(d):
    m = load_manifest(d)
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


@each_bundle
def test_bundle_hashes_intact(d):
    res = verify_bundle_hashes(d)
    assert res["ok"], res
