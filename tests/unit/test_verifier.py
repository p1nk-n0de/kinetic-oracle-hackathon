"""Frozen-rule verifier tests on SYNTHETIC_UNIT_TEST_FIXTURE tracks (no API, no Godot)."""
from __future__ import annotations

import json
from pathlib import Path

from propriosam.sensory_contract import CoverageGate, CrossingRule, SensoryContract
from propriosam.verifier import VerificationStatus, rule_sha256, verify
from propriosam.vision_tracker import Track, TrackPoint, build_track, parse_sam_text


def _contract(threshold=0, persistence=3, window=(45, 70), min_window=0.9, min_total=0.6) -> SensoryContract:
    return SensoryContract(contract_id="synthetic", objective="o", scene_brief="s", concept_vocabulary=["capsule", "yellow bar"],
                           statement="st", mover_concept="capsule", barrier_concept="yellow bar",
                           expected_pass_behaviour="", expected_fail_signature="",
                           rule=CrossingRule(threshold_px=threshold, persistence_frames=persistence),
                           coverage=CoverageGate(critical_window=window, min_window_coverage=min_window,
                                                 min_total_coverage=min_total)).freeze()


def _track(concept: str, bottoms: dict[int, float], n=80) -> Track:
    # SYNTHETIC_UNIT_TEST_FIXTURE: boxes 40px wide/70px tall whose bottom edge is the given value
    tr = Track(concept, "0", n, (960, 540))
    for f, b in sorted(bottoms.items()):
        tr.points[f] = TrackPoint(f, 460.0, b - 70, 500.0, b, 480.0, b - 35, b, 0.9)
    return tr


def _barrier_crossing_at(frame: int, n=80) -> dict[int, float]:
    # barrier bottom climbs 5px/frame from 78 and passes the mover's feet (296) at `frame`
    return {f: 296 - 5 * (frame - f) for f in range(n)}


def test_fail_detects_first_frame_of_persistent_crossing():
    c = _contract()
    mover = _track("capsule", {f: 296.0 for f in range(80)})
    barrier = _track("yellow bar", _barrier_crossing_at(59))
    r = verify(c, mover, barrier)
    assert r.status == VerificationStatus.FAIL
    assert r.t_fail == 60  # E(59) == 0 is not > threshold 0; first frame with E > 0 is 60
    assert r.violation_run == [60, 61, 62]
    assert r.residual[60] == 5.0 and r.residual[0] == -295.0


def test_threshold_shifts_detection_frame():
    c = _contract(threshold=12)
    mover = _track("capsule", {f: 296.0 for f in range(80)})
    barrier = _track("yellow bar", _barrier_crossing_at(59))
    r = verify(c, mover, barrier)
    assert r.status == VerificationStatus.FAIL and r.t_fail == 62  # E = 5,10,15 -> first > 12 at 62


def test_pass_when_barrier_stays_above_feet_and_coverage_met():
    c = _contract()
    mover = _track("capsule", {f: 296.0 for f in range(80)})
    barrier = _track("yellow bar", {f: min(78 + 5 * f, 283.0) for f in range(80)})
    r = verify(c, mover, barrier)
    assert r.status == VerificationStatus.PASS
    assert r.max_residual == -13.0 and r.margin_px == 13.0 and r.t_fail is None


def test_single_frame_jitter_is_not_a_violation():
    c = _contract(persistence=3)
    mover = _track("capsule", {f: 296.0 for f in range(80)})
    bottoms = {f: 283.0 for f in range(80)}
    bottoms[50] = 300.0  # one-frame spike above the feet
    bottoms[52] = 300.0  # non-consecutive second spike
    r = verify(c, mover, _track("yellow bar", bottoms))
    assert r.status == VerificationStatus.PASS


def test_gap_in_tracking_resets_persistence_run():
    c = _contract(persistence=3)
    mover_b = {f: 296.0 for f in range(80)}
    del mover_b[61]  # untracked frame splits 60,61,62
    barrier = _track("yellow bar", {f: (300.0 if f in (60, 61, 62) else 283.0) for f in range(80)})
    r = verify(c, _track("capsule", mover_b), barrier)
    assert r.status != VerificationStatus.FAIL


def test_missing_coverage_is_inconclusive_never_pass():
    c = _contract(window=(45, 70), min_window=0.9)
    mover = _track("capsule", {f: 296.0 for f in range(80) if not 50 <= f <= 65})  # hole across the window
    barrier = _track("yellow bar", {f: 283.0 for f in range(80)})
    r = verify(c, mover, barrier)
    assert r.status == VerificationStatus.INCONCLUSIVE
    assert any("coverage" in s for s in r.reasons)


def test_low_total_coverage_is_inconclusive():
    c = _contract(min_total=0.6)
    mover = _track("capsule", {f: 296.0 for f in range(40, 80)})  # 50% of frames
    barrier = _track("yellow bar", {f: 283.0 for f in range(80)})
    assert verify(c, mover, barrier).status == VerificationStatus.INCONCLUSIVE


def test_violation_outranks_coverage_gate():
    c = _contract()
    mover = _track("capsule", {f: 296.0 for f in range(55, 80)})  # poor total coverage but crossing well tracked
    barrier = _track("yellow bar", _barrier_crossing_at(59))
    r = verify(c, mover, barrier)
    assert r.status == VerificationStatus.FAIL and r.t_fail == 60


def test_concept_sam_cannot_find_is_inconclusive_never_pass():
    c = _contract()
    empty = Track("capsule", None, 80, (960, 540))
    r = verify(c, empty, _track("yellow bar", {f: 283.0 for f in range(80)}))
    assert r.status == VerificationStatus.INCONCLUSIVE
    assert any("no track for mover concept 'capsule'" in s for s in r.reasons)


def test_absent_track_object_is_error():
    c = _contract()
    r = verify(c, None, _track("yellow bar", {f: 283.0 for f in range(80)}))
    assert r.status == VerificationStatus.ERROR and "mover" in " ".join(r.reasons)


def test_never_reaching_the_barrier_is_inconclusive_not_pass():
    c = _contract()
    mover = _track("capsule", {f: 296.0 for f in range(80)})
    barrier = _track("yellow bar", {f: 150.0 for f in range(80)})  # 146px short, body height is 71px
    r = verify(c, mover, barrier)
    assert r.status == VerificationStatus.INCONCLUSIVE
    assert any("contract not exercised" in s for s in r.reasons)
    assert r.approach["exercised"] is False and r.approach["mover_body_px"] == 71


def test_approach_gate_scales_with_body_height():
    c = _contract()
    mover = _track("capsule", {f: 296.0 for f in range(80)})
    assert verify(c, mover, _track("yellow bar", {f: 225.0 for f in range(80)})).status == VerificationStatus.PASS  # exactly -71
    assert verify(c, mover, _track("yellow bar", {f: 224.0 for f in range(80)})).status == VerificationStatus.INCONCLUSIVE


def test_real_dropped_input_run_no_longer_passes():
    # REAL SAM 3.1 output, tests/fixtures/dropped_input_walk: the input was lost at frame 38, the robot stopped at
    # z=-7.13 about 4.3 m short of the hurdle, and the verifier without the approach gate returned PASS.
    d = Path(__file__).resolve().parents[1] / "fixtures" / "dropped_input_walk"
    meta = json.loads((d / "meta.json").read_text())
    c = _contract(threshold=meta["threshold_px"], persistence=meta["persistence_frames"], window=tuple(meta["critical_window"]),
                  min_window=meta["min_window_coverage"], min_total=meta["min_total_coverage"])
    mover = build_track(meta["mover_concept"], parse_sam_text((d / "mover.txt").read_text()), 80)
    barrier = build_track(meta["barrier_concept"], parse_sam_text((d / "barrier.txt").read_text()), 80)
    r = verify(c, mover, barrier)
    assert r.status == VerificationStatus.INCONCLUSIVE and r.approach["exercised"] is False
    assert r.t_fail is None


def test_contract_freeze_detects_tampering():
    c = _contract()
    assert c.check_frozen()
    c.rule.threshold_px = 19
    assert not c.check_frozen()


def test_rule_hash_is_stable_and_recorded():
    c = _contract()
    r = verify(c, _track("capsule", {f: 296.0 for f in range(80)}), _track("yellow bar", {f: 283.0 for f in range(80)}))
    assert r.rule_sha256 == rule_sha256() and len(r.rule_sha256) == 64
    assert r.contract_sha256 == c.frozen_sha256
