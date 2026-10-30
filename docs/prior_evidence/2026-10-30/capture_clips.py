"""Capture tick-locked frames of the defect fixture and today's repaired copy
through the real MCP surface, with the true Player state recorded per frame.
Repeats the failing scenario's inputs: settle 40, sidestep 25, walk 240 ticks."""
import asyncio, json, os, shutil, sys
from pathlib import Path

REPO = Path.home() / "Projects/<redacted:studio>-godot-studio"
sys.path.insert(0, str(REPO / "scripts"))
from mcp_client import studio_client, payload, REPO as RR

OUT = Path(sys.argv[1])
CLIPS = {
    "defect": str(RR / "tests/fixtures/pg_defect_hurdle"),
    "repaired": str(RR / "artifacts/working_copies/pg_defect_hurdle-repair-20261030-112402"),
}
EVERY, TOTAL = 3, 240


async def call(s, name, **kw):
    return payload(await s.call_tool(name, kw))


async def clip(s, label, project):
    d = OUT / label
    d.mkdir(parents=True, exist_ok=True)
    sid = (await call(s, "godot_launch_session", project=project, label=f"sam-{label}", offscreen=True))["session_id"]
    try:
        await call(s, "godot_time_control", session_id=sid, action="pause")
        await call(s, "godot_time_control", session_id=sid, action="step_ticks", ticks=40)
        await call(s, "godot_send_input", session_id=sid, action="move_left", mode="press", wait=False, observe=False)
        await call(s, "godot_time_control", session_id=sid, action="step_ticks", ticks=25)
        await call(s, "godot_send_input", session_id=sid, action="move_left", mode="release", wait=False, observe=False)
        await call(s, "godot_send_input", session_id=sid, action="move_forward", mode="press", wait=False, observe=False)
        rows = []
        for i in range(TOTAL // EVERY):
            await call(s, "godot_time_control", session_id=sid, action="step_ticks", ticks=EVERY)
            st = await call(s, "godot_inspect_runtime", session_id=sid, node_path="/root/Main/Player",
                            properties=["global_position", "velocity"])
            fr = await call(s, "godot_capture_frame", session_id=sid, label=f"f{i:03d}", max_width=960, return_image=False)
            if i == 0:
                print(label, "state sample:", json.dumps(st)[:400], flush=True)
                print(label, "frame sample:", json.dumps(fr)[:400], flush=True)
            src = fr.get("path") or fr.get("image_path") or fr.get("file")
            shutil.copy(src, d / f"f_{i:03d}.png")
            rows.append({"i": i, "tick": (i + 1) * EVERY, "state": st, "frame_meta": {k: v for k, v in fr.items() if k != "image"}})
        (d / "truth.json").write_text(json.dumps(rows, indent=0, default=str))
        print(label, "captured", len(rows), "frames", flush=True)
    finally:
        await call(s, "godot_stop_session", session_id=sid)


async def main():
    async with studio_client() as s:
        for label, project in CLIPS.items():
            await clip(s, label, project)


asyncio.run(main())
