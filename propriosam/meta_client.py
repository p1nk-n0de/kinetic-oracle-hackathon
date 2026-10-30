"""Unified Meta Model API client.

Bearer auth read from the environment only, every call logged with Meta's
request id and usage, a spend meter with a hard cap, SAM 3.1 video tracking
with a content-addressed cache, and Muse Spark / Muse Wonder calls on the
Responses API. Plain urllib so the runtime has no SDK dependency."""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_URL = "https://api.meta.ai/v1"
SAM_MODEL = "sam-3.1"
SPARK = "muse-spark-1.3"
SPARK_CONTRIBUTOR = "muse-spark-1.3-contributor"
WONDER = "muse-wonder-1.0"

# USD per 1M tokens: (input, cached input, output) — dev.meta.ai/docs/pricing-rate-limits, 2026-10-30
PRICES_PER_M = {
    SPARK: (1.25, 0.15, 4.25),
    SPARK_CONTRIBUTOR: (0.10, 0.002, 0.20),
    WONDER: (4.00, 0.20, 20.00),
}
SAM_USD_PER_FRAME = 0.20 / 1000
SAM_MIN_BILLED_FRAMES = 50
REQUEST_ID_HEADERS = ("x-request-id", "request-id", "x-meta-request-id")
RETRY_STATUSES = (429, 500, 502, 503, 504)


class MetaAPIError(RuntimeError):
    def __init__(self, status: int, path: str, body: str):
        super().__init__(f"Meta API {path} -> HTTP {status}: {body[:400]}")
        self.status, self.path, self.body = status, path, body


class BudgetExceeded(RuntimeError):
    pass


def api_key() -> str:
    key = os.environ.get("MODEL_API_KEY") or os.environ.get("META_API_KEY")
    if not key:
        raise RuntimeError("MODEL_API_KEY (or META_API_KEY) is not set in the environment")
    return key


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class SamResult:
    prompt: str
    model: str
    clip_sha256: str
    raw_text: str
    response_id: str | None
    request_id: str | None
    cached: bool
    frames_processed: int | None
    cache_path: str
    metadata: dict


class MetaClient:
    def __init__(self, run_dir: str | Path | None = None, *, budget_usd: float = 40.0,
                 cache_dir: str | Path | None = None, timeout_s: float = 240.0):
        self._key = api_key()
        self.run_dir = Path(run_dir) if run_dir else None
        self.cache_dir = Path(cache_dir) if cache_dir else Path(__file__).resolve().parents[1] / ".cache"
        self.budget_usd = budget_usd
        self.spent_usd = 0.0
        self.timeout_s = timeout_s
        self.calls: list[dict] = []

    # ------------------------------------------------------------------ transport
    def _http(self, method: str, path: str, *, data: bytes | None = None, headers: dict | None = None,
              retries: int = 3) -> tuple[int, dict, bytes, float]:
        url = f"{BASE_URL}{path}"
        hdrs = {"Authorization": f"Bearer {self._key}", **(headers or {})}
        last: tuple[int, str] | None = None
        for attempt in range(retries + 1):
            req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
            t0 = time.time()
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                    return resp.status, {k.lower(): v for k, v in resp.headers.items()}, resp.read(), time.time() - t0
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", "replace")
                if e.code in RETRY_STATUSES and attempt < retries:
                    last = (e.code, body)
                    time.sleep(1.5 * 2 ** attempt)
                    continue
                raise MetaAPIError(e.code, path, body)
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                if attempt < retries:
                    last = (0, str(e))
                    time.sleep(1.5 * 2 ** attempt)
                    continue
                raise MetaAPIError(0, path, str(e))
        raise MetaAPIError(last[0] if last else 0, path, last[1] if last else "retries exhausted")

    def _record(self, rec: dict) -> None:
        rec.setdefault("ts", utc_now())
        self.calls.append(rec)
        cost = rec.get("est_cost_usd") or 0.0
        self.spent_usd += cost
        rec["cumulative_est_cost_usd"] = round(self.spent_usd, 6)
        if self.run_dir:
            self.run_dir.mkdir(parents=True, exist_ok=True)
            with open(self.run_dir / "api_calls.jsonl", "a") as f:
                f.write(json.dumps(rec, sort_keys=True) + "\n")
        if self.spent_usd > self.budget_usd:
            raise BudgetExceeded(f"estimated spend ${self.spent_usd:.2f} exceeds cap ${self.budget_usd:.2f}")

    @staticmethod
    def estimate_cost(model: str | None, usage: dict | None) -> float | None:
        usage = usage or {}
        if model == SAM_MODEL:
            frames = usage.get("video_frames_processed")
            return None if frames is None else max(int(frames), SAM_MIN_BILLED_FRAMES) * SAM_USD_PER_FRAME
        p = PRICES_PER_M.get(model or "")
        if not p:
            return None
        inp = int(usage.get("input_tokens") or 0)
        cached = int((usage.get("input_tokens_details") or {}).get("cached_tokens") or 0)
        out = int(usage.get("output_tokens") or 0)
        return (max(inp - cached, 0) * p[0] + cached * p[1] + out * p[2]) / 1e6

    def spend_summary(self) -> dict:
        by_model: dict[str, dict] = {}
        for c in self.calls:
            m = by_model.setdefault(str(c.get("model")), {"calls": 0, "est_cost_usd": 0.0, "cached": 0})
            m["calls"] += 1
            m["est_cost_usd"] = round(m["est_cost_usd"] + (c.get("est_cost_usd") or 0.0), 6)
            m["cached"] += 1 if c.get("cached") else 0
        return {"calls": len(self.calls), "est_cost_usd": round(self.spent_usd, 6), "by_model": by_model,
                "request_ids": [c["request_id"] for c in self.calls if c.get("request_id")]}

    # ------------------------------------------------------------------ endpoints
    def responses(self, body: dict, *, purpose: str = "") -> dict:
        status, headers, raw, dt = self._http("POST", "/responses", data=json.dumps(body).encode(),
                                              headers={"Content-Type": "application/json"})
        resp = json.loads(raw)
        rid = next((headers[h] for h in REQUEST_ID_HEADERS if h in headers), None)
        usage = resp.get("usage") or {}
        cost = self.estimate_cost(body.get("model"), usage)
        self._record({"purpose": purpose, "endpoint": "/responses", "model": body.get("model"), "request_id": rid,
                      "response_id": resp.get("id"), "response_status": resp.get("status"), "http": status,
                      "latency_s": round(dt, 3), "usage": usage, "est_cost_usd": cost, "cached": False})
        resp["_request_id"], resp["_latency_s"], resp["_est_cost_usd"] = rid, dt, cost
        return resp

    def upload_file(self, path: str | Path, *, purpose: str = "user_data", mime: str = "video/mp4") -> str:
        path = Path(path)
        b = "----propriosam" + uuid.uuid4().hex
        body = (f'--{b}\r\nContent-Disposition: form-data; name="purpose"\r\n\r\n{purpose}\r\n'
                f'--{b}\r\nContent-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
                f"Content-Type: {mime}\r\n\r\n").encode() + path.read_bytes() + f"\r\n--{b}--\r\n".encode()
        status, headers, raw, dt = self._http("POST", "/files", data=body,
                                              headers={"Content-Type": f"multipart/form-data; boundary={b}"})
        resp = json.loads(raw)
        rid = next((headers[h] for h in REQUEST_ID_HEADERS if h in headers), None)
        self._record({"purpose": f"upload:{path.name}", "endpoint": "/files", "model": None, "request_id": rid,
                      "response_id": resp.get("id"), "http": status, "latency_s": round(dt, 3), "bytes": len(body),
                      "est_cost_usd": 0.0, "cached": False})
        return resp["id"]

    def sam_track_video(self, mp4: str | Path, prompt: str, *, include_confidence: bool = True,
                        mask_encoding: str = "one_bit", propagation_direction: str | None = None,
                        use_cache: bool = True) -> SamResult:
        mp4 = Path(mp4)
        clip_sha = sha256_file(mp4)
        metadata = {"include_confidence": "true" if include_confidence else "false", "mask_encoding": mask_encoding}
        if propagation_direction:
            metadata["propagation_direction"] = propagation_direction
        spec = {"prompt": prompt, "model": SAM_MODEL, "metadata": metadata}
        spec_hash = hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()[:16]
        cache_path = self.cache_dir / "sam_streams" / f"{clip_sha}__{spec_hash}__{SAM_MODEL}.json"
        if use_cache and cache_path.exists():
            c = json.loads(cache_path.read_text())
            self._record({"purpose": f"sam:{prompt}", "endpoint": "cache", "model": SAM_MODEL,
                          "request_id": c.get("request_id"), "response_id": c.get("response_id"), "http": 200,
                          "latency_s": 0.0, "usage": c.get("usage"), "est_cost_usd": 0.0, "cached": True,
                          "cache_path": str(cache_path)})
            return SamResult(prompt, SAM_MODEL, clip_sha, c["raw_text"], c.get("response_id"), c.get("request_id"),
                             True, c.get("frames_processed"), str(cache_path), metadata)
        file_id = self.upload_file(mp4)
        body = {"model": SAM_MODEL, "stream": False, "metadata": metadata,
                "input": [{"type": "message", "role": "user", "content": [
                    {"type": "input_text", "text": prompt}, {"type": "input_video", "file_id": file_id}]}]}
        resp = self.responses(body, purpose=f"sam:{prompt}")
        raw_text = self.output_text(resp)
        frames = (resp.get("usage") or {}).get("video_frames_processed")
        entry = {"clip_sha256": clip_sha, "clip_path": str(mp4), "spec": spec, "raw_text": raw_text,
                 "response_id": resp.get("id"), "request_id": resp["_request_id"], "frames_processed": frames,
                 "usage": resp.get("usage"), "created_at": utc_now(), "file_id": file_id,
                 "response": {k: v for k, v in resp.items() if not k.startswith("_")}}
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(entry, sort_keys=True))
        return SamResult(prompt, SAM_MODEL, clip_sha, raw_text, resp.get("id"), resp["_request_id"], False,
                         frames, str(cache_path), metadata)

    def muse(self, model: str, input_items: list, *, instructions: str | None = None, tools: list | None = None,
             tool_choice: str = "auto", text_format: dict | None = None, reasoning_effort: str = "medium",
             max_output_tokens: int = 4000, purpose: str = "") -> dict:
        body: dict[str, Any] = {"model": model, "input": input_items, "max_output_tokens": max_output_tokens,
                                "reasoning": {"effort": reasoning_effort}}
        if instructions:
            body["instructions"] = instructions
        if tools:
            body["tools"], body["tool_choice"] = tools, tool_choice
        if text_format:
            body["text"] = {"format": text_format}
        return self.responses(body, purpose=purpose)

    # ------------------------------------------------------------------ response helpers
    @staticmethod
    def output_text(resp: dict) -> str:
        parts = [c.get("text", "") for item in resp.get("output") or [] if item.get("type") == "message"
                 for c in item.get("content") or [] if c.get("type") in ("output_text", "text")]
        if any(parts):
            return "".join(parts)

        def walk(o):  # fallback: any string that carries SAM tokens
            if isinstance(o, str):
                return [o] if "<|box;" in o else []
            if isinstance(o, dict):
                return [t for v in o.values() for t in walk(v)]
            if isinstance(o, list):
                return [t for v in o for t in walk(v)]
            return []
        return "\n".join(walk(resp.get("output")))

    @staticmethod
    def function_calls(resp: dict) -> list[dict]:
        return [i for i in resp.get("output") or [] if i.get("type") == "function_call"]

    @staticmethod
    def replay_items(resp: dict) -> list[dict]:
        return [i for i in resp.get("output") or []]
