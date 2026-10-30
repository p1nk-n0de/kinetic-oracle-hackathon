"""Developer check, no Meta API: drive a scene with the capture recipe and print
what the engine says happened (position, stop point, what the player hit). This
is how a variant is validated before it is used as evidence.

  .venv/bin/python -m scripts.check_variant_truth <project> [--sidestep 25] [--probe /root/Main/Player]"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from propriosam.artifacts import RUNS_DIR
from propriosam.mcp_adapter import PLAYER, GodotStudio


async def run(project: Path, sidestep: int, walk_ticks: int) -> dict:
    async with GodotStudio(extra_root=RUNS_DIR, log_path=None) as st:
        sid = (await st.call("godot_launch_session", project=str(project), label="variant-check", offscreen=True))["session_id"]
        try:
            await st.call("godot_time_control", session_id=sid, action="pause")
            await st.call("godot_time_control", session_id=sid, action="step_ticks", ticks=40)
            await st.call("godot_send_input", session_id=sid, action="move_left", mode="press", wait=False, observe=False)
            await st.call("godot_time_control", session_id=sid, action="step_ticks", ticks=sidestep)
            await st.call("godot_send_input", session_id=sid, action="move_left", mode="release", wait=False, observe=False)
            await st.call("godot_send_input", session_id=sid, action="move_forward", mode="press", wait=False, observe=False)
            track = []
            for i in range(walk_ticks // 30):
                await st.call("godot_time_control", session_id=sid, action="step_ticks", ticks=30)
                s = await st.call("godot_inspect_runtime", session_id=sid, node_path=PLAYER, properties=["global_position", "velocity"])
                p = s["properties"]
                track.append((round(p["global_position"]["x"], 2), round(p["global_position"]["z"], 2), round(p["velocity"]["z"], 2)))
            phys = await st.call("godot_inspect_physics", session_id=sid, node_path=PLAYER)
            return {"track_x_z_vz_every_30_ticks": track, "physics_at_end": phys}
        finally:
            await st.call("godot_stop_session", session_id=sid)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--sidestep", type=int, default=25)
    ap.add_argument("--walk-ticks", type=int, default=240)
    a = ap.parse_args()
    out = asyncio.run(run(Path(a.project).resolve(), a.sidestep, a.walk_ticks))
    print("track:", out["track_x_z_vz_every_30_ticks"])
    ph = out["physics_at_end"]
    keys = [k for k in ph if k not in ("shapes", "transform")]
    print("physics:", json.dumps({k: ph[k] for k in keys}, default=str)[:900])
    return 0


if __name__ == "__main__":
    sys.exit(main())
