"""One pass = clip -> SAM 3.1 tracks -> frozen verifier -> overlay -> PassRecord.
Shared by the closed-loop orchestrator and the standalone clip evaluator."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from . import vision_tracker as vt
from .artifacts import PassRecord, sha256_file, write_json
from .meta_client import MetaClient
from .sensory_contract import SensoryContract
from .verifier import VerificationResult, verify


def track_and_verify(client: MetaClient, pass_dir: Path, *, index: int, label: str, clip_mp4: Path,
                     frames_dir: Path, contract: SensoryContract, capture: dict | None = None,
                     open_loop: dict | None = None, truth_hidden: Path | None = None,
                     project_tree_sha256: str | None = None, overlay_title: str = "") -> tuple[PassRecord, VerificationResult, dict]:
    pass_dir = Path(pass_dir)
    pass_dir.mkdir(parents=True, exist_ok=True)
    clip_dst = pass_dir / "clip.mp4"
    if Path(clip_mp4).resolve() != clip_dst.resolve():
        shutil.copy(clip_mp4, clip_dst)
    frames_dst = pass_dir / "frames"
    if Path(frames_dir).resolve() != frames_dst.resolve():
        if frames_dst.exists():
            shutil.rmtree(frames_dst)
        shutil.copytree(frames_dir, frames_dst)
    truth_dst = None
    if truth_hidden and Path(truth_hidden).exists():
        truth_dst = pass_dir / "truth_hidden.json"
        if Path(truth_hidden).resolve() != truth_dst.resolve():
            shutil.copy(truth_hidden, truth_dst)

    sam_dir = pass_dir / "sam"
    sam_dir.mkdir(exist_ok=True)
    roles = {"mover": contract.mover_concept, "barrier": contract.barrier_concept}
    sam_meta, detections, tracks = {}, {}, {}
    for role, concept in roles.items():
        r = client.sam_track_video(clip_dst, concept)
        raw_path = sam_dir / f"{role}.json"
        write_json(raw_path, {"concept": concept, "role": role, "model": r.model, "clip_sha256": r.clip_sha256,
                              "request_id": r.request_id, "response_id": r.response_id, "cached": r.cached,
                              "frames_processed": r.frames_processed, "metadata": r.metadata, "raw_text": r.raw_text})
        dets = vt.parse_sam_text(r.raw_text)
        tr = vt.build_track(concept, dets, contract.frame_count, tuple(contract.frame_size))
        detections[role], tracks[role] = dets, tr
        sam_meta[role] = {"concept": concept, "request_id": r.request_id, "response_id": r.response_id,
                          "cached": r.cached, "frames_processed": r.frames_processed, "raw_path": str(raw_path.relative_to(pass_dir.parent)),
                          "object_id_selected": tr.object_id, "selection": tr.selection,
                          "frames_tracked": len(tr.points), "coverage_total": round(tr.coverage(), 4)}
    tracks_path = pass_dir / "tracks.json"
    vt.save_tracks(tracks_path, tracks)
    result = verify(contract, tracks["mover"], tracks["barrier"])
    ver_path = write_json(pass_dir / "verification.json", result)

    def status_text(i: int) -> str:
        if result.t_fail is not None and i >= result.t_fail:
            return f"VIOLATION AT FRAME {result.t_fail}"
        if result.status.value == "PASS" and i == contract.frame_count - 1:
            return "PASS"
        return "tracking" if i < contract.frame_count - 1 else result.status.value
    overlay_path = pass_dir / "overlay.mp4"
    info = vt.render_overlay(frames_dst, overlay_path, detections, tracks, result.residual, status_text,
                             fps=contract.fps, title=overlay_title or label)
    rec = PassRecord(index=index, label=label, project_tree_sha256=project_tree_sha256,
                     clip_path=str(clip_dst.relative_to(pass_dir.parent)), clip_sha256=sha256_file(clip_dst),
                     frames_dir=str(frames_dst.relative_to(pass_dir.parent)), frame_count=contract.frame_count,
                     capture=capture or {}, open_loop=open_loop or {}, sam=sam_meta,
                     tracks_path=str(tracks_path.relative_to(pass_dir.parent)),
                     verification_path=str(ver_path.relative_to(pass_dir.parent)),
                     verification_status=result.status.value, t_fail=result.t_fail, max_residual=result.max_residual,
                     overlay_path=str(overlay_path.relative_to(pass_dir.parent)), overlay_sha256=sha256_file(overlay_path),
                     overlay_info=info, truth_hidden_path=None if truth_dst is None else str(truth_dst.relative_to(pass_dir.parent)))
    return rec, result, tracks
