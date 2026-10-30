"""Safe working-copy manager + narrow allowlisted bridge to the existing Godot
MCP server (godot-studio, pre-existing infrastructure).

* The baseline project is copied into `runs/<run_id>/workspace/<name>/` and its
  tree hash must equal the baseline's before anything runs. The baseline is
  never written. The spawned MCP server gets `GODOT_STUDIO_EXTRA_ROOT=<runs dir>` so the
  copy is a launchable project root.
* `capture_clip` is the tick-locked recipe that produced the prior evidence:
  settle, sidestep, hold forward, capture one real rendered frame every 3
  physics ticks (80 frames) while recording the player's true state to a
  *hidden* file the verifier and Muse never see.
* `DiagnosisTools` is the only surface Muse gets: live read-only inspection,
  real input, listing/reading an allowlist of source files, and a single
  bounded `patch_source` tool. No shell, no arbitrary MCP access."""
from __future__ import annotations

import asyncio
import difflib
import json
import os
import shutil
import time
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .artifacts import scrub, tree_sha256, write_json
from .meta_client import utc_now
from .vision_tracker import encode_frames

UV = "uv"
STUDIO = Path("~/Projects/godot-studio").expanduser()
SERVER = [UV, "run", "--directory", str(STUDIO), "godot-studio-mcp"]
PLAYER = "/root/Main/Player"


class ToolError(RuntimeError):
    pass


def _unwrap(result) -> dict:
    is_err = bool(getattr(result, "isError", None) or getattr(result, "is_error", False))
    sc = getattr(result, "structuredContent", None) or getattr(result, "structured_content", None)
    texts = [c.text for c in (getattr(result, "content", None) or []) if getattr(c, "type", "") == "text"]
    if is_err:
        raise ToolError(" ".join(texts)[:2000] or "tool error")
    if isinstance(sc, dict):
        return sc.get("result", sc) if set(sc) == {"result"} else sc
    out = []
    for t in texts:
        try:
            out.append(json.loads(t))
        except json.JSONDecodeError:
            out.append(t)
    return out[0] if len(out) == 1 else {"items": out}


class GodotStudio:
    """One MCP stdio connection to the Godot studio server, with a call log."""

    def __init__(self, extra_root: Path, log_path: Path | None = None, rpc_timeout_s: float = 90.0):
        self.extra_root, self.log_path, self.rpc_timeout_s = Path(extra_root), log_path, rpc_timeout_s
        self._cm = self._session_cm = None
        self.session: ClientSession | None = None
        self.calls = 0

    async def __aenter__(self):
        env = {k: v for k, v in os.environ.items() if k not in ("MODEL_API_KEY", "META_API_KEY")}
        env["GODOT_STUDIO_EXTRA_ROOT"] = str(self.extra_root)
        params = StdioServerParameters(command=SERVER[0], args=SERVER[1:], env=env, cwd=str(STUDIO))
        self._cm = stdio_client(params)
        read, write = await self._cm.__aenter__()
        self._session_cm = ClientSession(read, write)
        self.session = await self._session_cm.__aenter__()
        await self.session.initialize()
        return self

    async def __aexit__(self, *exc):
        try:
            if self._session_cm:
                await self._session_cm.__aexit__(*exc)
        finally:
            if self._cm:
                await self._cm.__aexit__(*exc)

    async def call(self, name: str, **args) -> dict:
        t0 = time.time()
        rec = {"ts": utc_now(), "tool": name, "args": args}
        try:
            res = await asyncio.wait_for(self.session.call_tool(name, args), timeout=self.rpc_timeout_s)
            out = _unwrap(res)
            rec.update(ok=True, latency_s=round(time.time() - t0, 3), result_preview=json.dumps(out, default=str)[:400])
            return out
        except Exception as e:
            rec.update(ok=False, latency_s=round(time.time() - t0, 3), error=str(e)[:600])
            raise
        finally:
            self.calls += 1
            if self.log_path:
                with open(self.log_path, "a") as f:
                    f.write(json.dumps(scrub(json.loads(json.dumps(rec, default=str)))) + "\n")


# ----------------------------------------------------------------------------- working copy
def stage_working_copy(baseline: Path, workspace_dir: Path, name: str = "hurdle_scene") -> dict:
    baseline, dst = Path(baseline), Path(workspace_dir) / name
    if dst.exists():
        shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(baseline, dst, symlinks=False)
    base_sha, n = tree_sha256(baseline)
    copy_sha, n2 = tree_sha256(dst)
    return {"path": str(dst), "name": name, "baseline_tree_sha256": base_sha, "staged_tree_sha256": copy_sha,
            "baseline_match_at_stage": base_sha == copy_sha, "files": n2, "staged_at": utc_now()}


# ----------------------------------------------------------------------------- capture
async def capture_clip(studio: GodotStudio, project: Path, out_dir: Path, *, label: str, frame_count: int = 80,
                       every_ticks: int = 3, settle_ticks: int = 40, sidestep_ticks: int = 25, fps: int = 20,
                       max_width: int = 960, timeout_s: float = 30.0) -> dict:
    out_dir = Path(out_dir)
    frames = out_dir / "frames"
    frames.mkdir(parents=True, exist_ok=True)
    t_start = time.time()
    launch = await studio.call("godot_launch_session", project=str(project), label=label, offscreen=True)
    sid = launch["session_id"]
    rows: list[dict] = []
    open_loop: dict = {}

    async def body():
        await studio.call("godot_time_control", session_id=sid, action="pause")
        await studio.call("godot_time_control", session_id=sid, action="step_ticks", ticks=settle_ticks)
        await studio.call("godot_send_input", session_id=sid, action="move_left", mode="press", wait=False, observe=False)
        await studio.call("godot_time_control", session_id=sid, action="step_ticks", ticks=sidestep_ticks)
        await studio.call("godot_send_input", session_id=sid, action="move_left", mode="release", wait=False, observe=False)
        args = dict(session_id=sid, action="move_forward", mode="press", wait=False, observe=False)
        walk = await studio.call("godot_send_input", **args)
        open_loop.update({"tool": "godot_send_input", "args": {k: v for k, v in args.items() if k != "session_id"},
                          "result": walk, "mcp_is_error": False,
                          "note": "The MCP tool reports success. Nothing in this result says whether the hurdle "
                                  "stopped the player; only the rendered clip can."})
        for i in range(frame_count):
            await studio.call("godot_time_control", session_id=sid, action="step_ticks", ticks=every_ticks)
            st = await studio.call("godot_inspect_runtime", session_id=sid, node_path=PLAYER,
                                   properties=["global_position", "velocity"])
            fr = await studio.call("godot_capture_frame", session_id=sid, label=f"f{i:03d}", max_width=max_width,
                                   return_image=False)
            shutil.copy(fr["path"], frames / f"f_{i:03d}.png")
            rows.append({"frame": i, "tick_offset": (i + 1) * every_ticks, "game_tick": fr.get("game_tick"),
                         "physics_frame": fr.get("physics_frame"), "player": st.get("properties")})

    try:
        await asyncio.wait_for(body(), timeout=timeout_s)
    finally:
        try:
            await studio.call("godot_stop_session", session_id=sid)
        except Exception:
            pass
    if len(rows) != frame_count:
        raise RuntimeError(f"capture incomplete: {len(rows)}/{frame_count} frames within {timeout_s}s")
    truth = write_json(out_dir / "truth_hidden.json",
                       {"note": "Ground truth from the engine for evaluation only. Never shown to any model and never "
                                "read by the verifier.", "project": str(project), "rows": rows})
    clip = encode_frames(frames, out_dir / "clip.mp4", fps=fps)
    capture = {"session_id": sid, "label": label, "frame_count": frame_count, "every_ticks": every_ticks,
               "settle_ticks": settle_ticks, "sidestep_ticks": sidestep_ticks, "fps": fps, "max_width": max_width,
               "duration_s": round(time.time() - t_start, 2), "launch": {k: launch.get(k) for k in ("pid", "port", "window", "resolution") if k in launch}}
    return {"clip": clip, "frames_dir": frames, "truth_hidden": truth, "open_loop": open_loop, "capture": capture}


# ----------------------------------------------------------------------------- Muse's tool surface
TOOL_SPECS = [
    {"type": "function", "name": "inspect_scene",
     "description": "Live read-only game state. Without node_path: the watch digest of every instrumented node "
                    "(player position/velocity/zone, HUD, doors, beacon) plus recent gameplay events. With node_path "
                    "(e.g. /root/Main/Player): the listed properties of that node.",
     "parameters": {"type": "object", "properties": {"node_path": {"type": "string"},
                                                     "properties": {"type": "array", "items": {"type": "string"}}}}},
    {"type": "function", "name": "inspect_physics",
     "description": "Physics diagnostics for one node: transform, collision layer and mask bits, collision shapes "
                    "with world AABB, CharacterBody velocity / floor / wall / slide collisions, area overlaps.",
     "parameters": {"type": "object", "properties": {"node_path": {"type": "string"}}, "required": ["node_path"]}},
    {"type": "function", "name": "drive",
     "description": "Deliver real gameplay input to the running game and observe the player after each step. "
                    "steps: list of {\"input\": one of move_forward|move_back|move_left|move_right|jump, \"ticks\": N} "
                    "or {\"wait_ticks\": N}. The game keeps running between calls.",
     "parameters": {"type": "object", "properties": {"steps": {"type": "array", "items": {"type": "object"}}},
                    "required": ["steps"]}},
    {"type": "function", "name": "list_source_files",
     "description": "List the project's GDScript and scene files (relative paths).", "parameters": {"type": "object", "properties": {}}},
    {"type": "function", "name": "read_source",
     "description": "Read one source file by relative path (from list_source_files).",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"type": "function", "name": "patch_source",
     "description": "Apply ONE minimal textual patch to a source file in the working copy: `find` must occur exactly "
                    "once and is replaced by `replace`. State the engineering reason. After your turn the patched game "
                    "is relaunched and re-measured by the independent visual verifier; you do not get to declare success.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "find": {"type": "string"},
                                                     "replace": {"type": "string"}, "reason": {"type": "string"}},
                    "required": ["path", "find", "replace", "reason"]}},
]


class DiagnosisTools:
    def __init__(self, studio: GodotStudio, project: Path, scenario, turn_dir: Path):
        self.studio, self.project, self.S, self.turn_dir = studio, Path(project), scenario, Path(turn_dir)
        self.session_id: str | None = None
        self.patches: list[dict] = []
        self.calls: list[dict] = []

    # -- source allowlist -----------------------------------------------------
    def _allowed(self, rel: str) -> bool:
        p = Path(rel)
        if p.is_absolute() or ".." in p.parts or not p.parts:
            return False
        if p.name in self.S.SOURCE_DENY_NAMES or any(part in self.S.SOURCE_DENY_DIRS for part in p.parts[:-1]):
            return False
        if rel == "project.godot":
            return True
        return p.parts[0] in self.S.SOURCE_ALLOW_DIRS and p.suffix in self.S.SOURCE_ALLOW_SUFFIXES

    def list_source_files(self) -> list[str]:
        out = []
        for r, ds, fs in os.walk(self.project):
            ds[:] = sorted(d for d in ds if d not in self.S.SOURCE_DENY_DIRS)
            for f in sorted(fs):
                rel = str((Path(r) / f).relative_to(self.project))
                if self._allowed(rel):
                    out.append(rel)
        return sorted(out)

    async def _ensure_session(self) -> str:
        if self.session_id is None:
            res = await self.studio.call("godot_launch_session", project=str(self.project), label="diagnosis", offscreen=True)
            self.session_id = res["session_id"]
        return self.session_id

    async def stop_session(self):
        if self.session_id:
            try:
                await self.studio.call("godot_stop_session", session_id=self.session_id)
            finally:
                self.session_id = None

    # -- dispatch -------------------------------------------------------------
    async def dispatch(self, name: str, args: dict) -> dict:
        t0 = time.time()
        try:
            if name == "inspect_scene":
                sid = await self._ensure_session()
                kw = {"session_id": sid}
                if args.get("node_path"):
                    kw["node_path"] = args["node_path"]
                if args.get("properties"):
                    kw["properties"] = args["properties"]
                out = await self.studio.call("godot_inspect_runtime", **kw)
            elif name == "inspect_physics":
                sid = await self._ensure_session()
                out = await self.studio.call("godot_inspect_physics", session_id=sid, node_path=args["node_path"])
            elif name == "drive":
                sid = await self._ensure_session()
                out = await self.studio.call("godot_run_input_sequence", session_id=sid, steps=args["steps"])
            elif name == "list_source_files":
                out = {"files": self.list_source_files()}
            elif name == "read_source":
                rel = args["path"]
                if not self._allowed(rel):
                    out = {"error": f"not readable: {rel}"}
                else:
                    out = {"path": rel, "content": (self.project / rel).read_text()}
            elif name == "patch_source":
                out = await self._patch(args)
            else:
                out = {"error": f"unknown tool {name}"}
        except ToolError as e:
            out = {"error": str(e)}
        except Exception as e:
            out = {"error": f"{type(e).__name__}: {e}"}
        out = scrub(out)
        self.calls.append({"ts": utc_now(), "tool": name, "args": args, "latency_s": round(time.time() - t0, 3),
                           "result_chars": len(json.dumps(out, default=str))})
        return out

    async def _patch(self, args: dict) -> dict:
        rel, find, repl, reason = args["path"], args["find"], args["replace"], args.get("reason", "")
        if not self._allowed(rel) or Path(rel).suffix not in (".gd", ".tscn"):
            return {"error": f"not patchable: {rel}"}
        fp = self.project / rel
        before = fp.read_text()
        n = before.count(find)
        if n != 1:
            return {"error": f"`find` must occur exactly once in {rel}; found {n}"}
        after = before.replace(find, repl, 1)
        diff = "".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True), f"a/{rel}", f"b/{rel}"))
        fp.write_text(after)
        rec = {"ts": utc_now(), "path": rel, "find": find, "replace": repl, "reason": reason, "diff": diff,
               "turn_patch_index": len(self.patches) + 1}
        self.patches.append(rec)
        await self.stop_session()  # the next launch must load the patched source
        return {"ok": True, "path": rel, "diff": diff, "note": "patch applied to the working copy; the game will be "
                                                                 "relaunched and re-measured after your turn"}
