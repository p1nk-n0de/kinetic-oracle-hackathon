"""Offline analysis of saved SAM output against Godot ground truth.

Rule fixed before any SAM output was seen:
  crossing(frame) = bar box bottom y > robot box bottom y
  VIOLATION       = crossing holds for 3 or more consecutive frames
Truth: the robot has crossed once z < -12.0 (hurdle centre), and the repaired
clip must never cross. No threshold here is fitted to SAM output."""
import json, os, re, statistics as st, sys

here = os.path.dirname(os.path.abspath(__file__))
BOX = re.compile(r"(\d+)<\|box;x1=(-?\d+);y1=(-?\d+);x2=(-?\d+);y2=(-?\d+);w=(\d+);h=(\d+)(?:;c=([0-9.]+))?\|>")
FRAME = re.compile(r"<(\d+)f>")


def parse(path):
    frames = {}
    if not os.path.exists(path):
        return frames
    for line in open(path):
        m = FRAME.match(line.strip())
        if not m:
            continue
        recs = [dict(id=int(a), x1=int(b), y1=int(c), x2=int(d), y2=int(e), conf=float(h) if h else None)
                for a, b, c, d, e, f, g, h in BOX.findall(line)]
        frames[int(m.group(1))] = recs
    return frames


def truth(clip):
    rows = json.load(open(os.path.join(here, "clips", clip, "truth.json")))
    return [r["state"]["properties"]["global_position"]["z"] for r in rows]


def best(recs):
    return max(recs, key=lambda r: (r["conf"] or 0, (r["x2"] - r["x1"]) * (r["y2"] - r["y1"]))) if recs else None


def report(clip, rtag, n):
    robot = parse(os.path.join(here, "sam", f"{clip}_{rtag}_{n}.txt"))
    bar = parse(os.path.join(here, "sam", f"{clip}_bar_{n}.txt"))
    z = truth(clip)
    run, first, crossed = 0, None, []
    gaps = {}
    for i in range(len(z)):
        r, b = best(robot.get(i, [])), best(bar.get(i, []))
        if r and b:
            gaps[i] = b["y2"] - r["y2"]
            run = run + 1 if gaps[i] > 0 else 0
            if run >= 3 and first is None:
                first = i - 2
    ids_r = sorted({x["id"] for v in robot.values() for x in v})
    ids_b = sorted({x["id"] for v in bar.values() for x in v})
    multi_r = sum(1 for v in robot.values() if len(v) > 1)
    conf = [x["conf"] for v in robot.values() for x in v if x["conf"] is not None]
    t_cross = next((i for i, q in enumerate(z) if q < -12.0), None)
    print(f"{clip:8s} {rtag:7s} run{n}: robot frames={len(robot)}/80 ids={ids_r[:6]} multi={multi_r} "
          f"bar frames={len(bar)}/80 ids={ids_b[:6]} paired={len(gaps)} "
          f"conf={min(conf) if conf else None}..{max(conf) if conf else None} | VIOLATION={'YES @'+str(first) if first is not None else 'no'} "
          f"truth_cross={t_cross} final_gap={gaps.get(max(gaps)) if gaps else None}")
    return gaps, z


if __name__ == "__main__":
    for rtag in ("box",):
        for clip in ("defect", "repaired"):
            for n in (1, 2):
                report(clip, rtag, n)
