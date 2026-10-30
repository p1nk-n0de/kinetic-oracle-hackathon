"""Lockstep proof clip from a closed-loop bundle, 1080p, with burned-in telemetry
(PIL; this machine's ffmpeg has no drawtext). One panel per pass, all playing the
same 80 frames at half speed. Every number and every quote on screen is read from
the bundle: the verdict comes from the verifier, the claim from the model's closing
text, and the two are shown side by side.

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

W, H, MARGIN, GAP = 1920, 1080, 32, 20
BG, FG, DIM, EDGE = (12, 14, 20), (240, 240, 245), (150, 155, 170), (60, 64, 80)
RED, GREEN, AMBER = (255, 96, 96), (110, 240, 160), (255, 196, 80)
STATUS_COLOUR = {"PASS": GREEN, "FAIL": RED, "INCONCLUSIVE": AMBER}


def font(size: int, bold=False):
    for p in ("/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/Supplemental/Arial.ttf"):
        try:
            return ImageFont.truetype(p, size, index=1 if bold else 0)
        except Exception:
            continue
    return ImageFont.load_default()


def best_bundle() -> Path:
    """The PASS bundle with the most repair turns, latest first."""
    best, key = None, (-1, "")
    for d in sorted(RUNS_DIR.glob("run_*")):
        if (d / "run_manifest.json").exists():
            m = load_manifest(d)
            if m.kind == "closed_loop" and m.final_verdict == "PASS" and m.repair_turns:
                k = (len(m.repair_turns), d.name)
                if k > key:
                    best, key = d, k
    if best is None:
        raise SystemExit("no PASS closed-loop bundle with repair turns under runs/")
    return best


def extract(mp4: Path, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp4), str(out_dir / "f_%03d.png")], check=True)
    return sorted(out_dir.glob("f_*.png"))


def wrap(draw, text: str, f, max_w: int, max_lines: int) -> list[str]:
    words, lines, cur = text.replace("—", "-").split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=f) <= max_w:
            cur = t
        else:
            lines.append(cur)
            cur = w
            if len(lines) == max_lines:
                break
    if len(lines) < max_lines and cur:
        lines.append(cur)
    elif lines:
        while draw.textlength(lines[-1] + " ...", font=f) > max_w and " " in lines[-1]:
            lines[-1] = lines[-1].rsplit(" ", 1)[0]
        lines[-1] += " ..."
    return lines


def centred(draw, text, y, f, colour):
    draw.text(((W - draw.textlength(text, font=f)) / 2, y), text, font=f, fill=colour)


def model_claim(turn) -> str:
    lines = [ln.strip() for ln in (turn.outcome_text or "").splitlines() if ln.strip()]
    if not lines:
        return ""
    last = lines[-1]
    return last.split(":", 1)[1].strip() if last.lower().startswith("why") and ":" in last else last


def short_model(model: str) -> str:
    return {"muse-spark-1.3": "Muse Spark", "muse-wonder-1.0": "Muse Wonder"}.get(model, model)


def status_chips(draw, passes, y, f) -> None:
    """Pass 1 FAIL -> Pass 2 FAIL -> Pass 3 PASS, drawn so no arrow glyph is needed."""
    labels = [f"Pass {v['index']}: {v['status']}" + (f" at frame {v['t_fail']}" if v["t_fail"] is not None else "") for v in passes]
    arrow_w = 70
    total = sum(draw.textlength(t, font=f) for t in labels) + arrow_w * (len(labels) - 1)
    x = (W - total) / 2
    for i, (t, v) in enumerate(zip(labels, passes)):
        draw.text((x, y), t, font=f, fill=STATUS_COLOUR.get(v["status"], FG))
        x += draw.textlength(t, font=f)
        if i < len(labels) - 1:
            mid = y + f.size * 0.6
            draw.line([(x + 14, mid), (x + arrow_w - 20, mid)], fill=DIM, width=4)
            draw.polygon([(x + arrow_w - 14, mid), (x + arrow_w - 28, mid - 10), (x + arrow_w - 28, mid + 10)], fill=DIM)
            x += arrow_w


def mini_chart(draw, x, y, w, h, residual, frame, t_fail, threshold, f) -> None:
    """E(t) up to the current frame, against the violation threshold."""
    lo, hi = -200.0, 260.0
    n = len(residual)
    px = lambda t: x + w * t / (n - 1)  # noqa: E731
    py = lambda e: y + h - h * (min(max(e, lo), hi) - lo) / (hi - lo)  # noqa: E731
    draw.rectangle([x, y, x + w, y + h], outline=EDGE, width=1)
    draw.rectangle([x, y, x + w, py(threshold)], fill=(32, 18, 22))
    draw.line([(x, py(threshold)), (x + w, py(threshold))], fill=(150, 90, 90), width=1)
    draw.text((x + 8, py(threshold) - 22), f"crossing zone: E > {threshold} px", font=f, fill=(190, 120, 120))
    if t_fail is not None and frame >= t_fail:
        draw.line([(px(t_fail), y), (px(t_fail), y + h)], fill=RED, width=2)
    pts = [(px(t), py(e)) for t, e in enumerate(residual[: frame + 1]) if e is not None]
    if len(pts) > 1:
        colour = RED if t_fail is not None and frame >= t_fail else GREEN
        draw.line(pts, fill=colour, width=3)
        draw.ellipse([pts[-1][0] - 5, pts[-1][1] - 5, pts[-1][0] + 5, pts[-1][1] + 5], fill=colour)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", default=None)
    ap.add_argument("--out", default=str(RUNS_DIR / "kinetic_oracle_demo_proof.mp4"))
    ap.add_argument("--fps", type=int, default=20)
    ap.add_argument("--repeat", type=int, default=2, help="frame repeat factor (2 = half speed)")
    ap.add_argument("--title-seconds", type=float, default=3.0)
    ap.add_argument("--hold-seconds", type=float, default=5.0)
    a = ap.parse_args()
    bundle = Path(a.run_dir) if a.run_dir else best_bundle()
    m = load_manifest(bundle)
    contract = json.loads((bundle / m.contract_path).read_text())
    passes = [{"rec": p, "v": json.loads((bundle / p.verification_path).read_text())} for p in m.passes]
    tmp = bundle / "_demo_tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    frames = [extract(bundle / p["rec"].overlay_path, tmp / f"p{i}") for i, p in enumerate(passes)]
    n = min(len(f) for f in frames)
    out_frames = tmp / "out"
    out_frames.mkdir()
    k_panels = len(passes)
    panel_w = (W - 2 * MARGIN - GAP * (k_panels - 1)) // k_panels
    panel_h = panel_w * 9 // 16
    f_big, f_title, f_h, f_cap, f_small = font(62, True), font(54, True), font(26, True), font(24), font(21)
    k = 0

    def emit(img):
        nonlocal k
        img.save(out_frames / f"f_{k:05d}.png")
        k += 1

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    centred(d, "KINETIC-ORACLE (ProprioSAM)", 340, f_title, FG)
    centred(d, "The agent that believed its tool", 420, f_h, AMBER)
    centred(d, "Godot MCP action, then SAM 3.1 tracks, a frozen residual E(t), blind Muse repair, and re-verification", 480, f_cap, DIM)
    centred(d, f"real run {m.run_id}   ·   contract {contract['contract_id']}   ·   the verifier decides, not the tools and not the model", 530, f_small, DIM)
    for _ in range(int(a.title_seconds * a.fps)):
        emit(img)

    y_p = 130
    for i in range(n):
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        d.text((MARGIN, 26), "Same action, every pass. One independent visual verifier.", font=f_h, fill=FG)
        d.text((MARGIN, 66), f"frame {i:02d}/{n - 1}   ·   {contract['mover_concept']} vs {contract['barrier_concept']}   ·   "
                             f"E(t) = y_bottom(barrier) - y_bottom(mover)   ·   violation: E > {contract['rule']['threshold_px']} px "
                             f"for {contract['rule']['persistence_frames']} frames", font=f_small, fill=DIM)
        for j, p in enumerate(passes):
            rec, v = p["rec"], p["v"]
            x = MARGIN + j * (panel_w + GAP)
            img.paste(Image.open(frames[j][i]).convert("RGB").resize((panel_w, panel_h)), (x, y_p))
            d.rectangle([x, y_p, x + panel_w, y_p + panel_h], outline=EDGE, width=2)
            turn = m.repair_turns[j - 1] if j >= 1 and j - 1 < len(m.repair_turns) else None
            y = y_p + panel_h + 14
            head = "PASS 1 · the MCP tool said OK" if j == 0 else f"PASS {rec.index} · after {short_model(turn.model) if turn else 'repair'}'s patch"
            d.text((x, y), head, font=f_h, fill=FG)
            y += 38
            if turn:
                d.text((x, y), f"{short_model(turn.model)}'s claim, verbatim:", font=f_small, fill=DIM)
                y += 28
                for ln in wrap(d, f"\"{model_claim(turn)}\"", f_small, panel_w - 6, 3):
                    d.text((x, y), ln, font=f_small, fill=AMBER)
                    y += 26
            else:
                d.text((x, y), f"{m.passes[0].open_loop.get('tool')} returned no error.", font=f_small, fill=DIM)
                y += 28
                d.text((x, y), "Nothing in that result says what the game did.", font=f_small, fill=DIM)
                y += 54
            e = v["residual"][i] if i < len(v["residual"]) else None
            d.text((x, y_p + panel_h + 196), f"E(t) = {e:+.0f} px" if e is not None else "E(t) = n/a", font=f_cap, fill=FG)
            tf = v.get("t_fail")
            if tf is not None and i >= tf:
                txt, col = f"VERIFIER: FAIL at frame {tf}", RED
            elif tf is None and i == n - 1:
                txt, col = f"VERIFIER: {v['status']}", STATUS_COLOUR.get(v["status"], FG)
            else:
                txt, col = "verifier: measuring", DIM
            d.text((x, y_p + panel_h + 232), txt, font=f_h, fill=col)
            mini_chart(d, x, y_p + panel_h + 276, panel_w, H - 72 - (y_p + panel_h + 276), v["residual"], i, tf,
                       contract["rule"]["threshold_px"], font(17))
        d.text((MARGIN, H - 54), "Verdicts come only from the frozen verifier over SAM 3.1 tracks. MCP status and model text are recorded, never consulted.", font=f_small, fill=DIM)
        for _ in range(a.repeat):
            emit(img)

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    status_chips(d, [{"index": p["rec"].index, "status": p["v"]["status"], "t_fail": p["v"].get("t_fail")} for p in passes], 300, f_big if k_panels == 2 else font(46, True))
    y = 400
    for t in m.repair_turns:
        for pt in t.patches:
            centred(d, f"turn {t.turn}, {short_model(t.model)}: {t.tool_calls} tool calls, patched {pt['path']}", y, f_cap, AMBER)
            y += 40
    y += 16
    last = passes[-1]["v"]
    centred(d, f"final max E(t): {last.get('max_residual'):+.0f} px   ·   coverage {last['coverage']['both_window']:.2f} in window {last['coverage']['critical_window']}", y, f_cap, FG)
    y += 46
    centred(d, f"baseline unchanged: {m.baseline.get('unchanged')}   ·   {len(m.request_ids)} Meta request ids   ·   est. ${m.spend.get('est_cost_usd', 0):.2f}   ·   replays offline with zero API calls", y, f_small, DIM)
    for _ in range(int(a.hold_seconds * a.fps)):
        emit(img)

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(a.fps), "-i", str(out_frames / "f_%05d.png"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-movflags", "+faststart", str(out)], check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"wrote {out} ({k} frames @ {a.fps} fps = {k / a.fps:.1f} s) from {bundle.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
