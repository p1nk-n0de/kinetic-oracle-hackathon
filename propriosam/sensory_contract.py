"""Falsifiable sensory contracts.

The invariant *family* is fixed library code (screen-space barrier crossing,
see verifier.py). Muse Spark compiles a contract *instance* from the user's
objective and a scene brief: which calibrated concept is the mover and which
the barrier, the numeric parameters, the critical window, the coverage gates
and the falsifiable statement. The instance is hashed (frozen) before any clip
is scored and never changed afterwards."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from .meta_client import SPARK, MetaClient, utc_now

PROMPT_VERSION = "contract-compiler-v2"

RULE_DEFINITION = ("E(t) = y_bottom(barrier, t) - y_bottom(mover, t) in source pixels (y grows downward). "
                   "The mover is judged to have crossed the barrier when E(t) > threshold_px for "
                   "persistence_frames consecutive tracked frames. A PASS also requires the interaction to have "
                   "happened: max E(t) must reach at least -(approach_body_heights x the mover's median box height). "
                   "If the mover never came that close, the contract was not exercised and the result is INCONCLUSIVE.")


class CrossingRule(BaseModel):
    family: Literal["screen_space_barrier_crossing"] = "screen_space_barrier_crossing"
    mover_edge: Literal["bottom"] = "bottom"
    barrier_edge: Literal["bottom"] = "bottom"
    definition: str = RULE_DEFINITION
    threshold_px: int = Field(ge=0, le=20)
    persistence_frames: int = Field(ge=2, le=6)
    approach_body_heights: float = Field(default=1.0, ge=0.25, le=3.0)


class CoverageGate(BaseModel):
    critical_window: tuple[int, int]
    min_window_coverage: float = Field(ge=0.5, le=1.0)
    min_total_coverage: float = Field(ge=0.3, le=1.0)


class SensoryContract(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    contract_id: str
    objective: str
    scene_brief: str
    concept_vocabulary: list[str]
    statement: str
    mover_concept: str
    barrier_concept: str
    expected_pass_behaviour: str
    expected_fail_signature: str
    rule: CrossingRule
    coverage: CoverageGate
    frame_count: int = 80
    fps: int = 20
    frame_size: tuple[int, int] = (960, 540)
    compiled_by: dict | None = None
    frozen_sha256: str | None = None

    def freeze(self) -> "SensoryContract":
        body = self.model_dump(exclude={"compiled_by", "frozen_sha256"})
        self.frozen_sha256 = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
        return self

    def check_frozen(self) -> bool:
        body = self.model_dump(exclude={"compiled_by", "frozen_sha256"})
        return self.frozen_sha256 == hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def compile_schema(vocabulary: list[str], frame_count: int) -> dict:
    return {"type": "object", "additionalProperties": False,
            "required": ["statement", "mover_concept", "barrier_concept", "expected_pass_behaviour",
                         "expected_fail_signature", "threshold_px", "persistence_frames", "critical_window_start",
                         "critical_window_end", "min_window_coverage", "min_total_coverage"],
            "properties": {
                "statement": {"type": "string", "description": "One falsifiable sentence about what the tracks must show."},
                "mover_concept": {"type": "string", "enum": vocabulary, "description": "The object whose motion is under test."},
                "barrier_concept": {"type": "string", "enum": vocabulary, "description": "The object that must stop the mover."},
                "expected_pass_behaviour": {"type": "string"},
                "expected_fail_signature": {"type": "string"},
                "threshold_px": {"type": "integer", "description": "0-20. Residual pixels above which a crossing counts (0 = any crossing)."},
                "persistence_frames": {"type": "integer", "description": "2-6. Consecutive frames the crossing must persist (guards against jitter)."},
                "critical_window_start": {"type": "integer", "description": f"0-{frame_count - 1}. First frame of the window in which the interaction must be well tracked."},
                "critical_window_end": {"type": "integer", "description": f"0-{frame_count - 1}. Last frame of that window."},
                "min_window_coverage": {"type": "number", "description": "0.5-1.0. Fraction of window frames in which BOTH concepts must be tracked."},
                "min_total_coverage": {"type": "number", "description": "0.3-1.0. Fraction of all frames in which each concept must be tracked."}}}


COMPILER_INSTRUCTIONS = (
    "You are the contract compiler of a visual verification system. A downstream verifier measures screen-space "
    "geometry from SAM 3.1 object tracks over a short clip and decides PASS, FAIL or INCONCLUSIVE from numbers only. "
    "Turn the user's objective and the scene brief into ONE falsifiable sensory contract.\n"
    f"The invariant family is fixed and cannot be changed: screen_space_barrier_crossing. {RULE_DEFINITION}\n"
    "Choose mover_concept and barrier_concept from the concept vocabulary (short noun phrases the tracker is "
    "calibrated for). Choose threshold_px, persistence_frames, the critical window (the frames in which the "
    "mover reaches the barrier must lie inside it, with margin on both sides) and the coverage minima. "
    "Write the statement so that a clip could prove it false. Describe expected_pass_behaviour and "
    "expected_fail_signature in terms of what the two tracks and E(t) would look like. Output JSON only.")


def compile_contract(client: MetaClient, *, objective: str, scene_brief: str, vocabulary: list[str],
                     frame_count: int = 80, fps: int = 20, frame_size: tuple[int, int] = (960, 540),
                     model: str = SPARK, cache_dir: Path | None = None, use_cache: bool = True) -> SensoryContract:
    schema = compile_schema(vocabulary, frame_count)
    key_src = json.dumps({"objective": objective, "scene_brief": scene_brief, "vocab": vocabulary, "schema": schema,
                          "model": model, "v": PROMPT_VERSION}, sort_keys=True)
    key = hashlib.sha256(key_src.encode()).hexdigest()[:24]
    cache_dir = Path(cache_dir) if cache_dir else client.cache_dir / "contracts"
    cache_path = cache_dir / f"{key}.json"
    if use_cache and cache_path.exists():
        c = SensoryContract.model_validate_json(cache_path.read_text())
        if c.check_frozen():
            return c
    user = (f"Objective: {objective}\n\nScene brief: {scene_brief}\n\nConcept vocabulary: {json.dumps(vocabulary)}\n\n"
            f"Clip: {frame_count} frames at {fps} fps, {frame_size[0]}x{frame_size[1]} px.")
    fmt = {"type": "json_schema", "name": "sensory_contract", "schema": schema, "strict": True}
    items = [{"role": "user", "content": user}]
    last_err = None
    for attempt in range(2):
        resp = client.muse(model, items, instructions=COMPILER_INSTRUCTIONS, text_format=fmt,
                           reasoning_effort="medium", max_output_tokens=3000, purpose="compile_contract")
        text = client.output_text(resp)
        try:
            d = json.loads(text)
            contract = SensoryContract(
                contract_id=f"hurdle-walk-{key[:8]}", objective=objective, scene_brief=scene_brief,
                concept_vocabulary=vocabulary, statement=d["statement"], mover_concept=d["mover_concept"],
                barrier_concept=d["barrier_concept"], expected_pass_behaviour=d["expected_pass_behaviour"],
                expected_fail_signature=d["expected_fail_signature"],
                rule=CrossingRule(threshold_px=int(d["threshold_px"]), persistence_frames=int(d["persistence_frames"])),
                coverage=CoverageGate(critical_window=(int(d["critical_window_start"]), int(d["critical_window_end"])),
                                      min_window_coverage=float(d["min_window_coverage"]),
                                      min_total_coverage=float(d["min_total_coverage"])),
                frame_count=frame_count, fps=fps, frame_size=frame_size,
                compiled_by={"model": model, "request_id": resp.get("_request_id"), "response_id": resp.get("id"),
                             "created_at": utc_now(), "prompt_version": PROMPT_VERSION, "attempt": attempt + 1,
                             "raw_output": text})
            if contract.mover_concept == contract.barrier_concept:
                raise ValueError("mover and barrier must be different concepts")
            lo, hi = contract.coverage.critical_window
            if not (0 <= lo < hi <= frame_count - 1):
                raise ValueError("critical window out of range")
            contract.freeze()
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(contract.model_dump_json(indent=1))
            return contract
        except (KeyError, ValueError, ValidationError, json.JSONDecodeError) as e:
            last_err = e
            items = [{"role": "user", "content": user},
                     {"role": "assistant", "content": text or "(empty)"},
                     {"role": "user", "content": f"That output was rejected: {e}. Return corrected JSON only."}]
    raise RuntimeError(f"contract compilation failed after 2 attempts: {last_err}")
