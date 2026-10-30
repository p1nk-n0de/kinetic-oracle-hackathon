"""Run the real Claude Code against Meta's API from the clean room, with an
explicit tool allowlist, and summarise each turn. The key is read from a
private file, passed by env only, and redacted from everything printed."""
import json, os, re, subprocess, sys, time

here = os.path.dirname(os.path.abspath(__file__))
KEY = open(os.path.join(here, ".meta_key")).read().strip()
REDACT = re.compile(r"LLM_[0-9]+_[A-Za-z0-9_-]+")
PRICE = {"input": 1.25, "cached": 0.15, "output": 4.25}  # muse-spark-1.3 Standard, $/M


def clean(s):
    return REDACT.sub("[REDACTED]", str(s))


name, prompt, allow = sys.argv[1], sys.argv[2], sys.argv[3].split(",")
extra = dict(kv.split("=", 1) for kv in sys.argv[4:] if "=" in kv)
timeout = int(extra.pop("TIMEOUT", "240"))
model = extra.pop("MODEL", "muse-spark-1.3")
mcp = extra.pop("MCP", os.path.join(here, "studio_only.json"))
add_dir = extra.pop("ADD_DIR", "")
deny = extra.pop("DENY", "")

env = {k: v for k, v in os.environ.items() if not k.startswith(("ANTHROPIC_", "CLAUDE_CODE_"))}
env.update({
    "ANTHROPIC_BASE_URL": "https://api.meta.ai", "ANTHROPIC_AUTH_TOKEN": KEY,
    "ANTHROPIC_MODEL": model, "ANTHROPIC_DEFAULT_OPUS_MODEL": model,
    "ANTHROPIC_DEFAULT_SONNET_MODEL": model, "ANTHROPIC_DEFAULT_HAIKU_MODEL": model,
    "CLAUDE_CODE_SUBAGENT_MODEL": model, "ENABLE_TOOL_SEARCH": "true",
    "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1", "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
})
env.update(extra)

log = os.path.join(here, f"live_{name}.jsonl")
cmd = ["claude", "-p", prompt, "--no-session-persistence", "--output-format", "stream-json", "--verbose",
       "--strict-mcp-config", "--mcp-config", mcp,
       "--setting-sources", "local", "--allowedTools", ",".join(allow),
       "--disallowedTools", "Bash,Edit,Write,NotebookEdit,Agent,WebFetch,WebSearch" + ("," + deny if deny else "")]
if add_dir:
    cmd += ["--add-dir", add_dir]
t0 = time.time()
err = ""
try:
    r = subprocess.run(cmd, cwd=os.path.join(here, "cleanroom"), env=env, stdin=subprocess.DEVNULL,
                       capture_output=True, text=True, timeout=timeout)
    out, err, rc = r.stdout, r.stderr, r.returncode
except subprocess.TimeoutExpired as e:
    out, rc = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or ""), "timeout"
open(log, "w").write(clean(out))

calls, turns, final = [], 0, None
usage = {"input": 0, "cached": 0, "output": 0}
seen = set()
for line in out.splitlines():
    try:
        m = json.loads(line)
    except ValueError:
        continue
    t = m.get("type")
    if t == "assistant":
        msg = m.get("message") or {}
        mid = msg.get("id")
        u = msg.get("usage") or {}
        if mid and mid not in seen:
            seen.add(mid)
            turns += 1
            usage["input"] += (u.get("input_tokens") or 0) + (u.get("cache_creation_input_tokens") or 0)
            usage["cached"] += u.get("cache_read_input_tokens") or 0
            usage["output"] += u.get("output_tokens") or 0
        for b in msg.get("content") or []:
            if b.get("type") == "tool_use":
                calls.append(("CALL", b.get("name"), clean(json.dumps(b.get("input")))[:200]))
            elif b.get("type") == "text" and b.get("text", "").strip():
                calls.append(("TEXT", clean(b["text"])[:400], ""))
    elif t == "user":
        for b in ((m.get("message") or {}).get("content") or []):
            if isinstance(b, dict) and b.get("type") == "tool_result":
                c = b.get("content")
                if isinstance(c, list):
                    kinds = [x.get("type") for x in c if isinstance(x, dict)]
                    txt = " ".join(x.get("text", "") for x in c if isinstance(x, dict))
                else:
                    kinds, txt = ["str"], str(c)
                calls.append(("RESULT", f"err={b.get('is_error')} kinds={kinds}", clean(txt)[:220].replace("\n", " ")))
    elif t == "result":
        final = m

print(f"=== {name}  rc={rc}  {time.time()-t0:.1f}s  turns={turns}  model={model}")
for c in calls:
    print(" ", *c)
if final:
    print("result:", {k: clean(final.get(k))[:300] for k in ("subtype", "is_error", "api_error_status", "result")})
if final and final.get("usage"):
    u = final["usage"]
    usage = {"input": (u.get("input_tokens") or 0) + (u.get("cache_creation_input_tokens") or 0),
             "cached": u.get("cache_read_input_tokens") or 0, "output": u.get("output_tokens") or 0}
cost = (usage["input"] * PRICE["input"] + usage["cached"] * PRICE["cached"] + usage["output"] * PRICE["output"]) / 1e6
print(f"usage: {usage}  est_cost=${cost:.4f}")
if rc != 0 or (final and final.get("is_error")):
    print("stderr:", clean(err)[:500])
