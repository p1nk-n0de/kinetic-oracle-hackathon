"""SAM 3.1 video output -> per-frame tracks, coverage metrics and overlays.

The wire grammar (dev.meta.ai/docs/sam/reading-segmentation): one line per
frame, `<Nf>` then comma-separated records `id<|box;...|><|mask;...|>`. Mask
payloads are base85 and never contain `|` or `;` (Meta's own parser relies
on the same fact), so `<\\|[^|]*\\|>` matches exactly one token."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

FRAME_RE = re.compile(r"^\s*<(\d+)f>(.*)$")
RECORD_RE = re.compile(r"(\d+)((?:<\|[^|]*\|>)+)")
TOKEN_RE = re.compile(r"<\|([A-Za-z][A-Za-z0-9_.-]*)(?:;([^|]*))?\|>")


@dataclass
class Detection:
    frame: int
    object_id: str
    x1: float
    y1: float
    x2: float
    y2: float
    frame_w: int
    frame_h: int
    confidence: float | None = None
    mask_h: int | None = None
    mask_w: int | None = None
    mask_encoding: str | None = None
    mask_payload: str | None = None

    @property
    def area(self) -> float:
        return max(self.x2 - self.x1 + 1, 0) * max(self.y2 - self.y1 + 1, 0)

    @property
    def cx(self) -> float:
        return (self.x1 + self.x2) / 2

    @property
    def cy(self) -> float:
        return (self.y1 + self.y2) / 2


def _fields(s: str | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in (s or "").split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k] = v
    return out


def parse_sam_text(raw: str) -> dict[int, list[Detection]]:
    """Frame index -> detections. Frames with no visible object have no line."""
    frames: dict[int, list[Detection]] = {}
    for line in raw.splitlines():
        m = FRAME_RE.match(line)
        if not m:
            continue
        fi, rest = int(m.group(1)), m.group(2)
        dets: list[Detection] = []
        for rid, toks in RECORD_RE.findall(rest):
            box, mask = None, None
            for name, fs in TOKEN_RE.findall(toks):
                if name == "box":
                    box = _fields(fs)
                elif name == "mask":
                    mask = _fields(fs)
            if not box:
                continue
            d = Detection(fi, rid, float(box["x1"]), float(box["y1"]), float(box["x2"]), float(box["y2"]),
                          int(box.get("w", 0)), int(box.get("h", 0)),
                          float(box["c"]) if "c" in box else None)
            if mask and "data" in mask:
                try:
                    h, w, enc_payload = mask["data"].split(",", 2)
                    d.mask_h, d.mask_w = int(h), int(w)
                    d.mask_encoding = "lossless" if enc_payload[:1] == "~" else "one_bit"
                    d.mask_payload = enc_payload
                except ValueError:
                    pass
            dets.append(d)
        if dets:
            frames.setdefault(fi, []).extend(dets)
    return frames


def object_summary(frames: dict[int, list[Detection]]) -> dict[str, dict]:
    acc: dict[str, dict] = {}
    for fi, dets in frames.items():
        for d in dets:
            a = acc.setdefault(d.object_id, {"frames": 0, "conf_sum": 0.0, "conf_n": 0, "area_sum": 0.0})
            a["frames"] += 1
            a["area_sum"] += d.area
            if d.confidence is not None:
                a["conf_sum"] += d.confidence
                a["conf_n"] += 1
    return {k: {"frames": v["frames"], "mean_confidence": (v["conf_sum"] / v["conf_n"]) if v["conf_n"] else None,
                "mean_area_px": v["area_sum"] / v["frames"]} for k, v in acc.items()}


def select_object(frames: dict[int, list[Detection]]) -> tuple[str | None, dict]:
    """Deterministic choice when a concept matches several objects: highest
    mean confidence, then largest mean box area, then most frames."""
    summ = object_summary(frames)
    if not summ:
        return None, {"candidates": {}, "rule": "none"}
    best = max(summ, key=lambda k: ((summ[k]["mean_confidence"] or 0.0), summ[k]["mean_area_px"], summ[k]["frames"]))
    return best, {"candidates": summ, "rule": "max(mean_confidence, mean_area_px, frames)", "selected": best}


@dataclass
class TrackPoint:
    frame: int
    x1: float
    y1: float
    x2: float
    y2: float
    cx: float
    cy: float
    bottom: float
    confidence: float | None
    vx: float | None = None  # px per frame, finite difference to the previous tracked frame
    vy: float | None = None
    has_mask: bool = False


@dataclass
class Track:
    concept: str
    object_id: str | None
    frame_count: int
    frame_size: tuple[int, int]
    points: dict[int, TrackPoint] = field(default_factory=dict)
    selection: dict = field(default_factory=dict)

    def coverage(self, window: tuple[int, int] | None = None) -> float:
        lo, hi = window if window else (0, self.frame_count - 1)
        n = hi - lo + 1
        return sum(1 for f in self.points if lo <= f <= hi) / n if n > 0 else 0.0

    def bottom(self, frame: int) -> float | None:
        p = self.points.get(frame)
        return p.bottom if p else None

    def to_json(self) -> dict:
        return {"concept": self.concept, "object_id": self.object_id, "frame_count": self.frame_count,
                "frame_size": list(self.frame_size), "coverage_total": round(self.coverage(), 4),
                "selection": self.selection, "points": [asdict(self.points[f]) for f in sorted(self.points)]}


def build_track(concept: str, frames: dict[int, list[Detection]], frame_count: int,
                frame_size: tuple[int, int] = (960, 540), object_id: str | None = None) -> Track:
    oid, sel = (object_id, {"rule": "given", "selected": object_id}) if object_id else select_object(frames)
    tr = Track(concept, oid, frame_count, frame_size, selection=sel)
    if oid is None:
        return tr
    prev: TrackPoint | None = None
    for fi in sorted(frames):
        if fi >= frame_count:
            continue
        d = next((x for x in frames[fi] if x.object_id == oid), None)
        if not d:
            continue
        p = TrackPoint(fi, d.x1, d.y1, d.x2, d.y2, d.cx, d.cy, d.y2, d.confidence, has_mask=d.mask_payload is not None)
        if prev is not None:
            dt = fi - prev.frame
            p.vx, p.vy = (p.cx - prev.cx) / dt, (p.cy - prev.cy) / dt
        tr.points[fi] = p
        prev = p
    return tr


def decode_mask(det: Detection) -> np.ndarray | None:
    """Boolean raster (mask_h x mask_w) via Meta's official codec; None if undecodable."""
    if not det.mask_payload or not det.mask_h or not det.mask_w:
        return None
    try:
        from meta_sam_parser import SegmentationMask, decode_mask_to_raster
    except Exception:
        return None
    for payload in (det.mask_payload, det.mask_payload[1:]):
        try:
            raw = decode_mask_to_raster(SegmentationMask(encoding=det.mask_encoding, payload=payload,
                                                         width=det.mask_w, height=det.mask_h))
            arr = np.frombuffer(bytes(raw), dtype=np.uint8)
            if arr.size == det.mask_h * det.mask_w:
                return arr.reshape(det.mask_h, det.mask_w) > 0
        except Exception:
            continue
    return None


def _font(size: int):
    for p in ("/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/Supplemental/Arial.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


COLOURS = {"mover": (80, 255, 120), "barrier": (255, 80, 255)}


def render_overlay(frames_dir: Path, out_mp4: Path, detections: dict[str, dict[int, list[Detection]]],
                   tracks: dict[str, Track], residual: list[float | None], status_text_for_frame, *,
                   fps: int = 20, title: str = "") -> dict:
    """Draw SAM masks/boxes/centroids + HUD on every frame, encode with ffmpeg.
    `detections`/`tracks` are keyed by role ('mover', 'barrier')."""
    frames_dir, out_mp4 = Path(frames_dir), Path(out_mp4)
    pngs = sorted(frames_dir.glob("f_*.png"))
    tmp = out_mp4.with_suffix("").with_name(out_mp4.stem + "_frames")
    tmp.mkdir(parents=True, exist_ok=True)
    big, small = _font(26), _font(18)
    masks_drawn, mask_failures = 0, 0
    for i, png in enumerate(pngs):
        im = Image.open(png).convert("RGBA")
        layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
        dr = ImageDraw.Draw(layer)
        for role, tr in tracks.items():
            p = tr.points.get(i)
            if not p:
                continue
            col = COLOURS.get(role, (255, 255, 0))
            det = next((d for d in detections.get(role, {}).get(i, []) if d.object_id == tr.object_id), None)
            m = decode_mask(det) if det else None
            if m is not None:
                bw, bh = int(p.x2 - p.x1 + 1), int(p.y2 - p.y1 + 1)
                mimg = Image.fromarray((m.astype(np.uint8) * 255))
                if mimg.size != (bw, bh):
                    mimg = mimg.resize((max(bw, 1), max(bh, 1)), Image.NEAREST)
                tint = Image.new("RGBA", mimg.size, col + (110,))
                layer.paste(tint, (int(p.x1), int(p.y1)), mimg)
                masks_drawn += 1
            elif det is not None and det.mask_payload:
                mask_failures += 1
            dr.rectangle([p.x1, p.y1, p.x2, p.y2], outline=col + (255,), width=3)
            dr.ellipse([p.cx - 4, p.cy - 4, p.cx + 4, p.cy + 4], fill=col + (255,))
            dr.line([(p.x1 - 12, p.bottom), (p.x2 + 12, p.bottom)], fill=col + (200,), width=2)
            dr.text((p.x1, max(p.y1 - 22, 0)), f"{tr.concept} #{tr.object_id}", font=small, fill=col + (255,))
        e = residual[i] if i < len(residual) else None
        status = status_text_for_frame(i)
        hud = f"frame {i:02d}   E(t) = {e:+.0f} px" if e is not None else f"frame {i:02d}   E(t) = n/a"
        dr.rectangle([0, im.height - 64, im.width, im.height], fill=(0, 0, 0, 170))
        dr.text((16, im.height - 58), hud, font=big, fill=(255, 255, 255, 255))
        colour = (255, 90, 90, 255) if status.startswith("VIOLATION") else (120, 255, 160, 255) if status.startswith("PASS") else (220, 220, 220, 255)
        dr.text((im.width - 16 - dr.textlength(status, font=big), im.height - 58), status, font=big, fill=colour)
        if title:
            dr.rectangle([0, 0, im.width, 34], fill=(0, 0, 0, 150))
            dr.text((16, 6), title, font=small, fill=(255, 255, 255, 255))
        Image.alpha_composite(im, layer).convert("RGB").save(tmp / f"f_{i:03d}.png")
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", str(tmp / "f_%03d.png"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
                    "-movflags", "+faststart", str(out_mp4)], check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    return {"frames": len(pngs), "masks_drawn": masks_drawn, "mask_decode_failures": mask_failures, "path": str(out_mp4)}


def encode_frames(frames_dir: Path, out_mp4: Path, fps: int = 20) -> Path:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", str(Path(frames_dir) / "f_%03d.png"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
                    "-movflags", "+faststart", str(out_mp4)], check=True)
    return Path(out_mp4)


def save_tracks(path: Path, tracks: dict[str, Track]) -> None:
    Path(path).write_text(json.dumps({k: v.to_json() for k, v in tracks.items()}, indent=1, sort_keys=True))
