"""Muse's allowlisted tool surface and the prompt screen, with no Godot and no API.
Project files below are SYNTHETIC_UNIT_TEST_FIXTURE content."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from propriosam.artifacts import scrub, unscrub
from propriosam.diagnosis import (AntiCheatViolation, banned_terms_found, format_evidence, format_own_history)
from propriosam.mcp_adapter import TOOL_SPECS, DiagnosisTools
from propriosam.meta_client import SAM_MODEL, SPARK, WONDER, MetaClient
from propriosam.sensory_contract import CoverageGate, CrossingRule, SensoryContract
from propriosam.verifier import VerificationResult, VerificationStatus
from scenarios.godot_hurdle import scenario as S


@pytest.fixture
def project(tmp_path: Path) -> Path:
    p = tmp_path / "hurdle_scene"
    for rel, body in {"project.godot": "config/name=\"x\"\n", "scripts/a.gd": "var a := 1\nvar b := 2\nvar b2 := 2\n",
                      "scenes/m.tscn": "[gd_scene]\n", "DEFECT_FIXTURE.md": "the answer\n", "README.md": "notes\n",
                      "scenarios/s.yaml": "description: the answer\n", "oracle.yaml": "x: 1\n", "addons/b/plugin.gd": "x\n"}.items():
        (p / rel).parent.mkdir(parents=True, exist_ok=True)
        (p / rel).write_text(body)
    return p


def tools(project: Path) -> DiagnosisTools:
    return DiagnosisTools(None, project, S, project.parent / "turn")


def test_listing_exposes_only_source(project):
    assert tools(project).list_source_files() == ["project.godot", "scenes/m.tscn", "scripts/a.gd"]


@pytest.mark.parametrize("rel", ["DEFECT_FIXTURE.md", "README.md", "scenarios/s.yaml", "oracle.yaml", "addons/b/plugin.gd",
                                 "../secret.gd", "/etc/passwd", "scripts/../DEFECT_FIXTURE.md", ".godot/x.gd", ""])
def test_denied_reads(project, rel):
    out = asyncio.run(tools(project).dispatch("read_source", {"path": rel}))
    assert "error" in out and "content" not in out


def test_allowed_read(project):
    assert "var a" in asyncio.run(tools(project).dispatch("read_source", {"path": "scripts/a.gd"}))["content"]


def test_patch_requires_exactly_one_match_and_records_a_diff(project):
    t = tools(project)
    assert "error" in asyncio.run(t.dispatch("patch_source", {"path": "scripts/a.gd", "find": "var b", "replace": "x", "reason": "r"}))
    assert "error" in asyncio.run(t.dispatch("patch_source", {"path": "scripts/a.gd", "find": "nope", "replace": "x", "reason": "r"}))
    ok = asyncio.run(t.dispatch("patch_source", {"path": "scripts/a.gd", "find": "var a := 1", "replace": "var a := 9", "reason": "r"}))
    assert ok["ok"] and "+var a := 9" in ok["diff"] and len(t.patches) == 1
    assert "var a := 9" in (project / "scripts/a.gd").read_text()


@pytest.mark.parametrize("rel", ["project.godot", "README.md", "oracle.yaml"])
def test_patch_refuses_non_source(project, rel):
    assert "error" in asyncio.run(tools(project).dispatch("patch_source", {"path": rel, "find": "x", "replace": "y", "reason": "r"}))


def test_no_tool_offers_a_shell_or_arbitrary_mcp_access():
    assert {t["name"] for t in TOOL_SPECS} == {"inspect_scene", "inspect_physics", "drive", "list_source_files", "read_source", "patch_source"}


def _failure() -> tuple[SensoryContract, VerificationResult]:
    c = SensoryContract(contract_id="synthetic", objective=S.OBJECTIVE, scene_brief=S.SCENE_BRIEF, concept_vocabulary=S.CONCEPT_VOCABULARY,
                        statement="st", mover_concept="capsule", barrier_concept="yellow bar", expected_pass_behaviour="stays above",
                        expected_fail_signature="goes below", rule=CrossingRule(threshold_px=5, persistence_frames=3),
                        coverage=CoverageGate(critical_window=(25, 75), min_window_coverage=0.9, min_total_coverage=0.6)).freeze()
    r = VerificationResult(status=VerificationStatus.FAIL, contract_id="synthetic", contract_sha256=c.frozen_sha256, rule_sha256="0" * 64,
                           frame_count=80, residual=[None] * 80, mover_bottom=[None] * 80, barrier_bottom=[None] * 80, t_fail=60,
                           violation_run=[60, 61, 62], max_residual=235.0, max_residual_frame=79,
                           coverage={"both_window": 1.0}, evidence_rows=[], reasons=["E(t) > 5px"])
    return c, r


def test_authored_prompt_passes_the_screen():
    c, r = _failure()
    text = format_evidence(c, r, {"tool": "godot_send_input", "args": {"action": "move_forward"}, "result": {}})
    assert banned_terms_found(text, S.BANNED_PROMPT_TERMS) == []
    assert ".gd" not in text and ".tscn" not in text


def test_screen_catches_leaks():
    for leak in ("the DEFECT is here", 'it has "layer": 2 set', "collision_mask mismatch", str(S.DEFECT_BASELINE)):
        assert banned_terms_found(leak, S.BANNED_PROMPT_TERMS), leak
    assert issubclass(AntiCheatViolation, RuntimeError)


def test_own_history_reports_the_measured_result():
    h = format_own_history([{"turn": 1, "model": SPARK, "patches": [{"path": "scripts/a.gd", "find": "a", "replace": "b", "reason": "r"}],
                             "result_after": "status=FAIL t_fail=60 max_E=236"}])
    assert "status=FAIL" in h and "scripts/a.gd" in h
    assert format_own_history([]) == ""


def test_paths_are_scrubbed_and_reversible():
    home = str(Path.home())
    assert scrub({"p": [f"{home}/x"]}) == {"p": ["~/x"]}
    assert unscrub("~/x") == f"{home}/x"


@pytest.mark.parametrize("model,usage,expected", [
    (SPARK, {"input_tokens": 1_000_000, "input_tokens_details": {"cached_tokens": 0}, "output_tokens": 1_000_000}, 5.50),
    (SPARK, {"input_tokens": 1_000_000, "input_tokens_details": {"cached_tokens": 1_000_000}, "output_tokens": 0}, 0.15),
    (WONDER, {"input_tokens": 1_000_000, "output_tokens": 1_000_000}, 24.0),
    (SAM_MODEL, {"video_frames_processed": 80}, 0.016),
    (SAM_MODEL, {"video_frames_processed": 10}, 0.010),
])
def test_cost_estimates_use_published_prices(model, usage, expected):
    assert MetaClient.estimate_cost(model, usage) == pytest.approx(expected)
