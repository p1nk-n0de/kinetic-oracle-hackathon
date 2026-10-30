"""Deterministic residual evaluator.

Frozen rule family (declared before any clip is scored; the hash of this
module's rule code is recorded in every result):

    E(t) = y_bottom(barrier, t) - y_bottom(mover, t)        [source pixels]
    VIOLATION  <=>  E(t) > threshold_px for `persistence_frames` consecutive
                    frames in which both concepts are tracked
    t_fail      =  first frame of the first such run

Status: FAIL if a violation run exists; otherwise INCONCLUSIVE when any
coverage gate is unmet, including a concept SAM could not find at all (never
PASS on missing evidence); otherwise PASS. ERROR only when no track object was
supplied. No tool status and no model text is consulted."""
from __future__ import annotations

import hashlib
import inspect
from enum import Enum

from pydantic import BaseModel

from .sensory_contract import SensoryContract
from .vision_tracker import Track


class VerificationStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"
    ERROR = "ERROR"


class VerificationResult(BaseModel):
    status: VerificationStatus
    contract_id: str
    contract_sha256: str | None
    rule_sha256: str
    frame_count: int
    residual: list[float | None]
    mover_bottom: list[float | None]
    barrier_bottom: list[float | None]
    t_fail: int | None = None
    violation_run: list[int] | None = None
    max_residual: float | None = None
    max_residual_frame: int | None = None
    margin_px: float | None = None
    coverage: dict
    evidence_rows: list[dict]
    reasons: list[str]


def _residual_series(contract: SensoryContract, mover: Track, barrier: Track) -> list[float | None]:
    out: list[float | None] = []
    for t in range(contract.frame_count):
        mb, bb = mover.bottom(t), barrier.bottom(t)
        out.append(None if mb is None or bb is None else float(bb - mb))
    return out


def _scan_violation(residual: list[float | None], threshold_px: int, persistence: int) -> list[int] | None:
    run: list[int] = []
    for t, e in enumerate(residual):
        if e is not None and e > threshold_px:
            run.append(t)
            if len(run) >= persistence:
                return run
        else:
            run = []
    return None


def rule_sha256() -> str:
    src = inspect.getsource(_residual_series) + inspect.getsource(_scan_violation) + inspect.getsource(verify)
    return hashlib.sha256(src.encode()).hexdigest()


def verify(contract: SensoryContract, mover: Track | None, barrier: Track | None) -> VerificationResult:
    n = contract.frame_count
    base = dict(contract_id=contract.contract_id, contract_sha256=contract.frozen_sha256, rule_sha256=rule_sha256(),
                frame_count=n)
    if mover is None or barrier is None:
        missing = [name for name, tr in (("mover", mover), ("barrier", barrier)) if tr is None]
        return VerificationResult(status=VerificationStatus.ERROR, residual=[None] * n, mover_bottom=[None] * n,
                                  barrier_bottom=[None] * n, coverage={}, evidence_rows=[],
                                  reasons=[f"no track object supplied for {m}" for m in missing], **base)
    residual = _residual_series(contract, mover, barrier)
    win = tuple(contract.coverage.critical_window)
    both_total = sum(1 for e in residual if e is not None) / n
    both_window = sum(1 for t in range(win[0], win[1] + 1) if residual[t] is not None) / (win[1] - win[0] + 1)
    coverage = {"mover_total": round(mover.coverage(), 4), "barrier_total": round(barrier.coverage(), 4),
                "both_total": round(both_total, 4), "mover_window": round(mover.coverage(win), 4),
                "barrier_window": round(barrier.coverage(win), 4), "both_window": round(both_window, 4),
                "critical_window": list(win), "min_window_coverage": contract.coverage.min_window_coverage,
                "min_total_coverage": contract.coverage.min_total_coverage}
    reasons: list[str] = []
    run = _scan_violation(residual, contract.rule.threshold_px, contract.rule.persistence_frames)
    tracked = [(t, e) for t, e in enumerate(residual) if e is not None]
    max_e, max_t = (max(tracked, key=lambda x: x[1])[1], max(tracked, key=lambda x: x[1])[0]) if tracked else (None, None)
    gates_ok = (both_window >= contract.coverage.min_window_coverage
                and mover.coverage() >= contract.coverage.min_total_coverage
                and barrier.coverage() >= contract.coverage.min_total_coverage)
    if run:
        status = VerificationStatus.FAIL
        reasons.append(f"E(t) > {contract.rule.threshold_px}px for {len(run)} consecutive tracked frames starting at frame {run[0]}")
    elif not gates_ok:
        status = VerificationStatus.INCONCLUSIVE
        for role, concept, tr in (("mover", contract.mover_concept, mover), ("barrier", contract.barrier_concept, barrier)):
            if tr.object_id is None:
                reasons.append(f"SAM 3.1 returned no track for {role} concept '{concept}'")
        if both_window < contract.coverage.min_window_coverage:
            reasons.append(f"both-tracked coverage in window {win} = {both_window:.2f} < {contract.coverage.min_window_coverage}")
        if mover.coverage() < contract.coverage.min_total_coverage:
            reasons.append(f"mover coverage {mover.coverage():.2f} < {contract.coverage.min_total_coverage}")
        if barrier.coverage() < contract.coverage.min_total_coverage:
            reasons.append(f"barrier coverage {barrier.coverage():.2f} < {contract.coverage.min_total_coverage}")
    else:
        status = VerificationStatus.PASS
        reasons.append(f"no crossing: max E(t) = {max_e:+.1f}px at frame {max_t}; coverage gates met")
    rows = []
    focus = set(range(win[0], win[1] + 1))
    if run:
        focus |= set(range(max(run[0] - 6, 0), min(run[0] + 10, n)))
    for t in sorted(focus):
        mp, bp = mover.points.get(t), barrier.points.get(t)
        rows.append({"frame": t, "E_px": residual[t],
                     "mover": None if not mp else {"cx": round(mp.cx, 1), "cy": round(mp.cy, 1), "bottom": mp.bottom,
                                                   "vx": None if mp.vx is None else round(mp.vx, 2),
                                                   "vy": None if mp.vy is None else round(mp.vy, 2)},
                     "barrier": None if not bp else {"cx": round(bp.cx, 1), "cy": round(bp.cy, 1), "bottom": bp.bottom,
                                                     "vx": None if bp.vx is None else round(bp.vx, 2),
                                                     "vy": None if bp.vy is None else round(bp.vy, 2)}})
    return VerificationResult(status=status, residual=residual, mover_bottom=[mover.bottom(t) for t in range(n)],
                              barrier_bottom=[barrier.bottom(t) for t in range(n)], t_fail=run[0] if run else None,
                              violation_run=run, max_residual=max_e, max_residual_frame=max_t,
                              margin_px=(None if max_e is None else round(-max_e, 2)), coverage=coverage,
                              evidence_rows=rows, reasons=reasons, **base)
