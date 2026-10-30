"""Blind, bounded diagnosis and repair by Muse.

Muse receives ONLY: the objective, the frozen contract, what the agent's tool
reported (the open-loop "success"), the verifier's measured failure report
(numbers from SAM 3.1 tracks), its own previous attempts in this run, and the
allowlisted tools. Never ground truth, fixture notes, diffs we authored, or
hints. The assembled prompt is screened against the scenario's banned terms
and hashed into the run bundle before it is sent."""
from __future__ import annotations

import json
from pathlib import Path

from .artifacts import RepairTurnRecord, sha256_bytes, write_json
from .mcp_adapter import TOOL_SPECS, DiagnosisTools
from .meta_client import SPARK, MetaClient
from .sensory_contract import SensoryContract
from .verifier import VerificationResult


class AntiCheatViolation(RuntimeError):
    pass


INSTRUCTIONS = (
    "You are the repair engineer for a small 3D game. An independent visual verifier decides whether the game meets "
    "an objective by tracking objects in the rendered clip with SAM 3.1 and evaluating a frozen geometric contract. "
    "The tool the agent used to act reported success, but the verifier measured a violation. Your job: find the root "
    "cause from evidence and apply the smallest source patch that makes the objective hold under the same contract.\n"
    "Rules: inspect before you patch, and reason from measured values (physics state, node properties, source). Do "
    "not modify the camera, the barrier's position or size, the verifier, or the capture; do not add new scripts; "
    "at most two patches per turn. You never declare success: after your turn the patched game is relaunched, "
    "re-captured and re-measured by the verifier. Finish with three short lines: root cause, patch, why it satisfies "
    "the contract.")


def _fmt(v, nd=1):
    return "n/a" if v is None else (f"{v:+.{nd}f}" if isinstance(v, float) else str(v))


def format_evidence(contract: SensoryContract, result: VerificationResult, open_loop: dict,
                    previous_turns: list[dict]) -> str:
    c = contract
    lines = [f"OBJECTIVE\n{c.objective}", "",
             "SENSORY CONTRACT (frozen before measurement)",
             f"statement: {c.statement}",
             f"mover concept: '{c.mover_concept}'   barrier concept: '{c.barrier_concept}'",
             f"rule: {c.rule.definition}",
             f"threshold_px={c.rule.threshold_px}  persistence_frames={c.rule.persistence_frames}  "
             f"critical_window={list(c.coverage.critical_window)}  frames={c.frame_count} @ {c.fps} fps, {c.frame_size[0]}x{c.frame_size[1]} px",
             f"expected if satisfied: {c.expected_pass_behaviour}",
             f"expected if violated: {c.expected_fail_signature}", "",
             "WHAT THE AGENT'S TOOL REPORTED (open loop)",
             f"{open_loop.get('tool')}({json.dumps(open_loop.get('args'))}) -> {json.dumps(open_loop.get('result'), default=str)[:300]}",
             "", "WHAT THE VISUAL VERIFIER MEASURED (SAM 3.1 tracks of the rendered clip; source pixels, y grows downward)",
             f"status: {result.status.value}   t_fail: {result.t_fail}   violation run: {result.violation_run}",
             f"max E(t): {_fmt(result.max_residual)} px at frame {result.max_residual_frame}   coverage: {json.dumps(result.coverage)}",
             f"reasons: {'; '.join(result.reasons)}", "",
             "frame | mover cx cy bottom vx vy | barrier cx cy bottom vy | E=barrier_bottom-mover_bottom"]
    for r in result.evidence_rows:
        m, b = r["mover"], r["barrier"]
        ms = "untracked" if not m else f"{m['cx']:.0f} {m['cy']:.0f} {m['bottom']:.0f} {_fmt(m['vx'])} {_fmt(m['vy'])}"
        bs = "untracked" if not b else f"{b['cx']:.0f} {b['cy']:.0f} {b['bottom']:.0f} {_fmt(b['vy'])}"
        mark = "  <-- t_fail" if r["frame"] == result.t_fail else ""
        lines.append(f"f{r['frame']:02d} | {ms} | {bs} | {_fmt(r['E_px'], 0)}{mark}")
    lines += ["", "HOW TO READ E(t): the chase camera follows the player, so the player stays near the same screen "
                  "position while approaching obstacles move down the frame. While the barrier is ahead of the "
                  "player its bottom edge is above the player's feet (E < 0). E rising above the threshold and staying "
                  "there means the barrier's bottom edge went below the player's feet: the player went past the barrier "
                  "instead of being stopped by it."]
    if previous_turns:
        lines += ["", "PREVIOUS REPAIR ATTEMPTS IN THIS RUN (your own; the verifier re-measured after each)"]
        for t in previous_turns:
            for p in t.get("patches", []):
                lines.append(f"turn {t['turn']} ({t['model']}): {p['path']}: {json.dumps(p['find'])} -> {json.dumps(p['replace'])}  reason: {p.get('reason','')}")
            lines.append(f"  -> re-measured: {t.get('result_after')}")
    lines += ["", "TASK: diagnose the root cause with the tools, then patch the working copy so that the objective holds "
                  "under this contract. Start with list_source_files / inspect_scene."]
    return "\n".join(lines)


def banned_terms_found(text: str, banned: tuple[str, ...]) -> list[str]:
    low = text.lower()
    return sorted({b for b in banned if b.lower() in low})


async def diagnose_and_repair(client: MetaClient, tools: DiagnosisTools, *, contract: SensoryContract,
                              result: VerificationResult, open_loop: dict, previous_turns: list[dict], scenario,
                              model: str, turn: int, turn_dir: Path, max_tool_calls: int = 24,
                              reasoning_effort: str = "medium", verbose: bool = True) -> RepairTurnRecord:
    turn_dir = Path(turn_dir)
    turn_dir.mkdir(parents=True, exist_ok=True)
    evidence = format_evidence(contract, result, open_loop, previous_turns)
    screened = INSTRUCTIONS + "\n" + evidence + "\n" + json.dumps(TOOL_SPECS)
    found = banned_terms_found(screened, scenario.BANNED_PROMPT_TERMS)
    prompt_rec = {"turn": turn, "model": model, "instructions": INSTRUCTIONS, "user": evidence, "tools": TOOL_SPECS,
                  "prompt_sha256": sha256_bytes(screened.encode()), "banned_terms_checked": list(scenario.BANNED_PROMPT_TERMS),
                  "banned_terms_found": found, "mentions_source_filenames": ".gd" in evidence or ".tscn" in evidence}
    prompt_path = write_json(turn_dir / "prompt.json", prompt_rec)
    if found:
        raise AntiCheatViolation(f"banned terms in outgoing prompt: {found}")

    items: list = [{"role": "user", "content": evidence}]
    transcript: list[dict] = []
    request_ids, response_ids, names = [], [], []
    n_calls, final_text, max_tokens, nudged = 0, "", 8000, False
    purpose = f"diagnosis_turn{turn}"
    try:
        while True:
            resp = client.muse(model, items, instructions=INSTRUCTIONS, tools=TOOL_SPECS, reasoning_effort=reasoning_effort,
                               max_output_tokens=max_tokens, purpose=purpose)
            request_ids.append(resp.get("_request_id") or "")
            response_ids.append(resp.get("id") or "")
            items.extend(client.replay_items(resp))
            calls = client.function_calls(resp)
            text = client.output_text(resp)
            transcript.append({"type": "assistant", "text": text, "calls": [{"name": c.get("name"), "arguments": c.get("arguments")} for c in calls],
                               "response_id": resp.get("id"), "request_id": resp.get("_request_id"),
                               "status": resp.get("status"), "usage": resp.get("usage")})
            if verbose:
                print(f"    [turn {turn}] {model}: {len(calls)} call(s) {[c.get('name') for c in calls]} {('| ' + text[:120].replace(chr(10), ' ')) if text else ''}")
            if text:
                final_text = text
            if not calls:
                if resp.get("status") == "incomplete" and not nudged:
                    nudged, max_tokens = True, 16000
                    items.append({"role": "user", "content": "Your previous response was cut off. Continue; call tools or give the final three lines."})
                    continue
                break
            for c in calls:
                n_calls += 1
                names.append(c.get("name"))
                try:
                    args = json.loads(c.get("arguments") or "{}")
                    out = await tools.dispatch(c["name"], args)
                except json.JSONDecodeError:
                    args, out = {}, {"error": "arguments were not valid JSON"}
                out_s = json.dumps(out, default=str)
                truncated = len(out_s) > 30000
                if truncated:
                    out_s = out_s[:30000] + " ...[truncated]"
                items.append({"type": "function_call_output", "call_id": c["call_id"], "output": out_s})
                transcript.append({"type": "tool", "name": c.get("name"), "arguments": args, "call_id": c.get("call_id"),
                                   "output": out_s if truncated else out})
            if n_calls >= max_tool_calls:
                items.append({"role": "user", "content": "Tool budget exhausted. Give the final three lines now; no more tool calls."})
                resp = client.muse(model, items, instructions=INSTRUCTIONS, reasoning_effort="low", max_output_tokens=4000, purpose=purpose)
                request_ids.append(resp.get("_request_id") or ""); response_ids.append(resp.get("id") or "")
                final_text = client.output_text(resp) or final_text
                transcript.append({"type": "assistant", "text": final_text, "calls": [], "response_id": resp.get("id"),
                                   "request_id": resp.get("_request_id"), "status": resp.get("status"), "usage": resp.get("usage")})
                break
    finally:
        await tools.stop_session()
    patches = tools.patches
    diff_path = diff_sha = None
    if patches:
        diff_text = "\n".join(p["diff"] for p in patches)
        diff_path = turn_dir / "diff.patch"
        diff_path.write_text(diff_text)
        diff_sha = sha256_bytes(diff_text.encode())
    transcript_path = write_json(turn_dir / "transcript.json", transcript)
    write_json(turn_dir / "patches.json", patches)
    write_json(turn_dir / "tool_calls.json", tools.calls)
    cost = sum((c.get("est_cost_usd") or 0.0) for c in client.calls if c.get("purpose") == purpose)
    return RepairTurnRecord(turn=turn, model=model, escalated=(model != SPARK), request_ids=[r for r in request_ids if r],
                            response_ids=[r for r in response_ids if r], tool_calls=n_calls, tool_call_names=names,
                            patches=[{k: v for k, v in p.items() if k != "diff"} for p in patches],
                            prompt_path=str(prompt_path.relative_to(turn_dir.parent)),
                            transcript_path=str(transcript_path.relative_to(turn_dir.parent)),
                            diff_path=None if diff_path is None else str(diff_path.relative_to(turn_dir.parent)),
                            diff_sha256=diff_sha, outcome_text=final_text[:3000],
                            anti_cheat={"prompt_sha256": prompt_rec["prompt_sha256"], "banned_terms_found": found,
                                        "banned_terms_checked": len(scenario.BANNED_PROMPT_TERMS),
                                        "mentions_source_filenames": prompt_rec["mentions_source_filenames"]},
                            est_cost_usd=round(cost, 6))
