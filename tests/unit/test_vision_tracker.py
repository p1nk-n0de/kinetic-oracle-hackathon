"""SAM 3.1 wire-text parsing and track building on SYNTHETIC_UNIT_TEST_FIXTURE data (no API, no Godot).

Every string below is hand-written to exercise the grammar documented in propriosam/vision_tracker.py:
one `<Nf>` line per frame, comma-separated records `id<|box;...|><|mask;...|>`. None of it is real SAM output."""
from __future__ import annotations

import math

import pytest

from propriosam.vision_tracker import (Detection, Track, build_track, object_summary, parse_sam_text, select_object)

W, H = 960, 540


def box(x1, y1, x2, y2, c=None, extra=""):
    """SYNTHETIC_UNIT_TEST_FIXTURE: one `<|box;...|>` token in SAM's field syntax."""
    s = f"x1={x1};y1={y1};x2={x2};y2={y2};w={W};h={H}"
    if c is not None:
        s += f";c={c}"
    return f"<|box;{s}{extra}|>"


def mask(data: str, c=None):
    """SYNTHETIC_UNIT_TEST_FIXTURE: one `<|mask;...|>` token (`data=H,W,payload`)."""
    cs = f";c={c}" if c is not None else ""
    return f"<|mask;x=0;y=0{cs};data={data}|>"


def line(frame: int, *records: str) -> str:
    return f"<{frame}f>" + ",".join(records)


# --------------------------------------------------------------------------------------------- parse_sam_text

def test_frame_markers_that_skip_frames_leave_gaps():
    # SYNTHETIC_UNIT_TEST_FIXTURE: frames 0, 1 and 5 present; 2-4 have no line at all (object not visible)
    raw = "\n".join([line(0, "0" + box(10, 20, 30, 60, 0.9)),
                     line(1, "0" + box(11, 20, 31, 60, 0.9)),
                     line(5, "0" + box(15, 20, 35, 60, 0.9))])
    frames = parse_sam_text(raw)
    assert sorted(frames) == [0, 1, 5]
    assert all(isinstance(d, Detection) for ds in frames.values() for d in ds)
    tr = build_track("capsule", frames, frame_count=8, frame_size=(W, H))
    assert sorted(tr.points) == [0, 1, 5]
    assert tr.coverage() == pytest.approx(3 / 8)
    assert tr.coverage((4, 7)) == pytest.approx(1 / 4)
    assert tr.bottom(3) is None and tr.bottom(5) == 60.0


def test_non_frame_lines_and_boxless_records_are_ignored():
    # SYNTHETIC_UNIT_TEST_FIXTURE: chatter, blank lines, a frame with only a mask token (no box) and a frame-less token
    raw = "\n".join(["Here are the tracks:", "", line(2, "7" + mask("4,4,!abcd")), "  " + line(3, "7" + box(0, 0, 9, 9)),
                     "<|box;x1=1;y1=1;x2=2;y2=2|>"])
    frames = parse_sam_text(raw)
    assert sorted(frames) == [3]  # frame 2 had no box -> no detection -> no entry; leading whitespace is tolerated
    assert frames[3][0].object_id == "7" and frames[3][0].mask_payload is None


def test_multiple_object_ids_per_frame():
    # SYNTHETIC_UNIT_TEST_FIXTURE: two objects on frame 4 (the hurdle and the far pressure plate both match "yellow bar")
    raw = line(4, "0" + box(400, 100, 560, 130, 0.91), "1" + box(470, 40, 500, 48, 0.72))
    frames = parse_sam_text(raw)
    assert [d.object_id for d in frames[4]] == ["0", "1"]
    a, b = frames[4]
    assert (a.x1, a.y1, a.x2, a.y2) == (400.0, 100.0, 560.0, 130.0) and (a.frame_w, a.frame_h) == (W, H)
    assert a.area == 161 * 31 and b.area == 31 * 9
    assert a.cx == 480.0 and a.cy == 115.0
    # build_track keeps only the selected id's detection per frame
    tr = build_track("yellow bar", frames, frame_count=10, frame_size=(W, H))
    assert tr.object_id == "0" and tr.points[4].x1 == 400.0 and tr.points[4].bottom == 130.0


def test_confidence_field_is_parsed_and_optional():
    # SYNTHETIC_UNIT_TEST_FIXTURE: `c=` present on frame 0, absent on frame 1
    raw = "\n".join([line(0, "0" + box(1, 2, 3, 4, 0.7538461089134216)), line(1, "0" + box(1, 2, 3, 4))])
    frames = parse_sam_text(raw)
    assert frames[0][0].confidence == pytest.approx(0.7538461089134216)
    assert frames[1][0].confidence is None
    summ = object_summary(frames)
    assert summ["0"]["frames"] == 2 and summ["0"]["mean_confidence"] == pytest.approx(0.7538461089134216)
    tr = build_track("capsule", frames, 2, (W, H))
    assert tr.points[0].confidence == pytest.approx(0.7538461089134216) and tr.points[1].confidence is None


def test_mask_data_parsing_one_bit_lossless_and_malformed():
    # SYNTHETIC_UNIT_TEST_FIXTURE payloads: one_bit payloads start with '!', lossless with '~'
    raw = "\n".join([line(0, "0" + box(459, 231, 501, 297, 0.75) + mask("67,43,!!!!!QFFb=IPLbosU", 0.75)),
                     line(1, "0" + box(459, 231, 501, 297, 0.75) + mask("12,34,~zz9=lossless", 0.75)),
                     line(2, "0" + box(459, 231, 501, 297, 0.75) + mask("not-a-triplet", 0.75)),
                     line(3, "0" + box(459, 231, 501, 297, 0.75))])
    frames = parse_sam_text(raw)
    d0, d1, d2, d3 = (frames[i][0] for i in range(4))
    assert (d0.mask_h, d0.mask_w, d0.mask_encoding, d0.mask_payload) == (67, 43, "one_bit", "!!!!!QFFb=IPLbosU")
    assert (d1.mask_h, d1.mask_w, d1.mask_encoding, d1.mask_payload) == (12, 34, "lossless", "~zz9=lossless")
    assert d2.mask_payload is None and d2.mask_h is None  # malformed data field is tolerated, box still used
    assert d3.mask_payload is None
    tr = build_track("capsule", frames, 4, (W, H))
    assert [tr.points[i].has_mask for i in range(4)] == [True, True, False, False]


def test_mask_payload_may_contain_commas_and_equals():
    # SYNTHETIC_UNIT_TEST_FIXTURE: base85 may contain ',' and '=' — split must be limited to the first two commas
    raw = line(0, "0" + box(0, 0, 10, 10, 0.5) + mask("5,6,!a,b=c,d", 0.5))
    d = parse_sam_text(raw)[0][0]
    assert (d.mask_h, d.mask_w, d.mask_payload) == (5, 6, "!a,b=c,d")


# --------------------------------------------------------------------------------------------- select_object

def _frames(spec: dict[str, list[tuple[int, float, float | None]]]) -> dict[int, list[Detection]]:
    """SYNTHETIC_UNIT_TEST_FIXTURE: {object_id: [(frame, side_px, confidence), ...]} -> square boxes of that side."""
    out: dict[int, list[Detection]] = {}
    for oid, items in spec.items():
        for f, side, c in items:
            out.setdefault(f, []).append(Detection(f, oid, 0.0, 0.0, side - 1, side - 1, W, H, c))
    return {k: out[k] for k in sorted(out)}


def test_select_object_prefers_mean_confidence_over_area_and_frames():
    frames = _frames({"0": [(f, 20, 0.95) for f in range(3)],            # small, few frames, confident
                      "1": [(f, 200, 0.60) for f in range(10)]})         # big, many frames, less confident
    oid, sel = select_object(frames)
    assert oid == "0" and sel["selected"] == "0"
    assert sel["rule"] == "max(mean_confidence, mean_area_px, frames)"
    assert set(sel["candidates"]) == {"0", "1"}


def test_select_object_ties_on_confidence_break_by_area_then_frames():
    # (0.75 is exactly representable, so the per-object confidence means tie exactly regardless of frame count)
    # equal confidence -> larger mean area wins
    frames = _frames({"0": [(f, 50, 0.75) for f in range(10)], "1": [(f, 60, 0.75) for f in range(4)]})
    assert select_object(frames)[0] == "1"
    # equal confidence and equal area -> more frames wins
    frames = _frames({"0": [(f, 50, 0.75) for f in range(4)], "1": [(f, 50, 0.75) for f in range(5)]})
    assert select_object(frames)[0] == "1"


def test_select_object_without_confidence_falls_back_to_area():
    frames = _frames({"0": [(f, 30, None) for f in range(5)], "1": [(f, 90, None) for f in range(2)]})
    oid, sel = select_object(frames)
    assert oid == "1" and sel["candidates"]["1"]["mean_confidence"] is None


def test_select_object_empty_and_given_id():
    assert select_object({}) == (None, {"candidates": {}, "rule": "none"})
    tr = build_track("capsule", {}, 80, (W, H))
    assert tr.object_id is None and tr.points == {} and tr.coverage() == 0.0
    frames = _frames({"0": [(0, 10, 0.9)], "1": [(0, 20, 0.1)]})
    tr = build_track("capsule", frames, 80, (W, H), object_id="1")
    assert tr.object_id == "1" and tr.selection == {"rule": "given", "selected": "1"} and tr.points[0].x2 == 19.0


# --------------------------------------------------------------------------------------------- build_track

def test_velocity_is_a_finite_difference_across_gaps():
    # SYNTHETIC_UNIT_TEST_FIXTURE: tracked on frames 10, 11 and 14 (12-13 missing); 40x60 boxes
    def rec(cx, cy):
        return "0" + box(cx - 20, cy - 30, cx + 20, cy + 30, 0.8)
    raw = "\n".join([line(10, rec(100, 50)), line(11, rec(104, 52)), line(14, rec(134, 58))])
    tr = build_track("capsule", parse_sam_text(raw), 80, (W, H))
    p10, p11, p14 = tr.points[10], tr.points[11], tr.points[14]
    assert p10.vx is None and p10.vy is None                       # no previous tracked frame
    assert p11.vx == pytest.approx(4.0) and p11.vy == pytest.approx(2.0)  # dt = 1
    assert p14.vx == pytest.approx((134 - 104) / 3) and p14.vy == pytest.approx((58 - 52) / 3)  # dt = 3 across the gap
    assert p14.bottom == p14.y2 == 88.0 and p14.cx == 134.0 and p14.cy == 58.0
    assert 12 not in tr.points and 13 not in tr.points


def test_frames_at_or_beyond_frame_count_are_dropped():
    raw = "\n".join([line(79, "0" + box(0, 0, 9, 9, 0.9)), line(80, "0" + box(0, 0, 9, 9, 0.9)), line(200, "0" + box(0, 0, 9, 9, 0.9))])
    tr = build_track("capsule", parse_sam_text(raw), 80, (W, H))
    assert sorted(tr.points) == [79]


def test_track_to_json_shape_matches_bundle_tracks_json():
    raw = "\n".join([line(1, "0" + box(10, 10, 20, 30, 0.9) + mask("3,3,!abc", 0.9)), line(0, "0" + box(10, 10, 20, 30, 0.9))])
    tr = build_track("capsule", parse_sam_text(raw), 4, (W, H))
    j = tr.to_json()
    assert j["concept"] == "capsule" and j["object_id"] == "0" and j["frame_count"] == 4 and j["frame_size"] == [W, H]
    assert j["coverage_total"] == 0.5 and [p["frame"] for p in j["points"]] == [0, 1]  # points sorted by frame
    assert set(j["points"][0]) == {"frame", "x1", "y1", "x2", "y2", "cx", "cy", "bottom", "confidence", "vx", "vy", "has_mask"}
    assert j["points"][1]["has_mask"] is True and j["points"][0]["has_mask"] is False
    assert isinstance(tr, Track) and math.isclose(j["points"][1]["bottom"], 30.0)
