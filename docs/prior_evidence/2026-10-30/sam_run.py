"""Upload both clips and run SAM 3.1 text-prompt tracking through the Responses
API. Raw model text is saved for offline analysis; the key is read from the
private file and never printed."""
import json, os, re, sys, time, urllib.error, urllib.request, uuid

here = os.path.dirname(os.path.abspath(__file__))
KEY = open(os.path.join(here, ".meta_key")).read().strip()
BASE = "https://api.meta.ai/v1"
REDACT = re.compile(r"LLM_[0-9]+_[A-Za-z0-9_-]+")
PROMPTS = {"capsule": "blue capsule", "robot": "robot", "bar": "yellow bar"}
RUNS = 2
out = os.path.join(here, "sam")
os.makedirs(out, exist_ok=True)


def req(url, data, headers, timeout=240):
    r = urllib.request.Request(url, data=data, headers={"Authorization": f"Bearer {KEY}", **headers}, method="POST")
    t0 = time.time()
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace"), time.time() - t0
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), time.time() - t0


def upload(path):
    b = "----" + uuid.uuid4().hex
    body = (f'--{b}\r\nContent-Disposition: form-data; name="purpose"\r\n\r\nuser_data\r\n'
            f'--{b}\r\nContent-Disposition: form-data; name="file"; filename="{os.path.basename(path)}"\r\n'
            f"Content-Type: video/mp4\r\n\r\n").encode() + open(path, "rb").read() + f"\r\n--{b}--\r\n".encode()
    code, txt, dt = req(f"{BASE}/files", body, {"Content-Type": f"multipart/form-data; boundary={b}"})
    print(f"upload {os.path.basename(path)}: http={code} {dt:.1f}s", flush=True)
    if code != 200:
        sys.exit("upload failed: " + REDACT.sub("[REDACTED]", txt)[:400])
    return json.loads(txt)["id"]


def texts(o):
    if isinstance(o, str):
        return [o] if "<|box;" in o else []
    if isinstance(o, dict):
        return [t for v in o.values() for t in texts(v)]
    if isinstance(o, list):
        return [t for v in o for t in texts(v)]
    return []


for clip in ("defect", "repaired"):
    fid = upload(os.path.join(here, "clips", f"{clip}.mp4"))
    for tag, phrase in PROMPTS.items():
        for n in range(1, RUNS + 1):
            body = {"model": "sam-3.1", "stream": False,
                    "metadata": {"include_confidence": "true", "mask_encoding": "one_bit"},
                    "input": [{"type": "message", "role": "user", "content": [
                        {"type": "input_text", "text": phrase}, {"type": "input_video", "file_id": fid}]}]}
            code, txt, dt = req(f"{BASE}/responses", json.dumps(body).encode(),
                                {"Content-Type": "application/json", "Accept": "application/json"})
            name = f"{clip}_{tag}_{n}"
            if code != 200:
                print(f"{name}: http={code} {dt:.1f}s {REDACT.sub('[REDACTED]', txt)[:300]}", flush=True)
                continue
            d = json.loads(txt)
            t = "\n".join(texts(d))
            open(os.path.join(out, name + ".txt"), "w").write(t)
            print(f"{name}: http=200 {dt:.1f}s lines={len([l for l in t.splitlines() if l.strip()])} "
                  f"chars={len(t)} usage={json.dumps(d.get('usage'))[:160]} status={d.get('status')}", flush=True)
