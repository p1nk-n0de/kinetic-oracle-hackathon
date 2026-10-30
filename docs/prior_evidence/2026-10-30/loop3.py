"""Three independent Spark attempts at the Godot defect. Muse gets no diagnosis
and no godot_propose_repair. Success is read from the retest tool's own JSON,
never from the model's summary. Stops early if estimated spend passes the cap."""
import hashlib, json, os, re, subprocess, sys, time

here = os.path.dirname(os.path.abspath(__file__))
FIX = "<godot-studio>/tests/fixtures/pg_defect_hurdle"
SCN = "example_game/proving_ground/scenarios/"
CAP = 5.0
g = "mcp__<redacted:studio>-godot__godot_"
allow = ",".join(g + t for t in ("run_scenario", "launch_session", "run_input_sequence", "send_input", "inspect_physics",
                                 "inspect_runtime", "session_status", "get_runtime_errors", "stop_session", "capture_frame",
                                 "apply_repair_copy", "retest_repair"))
deny = ",".join(g + t for t in ("propose_repair", "debug_inject", "time_control", "verify_completion",
                                "export_evidence", "export_build", "project_validate", "assert_condition", "capture_playthrough"))
prompt = f"""You are repairing a physics bug in a Godot 4 game.
Project: {FIX}
Failing scenario_path: {SCN}hurdle_blocks_walking.yaml
Expected behaviour: a robot walking forward into the hurdle must be physically stopped by it. It is not.

1. Reproduce with godot_run_scenario using that project and scenario_path.
2. Find the root cause from runtime evidence. Launch a session with offscreen=true, drive the robot with godot_run_input_sequence, and inspect the relevant nodes with godot_inspect_physics. Stop the session when done. Source files are readable under {FIX}/scripts.
3. Never modify the baseline. Fix a working copy with godot_apply_repair_copy, passing baseline_project, patches as a list of file/find/replace objects, and a reason.
4. Prove the fix with godot_retest_repair using the same scenario_path, copy_project set to the copy path returned in step 3, and regression_scenarios {SCN}jump_clears_hurdle.yaml and {SCN}reach_corridor.yaml.
5. If the retest does not pass, keep diagnosing, with at most two more repair attempts.
Finish with exactly three lines: root cause, the exact patch, the retest outcome."""


def tree_hash(p):
    h = hashlib.sha256()
    for r, ds, fs in sorted(os.walk(p)):
        ds[:] = sorted(d for d in ds if d not in (".godot",))
        for f in sorted(fs):
            fp = os.path.join(r, f)
            h.update(os.path.relpath(fp, p).encode())
            h.update(open(fp, "rb").read())
    return h.hexdigest()


before = tree_hash(FIX)
spent = 0.0
rows = []
for i in (2, 3):
    name = f"loop{i}"
    t0 = time.time()
    if i == 2:
        r = subprocess.CompletedProcess([], 0, open(os.path.join(here, "loop2.txt")).read() if os.path.exists(os.path.join(here, "loop2.txt")) else "", "")
    else:
      r = subprocess.run([sys.executable, "-I", os.path.join(here, "run_live.py"), name, prompt, allow,
                        f"MCP={os.path.join(here, 'godot_only.json')}", f"ADD_DIR={FIX}/scripts", f"DENY={deny}",
                        "CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1", "TIMEOUT=480"], capture_output=True, text=True)
      open(os.path.join(here, f"loop{i}.txt"), "w").write(r.stdout + r.stderr)
    m = re.search(r"est_cost=\$([0-9.]+)", r.stdout)
    cost = float(m.group(1)) if m else 0.0
    spent += cost
    # verdict from the tool's own JSON
    pending, results, patches = {}, [], []
    for line in open(os.path.join(here, f"live_{name}.jsonl"), errors="replace"):
        try:
            e = json.loads(line)
        except ValueError:
            continue
        msg = e.get("message")
        if not isinstance(msg, dict):
            continue
        for b in (msg.get("content") or []):
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_use":
                pending[b["id"]] = b
            elif b.get("type") == "tool_result" and b.get("tool_use_id") in pending:
                u = pending[b["tool_use_id"]]
                c = b.get("content")
                txt = " ".join(x.get("text", "") for x in c if isinstance(x, dict)) if isinstance(c, list) else str(c)
                results.append((u["name"].split("__")[-1], txt))
                if u["name"].endswith("apply_repair_copy") and u["input"].get("patches"):
                    patches.append(u["input"]["patches"])
    verdict = None
    for n, txt in results:
        if n == "godot_retest_repair":
            try:
                d = json.loads(txt)
                verdict = {"fixed": d.get("comparison", {}).get("fixed"), "regressions_all_pass": d.get("regressions_all_pass"),
                           "baseline_unchanged": d.get("baseline_unchanged"),
                           "regressions": [(x.get("scenario_id"), x.get("outcome")) for x in d.get("regressions", [])],
                           "comparison": d.get("comparison")}
            except ValueError:
                verdict = {"unparsed": txt[:300]}
    tools = [n.replace("godot_", "") for n, _ in results]
    rows.append({"run": name, "secs": round(time.time() - t0), "cost": cost, "n_calls": len(tools), "tools": tools,
                 "patches": patches, "verdict": verdict})
    print(json.dumps(rows[-1], default=str)[:1500], flush=True)
    if spent > CAP:
        print("STOPPED: spend cap reached", flush=True)
        break
print("baseline unchanged by hash:", before == tree_hash(FIX), flush=True)
print(f"total est spend ${spent:.3f}", flush=True)
json.dump(rows, open(os.path.join(here, "loop_summary.json"), "w"), indent=1, default=str)
