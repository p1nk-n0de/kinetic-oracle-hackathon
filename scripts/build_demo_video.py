"""Side-by-side 1080p proof clip from a closed-loop bundle, with burned-in
telemetry captions (PIL; this machine's ffmpeg has no drawtext).

Left: pass 1 (the agent's tool said OK; SAM 3.1 finds the violation).
Right: the last pass (after Muse's repair via the Godot MCP; SAM 3.1 verifies).
Both play in lockstep at half speed, preceded by a title card and followed by
a verdict hold. Every number on screen is read from the bundle.

  .venv/bin/python -m scripts.build_demo_video [--run-dir runs/<id>] [--out runs/kinetic_oracle_demo_proof.mp4]"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from propriosam.artifacts import RUNS_DIR, load_manifest

W, H = 1920, 1080
PANEL_W, PANEL_H = 928, 522
BG, FG, DIM = (12, 14, 20), (240, 240, 245), (150, 155, 170)
RED, GREEN, AMBER = (255, 96, 96), (110, 240, 160), (255, 196, 80)


def font(size: int, bold=False):
    for p in ("/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/Supplemental/Arial.ttf"):
        try:
            return ImageFont.truetype(p, size, index=1 if bold else 0)
        except Exception:
            continue
    return ImageFont.load_default()


def latest_pass_bundle() -> Path:
    best = None
    for d in sorted(RUNS_DIR.glob("run_*")):
        if (d / "run_manifest.json").exists():
            m = load_manifest(d)
            if m.kind == "closed_loop" and m.final_verdict == "PASS" and m.repair_turns:
                best = d
    if best is None:
        raise SystemExit("no PASS closed-loop bundle with repair turns under runs/")
    return best


def extract(mp4: Path, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp4), str(out_dir / "f_%03d.png")], check=True)
    return sorted(out_dir.glob("f_*.png"))


def card(draw, text_lines, y0, fonts, colours):
    y = y0
    for t, f, c in zip(text_lines, fonts, colours):
        w = draw.textlength(t, font=f)
        draw.text(((W - w) / 2, y), t, font=f, fill=c)
        y += f.size + 18
    return y


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", default=None)
    ap.add_argument("--out", default=str(RUNS_DIR / "kinetic_oracle_demo_proof.mp4"))
    ap.add_argument("--fps", type=int, default=20)
    ap.add_argument("--repeat", type=int, default=2, help="frame repeat factor (2 = half speed)")
    ap.add_argument("--title-seconds", type=float, default=2.5)
    ap.add_argument("--hold-seconds", type=float, default=3.0)
    a = ap.parse_args()
    bundle = Path(a.run_dir) if a.run_dir else latest_pass_bundle()
    m = load_manifest(bundle)
    contract = json.loads((bundle / m.contract_path).read_text())
    p1, pl = m.passes[0], m.passes[-1]
    v1 = json.loads((bundle / p1.verification_path).read_text())
    vl = json.loads((bundle / pl.verification_path).read_text())
    turn = m.repair_turns[-1] if m.repair_turns else None
    tmp = bundle / "_demo_tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    left = extract(bundle / p1.overlay_path, tmp / "left")
    right = extract(bundle / pl.overlay_path, tmp / "right")
    n = min(len(left), len(right))
    frames_dir = tmp / "out"
    frames_dir.mkdir()
    f_title, f_h, f_cap, f_small, f_big = font(54, True), font(30, True), font(26), font(22), font(64, True)
    k = 0

    def emit(img):
        nonlocal k
        img.save(frames_dir / f"f_{k:05d}.png"); k += 1

    # title card
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    card(d, ["KINETIC-ORACLE (ProprioSAM)", "The agent that believed its tool",
             f"Godot MCP action  >>  SAM 3.1 tracks  >>  frozen residual E(t)  >>  Muse Spark blind repair  >>  re-verified",
             f"run {m.run_id}   ·   contract {contract['contract_id']}   ·   rule: {contract['rule']['definition'][:70]}…"],
         330, [f_title, f_h, f_cap, f_small], [FG, AMBER, DIM, DIM])
    for _ in range(int(a.title_seconds * a.fps)):
        emit(img)
    # lockstep playback
    x_l, x_r, y_p = 32, W - 32 - PANEL_W, 150
    for i in range(n):
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        d.text((32, 28), "KINETIC-ORACLE — same action, two passes, one independent visual verifier", font=f_h, fill=FG)
        d.text((32, 72), f"frame {i:02d}/{n - 1}   ·   {contract['mover_concept']} vs {contract['barrier_concept']}   ·   E(t) = y_bottom(barrier) − y_bottom(mover)   ·   threshold {contract['rule']['threshold_px']} px, persistence {contract['rule']['persistence_frames']}", font=f_small, fill=DIM)
        img.paste(Image.open(left[i]).convert("RGB").resize((PANEL_W, PANEL_H)), (x_l, y_p))
        img.paste(Image.open(right[i]).convert("RGB").resize((PANEL_W, PANEL_H)), (x_r, y_p))
        d.rectangle([x_l, y_p, x_l + PANEL_W, y_p + PANEL_H], outline=(60, 64, 80), width=2)
        d.rectangle([x_r, y_p, x_r + PANEL_W, y_p + PANEL_H], outline=(60, 64, 80), width=2)
        e1, el = v1["residual"][i] if i < len(v1["residual"]) else None, vl["residual"][i] if i < len(vl["residual"]) else None
        tf = v1.get("t_fail")
        left_status = (f"VERIFIER: FAIL — violation since frame {tf}" if tf is not None and i >= tf else "verifier: tracking…")
        right_status = f"VERIFIER: {vl['status']}" if i == n - 1 else "verifier: tracking…"
        d.text((x_l, y_p + PANEL_H + 16), "PASS 1 · open loop · MCP tool returned OK", font=f_h, fill=FG)
        d.text((x_l, y_p + PANEL_H + 56), f"E(t) = {e1:+.0f} px" if e1 is not None else "E(t) = n/a", font=f_cap, fill=FG)
        d.text((x_l, y_p + PANEL_H + 92), left_status, font=f_cap, fill=RED if "FAIL" in left_status else DIM)
        rl = f"PASS {pl.index} · after {turn.model if turn else '-'} repair via Godot MCP ({len(turn.patches) if turn else 0} patch)"
        d.text((x_r, y_p + PANEL_H + 16), rl, font=f_h, fill=FG)
        d.text((x_r, y_p + PANEL_H + 56), f"E(t) = {el:+.0f} px" if el is not None else "E(t) = n/a", font=f_cap, fill=FG)
        d.text((x_r, y_p + PANEL_H + 92), right_status, font=f_cap, fill=GREEN if "PASS" in right_status else DIM)
        d.text((32, H - 60), "Verdicts come only from the frozen verifier over SAM 3.1 tracks. MCP status and model text are recorded, never consulted. "
                             f"Muse saw numbers and tools only: banned-term screen found {len(turn.anti_cheat.get('banned_terms_found', [])) if turn else 0} terms.", font=f_small, fill=DIM)
        for _ in range(a.repeat):
            emit(img)
    # verdict hold
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    patch = turn.patches[0] if turn and turn.patches else None
    card(d, ["Pass 1: FAIL at frame %s   >>   Pass %d: %s" % (v1.get("t_fail"), pl.index, vl["status"]),
             f"max E(t): {v1.get('max_residual'):+.0f} px  >>  {vl.get('max_residual'):+.0f} px     ·     coverage {vl['coverage']['both_window']:.2f} in window {vl['coverage']['critical_window']}",
             f"Muse patch: {patch['path']}   {patch['find'][-12:]}  >>  {patch['replace'][-12:]}" if patch else "no patch",
             f"baseline unchanged: {m.baseline.get('unchanged')}   ·   {len(m.request_ids)} Meta request ids   ·   est. ${m.spend.get('est_cost_usd', 0):.3f}   ·   offline-replayable bundle"],
         360, [f_big, f_h, f_cap, f_small], [GREEN if vl["status"] == "PASS" else RED, FG, AMBER, DIM])
    for _ in range(int(a.hold_seconds * a.fps)):
        emit(img)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(a.fps), "-i", str(frames_dir / "f_%05d.png"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-movflags", "+faststart", str(out)], check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"wrote {out} ({k} frames @ {a.fps} fps = {k / a.fps:.1f} s) from {bundle.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
