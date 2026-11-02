"""Offline replay verifier for a run bundle (`runs/<run_id>/`).

  .venv/bin/python -m scripts.replay_run --run-dir runs/<run_id> [--json]

Zero API spend, no network, no Godot. From the bundle alone it
  1. recomputes the sha256 of every present bundle file and compares it with `run_manifest.json: files`
     (raw `frames/` PNGs and the staged `workspace/` tree are gitignored: absence is reported, not failed);
  2. re-parses SAM 3.1's exact wire text (`passN/sam/*.json: raw_text`), rebuilds the tracks, re-runs the frozen
     verifier under the frozen `contract.json`, and asserts equality with the stored `verification.json`
     (status, t_fail, residual series, coverage) and `tracks.json`;
  3. prints a turn-by-turn audit table (hashes, contract, passes, repair turns, spend);
  4. exits 0 only if every hash matches and every recomputed verdict matches, else 1.

The verdict printed here is the verifier's: tool statuses and model text are shown but never consulted."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from propriosam.artifacts import RunManifest, load_manifest, verify_bundle_hashes  # noqa: E402
from propriosam.sensory_contract import SensoryContract  # noqa: E402
from propriosam.verifier import rule_sha256, verify  # noqa: E402
from propriosam.vision_tracker import Track, build_track, parse_sam_text  # noqa: E402

# Fields of verification.json that must be reproduced bit-for-bit by the replay.
VERDICT_FIELDS = ("status", "t_fail", "residual", "coverage", "violation_run", "max_residual", "max_residual_frame",
                  "margin_px", "mover_bottom", "barrier_bottom", "reasons", "frame_count", "contract_id")
# Fields of each tracks.json entry that must be reproduced from raw SAM text.
TRACK_FIELDS = ("concept", "object_id", "frame_count", "frame_size", "coverage_total", "selection", "points")

VERDICT_BASIS = "from the verifier over SAM 3.1 tracks; tool status and model text are never consulted"


# ----------------------------------------------------------------------------------------------- helpers

def _read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def _short(h: str | None, n: int = 12) -> str:
    return "-" if not h else f"{h[:n]}…"


def _flag(ok: bool | None, yes: str = "✓", no: str = "✗", unknown: str = "?") -> str:
    return unknown if ok is None else (yes if ok else no)


def _fmt_px(v: float | None) -> str:
    return "n/a" if v is None else f"{v:+.1f}"


def _diff_keys(a: dict, b: dict, keys: tuple[str, ...]) -> list[str]:
    return [k for k in keys if a.get(k) != b.get(k)]


# ----------------------------------------------------------------------------------------------- checks

def classify_hashes(run_dir: Path) -> dict:
    """verify_bundle_hashes + classification of entries the repo does not distribute.

    `hash_bundle_files` materialises `os.walk` before pruning, so a closed_loop manifest also lists the staged
    `workspace/` tree (gitignored) including its `.godot/` editor cache (excluded from tree hashes by design).
    Absent workspace files are therefore optional; a present-but-changed workspace file still fails, except
    under `.godot/` which Godot rewrites on every open."""
    r = verify_bundle_hashes(run_dir)
    missing_ws = [k for k in r["missing"] if k.startswith("workspace/")]
    missing_required = [k for k in r["missing"] if not k.startswith("workspace/")]
    changed_godot = [k for k in r["changed"] if "/.godot/" in k]
    changed = [k for k in r["changed"] if "/.godot/" not in k]
    return {"ok": not missing_required and not changed, "checked": r["checked"],
            "verified_present": r["checked"] - len(r["missing"]) - r["missing_optional_frames"] - len(r["changed"]) - len(r["sanitized"]),
            "sanitized": r["sanitized"],
            "missing_required": missing_required, "missing_optional_frames": r["missing_optional_frames"],
            "missing_optional_workspace": len(missing_ws), "changed": changed, "ignored_changed_godot_cache": changed_godot,
            "extra_untracked": r["extra"]}


def check_contract(run_dir: Path, m: RunManifest) -> tuple[SensoryContract | None, dict]:
    out: dict[str, Any] = {"ok": False, "warnings": []}
    if not m.contract_path or not (run_dir / m.contract_path).exists():
        out["error"] = "contract.json missing"
        return None, out
    c = SensoryContract.model_validate_json((run_dir / m.contract_path).read_text())
    out["contract_id"] = c.contract_id
    out["frozen_intact"] = c.check_frozen()
    out["frozen_sha256"] = c.frozen_sha256
    out["matches_manifest"] = c.frozen_sha256 == m.contract_sha256
    now_rule = rule_sha256()
    out["rule_sha256_now"] = now_rule
    out["rule_sha256_manifest"] = m.rule_sha256
    out["rule_matches"] = now_rule == m.rule_sha256
    if not out["rule_matches"]:
        out["warnings"].append(
            "rule_sha256 differs: propriosam/verifier.py (_residual_series/_scan_violation/verify) has been edited since this "
            f"bundle was written (bundle {_short(m.rule_sha256)} vs code {_short(now_rule)}); verdicts below are recomputed with "
            "the current code and must still match")
    out["ok"] = bool(out["frozen_intact"] and out["matches_manifest"])
    return c, out


def replay_pass(run_dir: Path, c: SensoryContract, p) -> dict:
    """Rebuild both tracks from raw SAM text, re-verify, and compare with the stored artefacts."""
    out: dict[str, Any] = {"index": p.index, "label": p.label, "ok": False, "mismatches": [], "sam": {}}
    tracks: dict[str, Track] = {}
    for role, concept in (("mover", c.mover_concept), ("barrier", c.barrier_concept)):
        sam_path = run_dir / p.sam.get(role, {}).get("raw_path", f"pass{p.index}/sam/{role}.json")
        if not sam_path.exists():
            out["mismatches"].append(f"{role}: {sam_path.name} missing")
            continue
        sam = _read_json(sam_path)
        if sam.get("concept") != concept:
            out["mismatches"].append(f"{role}: sam concept {sam.get('concept')!r} != contract {concept!r}")
        dets = parse_sam_text(sam["raw_text"])
        tracks[role] = build_track(concept, dets, c.frame_count, tuple(c.frame_size))
        out["sam"][role] = {"concept": concept, "request_id": sam.get("request_id"), "response_id": sam.get("response_id"),
                            "cached": sam.get("cached"), "frames_processed": sam.get("frames_processed"),
                            "raw_lines": len(sam["raw_text"].splitlines()), "object_ids": sorted({d.object_id for ds in dets.values() for d in ds}),
                            "object_id_selected": tracks[role].object_id, "frames_tracked": len(tracks[role].points)}
    if len(tracks) < 2:
        return out
    stored_tracks_path = run_dir / p.tracks_path
    if stored_tracks_path.exists():
        stored_tracks = _read_json(stored_tracks_path)
        for role, tr in tracks.items():
            bad = _diff_keys(tr.to_json(), stored_tracks.get(role, {}), TRACK_FIELDS)
            if bad:
                out["mismatches"].append(f"tracks.json[{role}] differs in {bad}")
    else:
        out["mismatches"].append("tracks.json missing")
    res = verify(c, tracks["mover"], tracks["barrier"])
    rec = res.model_dump(mode="json")
    out["recomputed"] = {"status": rec["status"], "t_fail": rec["t_fail"], "max_residual": rec["max_residual"],
                         "max_residual_frame": rec["max_residual_frame"], "violation_run": rec["violation_run"],
                         "coverage": rec["coverage"], "reasons": rec["reasons"],
                         "tracked_frames": sum(1 for e in rec["residual"] if e is not None)}
    stored_path = run_dir / p.verification_path
    if not stored_path.exists():
        out["mismatches"].append("verification.json missing")
        return out
    stored = _read_json(stored_path)
    out["stored"] = {"status": stored.get("status"), "t_fail": stored.get("t_fail"), "max_residual": stored.get("max_residual")}
    bad = _diff_keys(rec, stored, VERDICT_FIELDS)
    if bad:
        out["mismatches"].append(f"verification.json differs in {bad}")
    if stored.get("rule_sha256") != rec["rule_sha256"]:
        out["rule_sha256_differs"] = True  # reported as a warning at contract level; verdict equality is what matters
    if p.verification_status != rec["status"] or p.t_fail != rec["t_fail"]:
        out["mismatches"].append(f"manifest PassRecord says {p.verification_status}@{p.t_fail}, recomputed {rec['status']}@{rec['t_fail']}")
    out["ok"] = not out["mismatches"]
    return out


def replay(run_dir: str | Path) -> dict:
    """Full offline replay. Returns a JSON-serialisable report with `ok` = exit-0 condition."""
    t0 = time.perf_counter()
    run_dir = Path(run_dir)
    m = load_manifest(run_dir)
    report: dict[str, Any] = {"run_id": m.run_id, "run_dir": str(run_dir), "kind": m.kind, "status": m.status,
                              "final_verdict": m.final_verdict, "verdict_basis": m.verdict_basis, "created_at": m.created_at,
                              "finished_at": m.finished_at, "models": m.models, "baseline": m.baseline, "workspace": m.workspace,
                              "spend": m.spend, "request_ids": m.request_ids, "warnings": []}
    report["hashes"] = classify_hashes(run_dir)
    contract, cinfo = check_contract(run_dir, m)
    report["contract"] = cinfo
    report["warnings"].extend(cinfo.get("warnings", []))
    report["passes"] = [replay_pass(run_dir, contract, p) for p in m.passes] if contract else []
    if contract is None:
        report["warnings"].append("no contract: verdicts cannot be recomputed")
    for p, rp in zip(m.passes, report["passes"]):
        rp["manifest"] = {"label": p.label, "verification_status": p.verification_status, "t_fail": p.t_fail,
                          "max_residual": p.max_residual, "clip_sha256": p.clip_sha256, "overlay_sha256": p.overlay_sha256,
                          "project_tree_sha256": p.project_tree_sha256, "open_loop": p.open_loop,
                          "sam_meta": {r: {k: s.get(k) for k in ("request_id", "response_id", "cached", "frames_tracked", "coverage_total")}
                                       for r, s in p.sam.items()}}
    report["repair_turns"] = []
    for rt in m.repair_turns:
        prompt = _read_json(run_dir / rt.prompt_path) if (run_dir / rt.prompt_path).exists() else {}
        report["repair_turns"].append({
            "turn": rt.turn, "model": rt.model, "escalated": rt.escalated, "tool_calls": rt.tool_calls,
            "tool_call_names": rt.tool_call_names, "patches": rt.patches, "diff_sha256": rt.diff_sha256,
            "diff_present": bool(rt.diff_path and (run_dir / rt.diff_path).exists()),
            "request_ids": rt.request_ids, "response_ids": rt.response_ids, "est_cost_usd": rt.est_cost_usd,
            "anti_cheat": rt.anti_cheat, "prompt_banned_terms_found": prompt.get("banned_terms_found"),
            "prompt_sha256_matches": (prompt.get("prompt_sha256") == rt.anti_cheat.get("prompt_sha256")) if prompt else None,
            "outcome_text": rt.outcome_text})
    verdicts_ok = bool(report["passes"]) and all(p["ok"] for p in report["passes"]) if m.passes else contract is not None
    report["checks"] = {"hashes_ok": report["hashes"]["ok"], "contract_ok": cinfo.get("ok", False), "verdicts_ok": verdicts_ok,
                        "passes_total": len(m.passes), "passes_reproduced": sum(1 for p in report["passes"] if p["ok"])}
    report["ok"] = bool(report["hashes"]["ok"] and cinfo.get("ok", False) and verdicts_ok)
    report["elapsed_s"] = round(time.perf_counter() - t0, 3)
    return report


# ----------------------------------------------------------------------------------------------- audit table

def _table(rows: list[list[str]], header: list[str] | None = None, indent: str = "  ") -> str:
    allrows = ([header] if header else []) + rows
    widths = [max(len(str(r[i])) for r in allrows) for i in range(len(allrows[0]))]
    lines = []
    for n, r in enumerate(allrows):
        lines.append(indent + "  ".join(str(v).ljust(widths[i]) for i, v in enumerate(r)).rstrip())
        if header and n == 0:
            lines.append(indent + "  ".join("-" * w for w in widths))
    return "\n".join(lines)


def render_report(rep: dict) -> str:
    L: list[str] = []
    bar = "=" * 100
    L += [bar, f"KINETIC-ORACLE offline replay — {rep['run_id']}  (kind={rep['kind']}, status={rep['status']})", bar,
          f"created {rep['created_at']}  finished {rep['finished_at']}  models {json.dumps(rep['models'])}",
          f"manifest final_verdict: {rep['final_verdict']}",
          f"verdict basis: {rep['verdict_basis']}", ""]
    h = rep["hashes"]
    L += ["[1] BUNDLE INTEGRITY (sha256 of every present file vs run_manifest.json: files)",
          f"  entries in manifest: {h['checked']}   verified byte-original: {h['verified_present']}   "
          f"changed: {len(h['changed'])}   missing (required): {len(h['missing_required'])}",
          f"  optional, not distributed (gitignored): frames/ {h['missing_optional_frames']}   workspace/ {h['missing_optional_workspace']}"]
    if h["ignored_changed_godot_cache"]:
        L.append(f"  ignored: {len(h['ignored_changed_godot_cache'])} changed file(s) under workspace/.godot/ (editor cache, excluded from tree hashes)")
    if h["extra_untracked"]:
        L.append(f"  extra files not in manifest (not hashed at write time): {h['extra_untracked']}")
    if h["sanitized"]:
        L.append(f"  redacted copies (identity metadata only; the manifest hash is of the private original, the present hash is in "
                 f"runs/SANITIZATION_LEDGER.json): {len(h['sanitized'])}")
        L += [f"    redacted: {k}" for k in h["sanitized"]]
    for k in h["changed"]:
        L.append(f"  CHANGED: {k}")
    for k in h["missing_required"]:
        L.append(f"  MISSING: {k}")
    L.append(f"  => hashes {'OK' if h['ok'] else 'MISMATCH'}")
    b, w = rep.get("baseline") or {}, rep.get("workspace") or {}
    L += ["", "[2] BASELINE / WORKSPACE (proof the original project was never mutated)"]
    if b or w:
        L += [f"  baseline tree        {b.get('tree_sha256')}  ({b.get('files')} files)",
              f"  baseline after run   {b.get('tree_sha256_after_run')}   unchanged: {_flag(b.get('unchanged'))}",
              f"  workspace staged     {w.get('staged_tree_sha256')}   matched baseline at stage: {_flag(w.get('baseline_match_at_stage'))}",
              f"  workspace final      {w.get('final_tree_sha256')}   modified during run: {_flag(w.get('modified_during_run'), 'yes', 'no')}"]
    else:
        L.append("  (none: clip_evaluation bundles score pre-captured clips; no project was staged)")
    c = rep["contract"]
    L += ["", "[3] SENSORY CONTRACT (frozen before any clip was scored)"]
    if "error" in c:
        L.append(f"  ERROR: {c['error']}")
    else:
        L += [f"  id {c['contract_id']}   frozen_sha256 {c['frozen_sha256']}",
              f"  frozen intact: {_flag(c['frozen_intact'])}   matches manifest.contract_sha256: {_flag(c['matches_manifest'])}",
              f"  rule_sha256 code {c['rule_sha256_now']}",
              f"  rule_sha256 bundle {c['rule_sha256_manifest']}   matches: {_flag(c['rule_matches'])}"]
    L += ["", "[4] PASSES (verdict recomputed from raw SAM 3.1 text under the frozen contract; compared with stored verification.json)"]
    rows = []
    for p in rep["passes"]:
        rc, st, mf = p.get("recomputed") or {}, p.get("stored") or {}, p.get("manifest") or {}
        cov = rc.get("coverage") or {}
        rows.append([f"pass{p['index']}", p["label"][:28], rc.get("status", "-"), str(rc.get("t_fail")), _fmt_px(rc.get("max_residual")),
                     f"m {cov.get('mover_total', 0):.3f}/{cov.get('mover_window', 0):.2f}  b {cov.get('barrier_total', 0):.3f}/{cov.get('barrier_window', 0):.2f}",
                     f"{st.get('status', '-')}@{st.get('t_fail')}", _flag(p["ok"], "MATCH", "MISMATCH")])
    L.append(_table(rows, ["pass", "label", "status", "t_fail", "max E", "coverage total/window", "stored", "replay"]))
    for p in rep["passes"]:
        mf = p.get("manifest") or {}
        ol = mf.get("open_loop") or {}
        L.append(f"  pass{p['index']}: clip {_short(mf.get('clip_sha256'))}  overlay {_short(mf.get('overlay_sha256'))}  "
                 f"project tree {_short(mf.get('project_tree_sha256'))}")
        for role, s in (p.get("sam") or {}).items():
            L.append(f"    SAM {role:<7} '{s['concept']}'  request_id {s['request_id']}  cached={s['cached']}  "
                     f"ids seen {s['object_ids']} -> selected {s['object_id_selected']}  tracked {s['frames_tracked']} frames "
                     f"({s['raw_lines']} SAM lines)")
        if ol:
            L.append(f"    open-loop tool result (recorded, never consulted): {ol.get('tool')} -> is_error={ol.get('mcp_is_error')} "
                     f"result={json.dumps(ol.get('result'), default=str)[:90]}")
        for mm in p["mismatches"]:
            L.append(f"    MISMATCH: {mm}")
    L += ["", "[5] REPAIR TURNS (Muse diagnosed blind: evidence prompt screened for banned terms before sending)"]
    if not rep["repair_turns"]:
        L.append("  (none)")
    for t in rep["repair_turns"]:
        ac = t["anti_cheat"] or {}
        L += [f"  turn {t['turn']}  model {t['model']}{'  (escalated)' if t['escalated'] else ''}  tool calls {t['tool_calls']}  "
              f"patches {len(t['patches'])}  est ${t['est_cost_usd']}",
              f"    tool calls: {', '.join(t['tool_call_names']) or '-'}",
              f"    anti-cheat: banned terms checked {ac.get('banned_terms_checked')}  found {ac.get('banned_terms_found')}  "
              f"mentions source filenames {ac.get('mentions_source_filenames')}  prompt sha {_short(ac.get('prompt_sha256'))} "
              f"(prompt.json agrees: {_flag(t['prompt_sha256_matches'])})",
              f"    diff sha {_short(t['diff_sha256'])} present={t['diff_present']}   request ids: {', '.join(t['request_ids'])}"]
        for pt in t["patches"]:
            L.append(f"    patch {pt.get('turn_patch_index')}: {pt.get('path')}  reason: {str(pt.get('reason', ''))[:110]}")
        if t["outcome_text"]:
            L.append("    model text (NOT a verdict): " + t["outcome_text"].replace("\n", " | ")[:220])
    sp = rep.get("spend") or {}
    L += ["", "[6] SPEND (Meta API, estimated at published prices)", f"  calls {sp.get('calls')}  est ${sp.get('est_cost_usd')}"]
    for model, v in sorted((sp.get("by_model") or {}).items()):
        L.append(f"    {model:<16} calls {v.get('calls'):>3}  cached {v.get('cached'):>3}  est ${v.get('est_cost_usd')}")
    L.append(f"  request ids recorded: {len(rep.get('request_ids') or [])}")
    for wmsg in rep["warnings"]:
        L.append(f"\nWARNING: {wmsg}")
    ck = rep["checks"]
    verdicts = " / ".join(f"pass{p['index']} {(p.get('recomputed') or {}).get('status', 'ERROR')}" for p in rep["passes"]) or "n/a"
    L += ["", bar,
          f"REPLAY {'OK' if rep['ok'] else 'FAILED'}: hashes {_flag(ck['hashes_ok'], 'match', 'MISMATCH')}, contract "
          f"{_flag(ck['contract_ok'], 'frozen+matching', 'BROKEN')}, verdicts reproduced {ck['passes_reproduced']}/{ck['passes_total']} "
          f"({rep['elapsed_s']} s, zero API calls)",
          f"VERDICT (recomputed): {verdicts} — {VERDICT_BASIS}", bar]
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-dir", required=True, help="bundle directory containing run_manifest.json")
    ap.add_argument("--json", action="store_true", help="print the machine-readable report instead of the audit table")
    a = ap.parse_args(argv)
    run_dir = Path(a.run_dir)
    if not (run_dir / "run_manifest.json").exists():
        print(f"error: {run_dir}/run_manifest.json not found", file=sys.stderr)
        return 2
    rep = replay(run_dir)
    if a.json:
        print(json.dumps(rep, indent=1, sort_keys=True, default=str))
    else:
        print(render_report(rep))
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
