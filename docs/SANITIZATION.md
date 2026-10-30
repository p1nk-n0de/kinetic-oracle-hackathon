# History sanitization

Before publication, this repository's history was rewritten once with `git-filter-repo`. No credential was found in any commit,
blob or commit message at any point; the rewrite exists to remove machine-specific paths and personal metadata. Commit ids here
differ from the private development repository. The mapping between them is kept privately and is not published.

## What was preserved
- All 16 development commits, in order, with their original author and committer dates, subjects and merge structure. The development
  history runs from 12:03 to 14:15 UTC on 2026-10-30. The commit that adds this file is dated later and is the only new one.
- The 21 final run bundles. Every file in them except `run_manifest.json` is byte-identical to the original, including all clips, overlays, raw
  SAM output, tracks, verifications, prompts and transcripts. `runs/evaluation_summary.json`, `docs/EVALUATION_REPORT.md` and the proof
  clip are also byte-identical. No experiment was re-run, regenerated or edited for this rewrite.

## What changed
1. **Commit identity.** Author and committer emails now use the GitHub noreply address.
2. **Run manifests.** `environment.git.commit` in each `run_manifest.json` (in `runs/` and in the copies under `web/public/runs/`) now holds the
   rewritten id of the commit that produced the run. Each resolves in this history and is an ancestor of the commit that added the bundle.
   No other manifest field changed. `run_manifest.json` is not part of a bundle's own hash list, so replay is unaffected.
3. **Local paths in historical files.** Machine-specific path prefixes in older commits were replaced with `<repo>`, `<godot-studio>`, `<scratch>`
   and `~`, the same placeholders the code writes today. Only those prefixes changed.
4. **Removed from all commits:** six raw Claude Code session logs from a pre-build test (`docs/prior_evidence/2026-10-30/live_loop{1,2,3}.jsonl`
   and `loop{1,2,3}.txt`) and an internal pre-publication scanner (`scripts/privacy_scan.py`). Private copies are retained. The final
   bundles supersede those tests.
5. **Commit messages.** A `Claude-Session:` trailer linking to a private session was removed from three commits.
6. **Documentation.** One operational note was removed from `docs/BUILD_STATE.md` across history. In this final commit, the internal to-do
   list was removed from that file, one stale example path was corrected, and this file was added.

## Known consequences
- The three commits made by the cloud session were signed. Rewriting removes those signatures.
- Exploratory bundles from early commits were superseded and are not in the final tree. Where path prefixes were replaced in them, their recorded
  hashes no longer match at those historical commits. The 21 final bundles are unaffected and replay exactly:
  `python -m scripts.replay_run --run-dir runs/<run_id>`.
- `prompt.json` and each manifest record the anti-cheat banned-term list as it was used, which includes the external drive label `<redacted:volume>`
  and the name of the separate Godot tooling repository. They are left as recorded.
