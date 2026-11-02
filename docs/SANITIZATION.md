# Sanitisation of this public copy

This repository is a sanitised copy of a private development repository. Its history was rewritten with `git-filter-repo`
to remove personal identity metadata, local paths and the names of the author's private tooling. **It is not
byte-identical to the originals.** Some recorded evidence files carry visible `<redacted:…>` markers, and every commit id
differs. No experiment was re-run, regenerated or edited. No verdict, measurement, SAM 3.1 output, model decision, patch,
test result, score, replay outcome or timestamp was changed.

No credential was found in any commit, blob or commit message at any point.

## Four kinds of evidence

| | What it is | Where | Who can check it |
|---|---|---|---|
| **1. Private originals** | The bundles exactly as the runs wrote them, and the original history | Kept offline by the author, in two backups. Not published. | The author |
| **2. Sanitised public evidence** | `runs/` and the dashboard copies in `web/public/runs/` | This repository | Anyone |
| **3. Results recomputed from the public evidence** | Offline replay of all 21 bundles, which reproduces every verdict from the stored SAM 3.1 output; the tests; the evaluation tables; the prompt-hash check below | This repository | Anyone |
| **4. Checks that need the private originals** | That each redacted file equals its original apart from the markers; that the hashes recorded in the manifests are those of the originals; the banned-term screen re-run with the unredacted terms | Run by the author on 2 Nov 2026; results below | The author |

## What changed

The replacements are literal, deterministic and chosen by file path. Binary files (clips, overlays, images) were never
modified. Every rule was applied to every commit, so no earlier version of a file keeps the original strings.

### Commit metadata
- Author and committer: `p1nk-n0de` with the account's GitHub noreply address, on every commit.
- Dates, messages, order and merge structure are unchanged. The 16 development commits, which contain the system and all
  21 runs, date from 30 Oct 2026, 12:03 to 14:15 UTC. Three later commits contain no new runs: release preparation (30 Oct,
  15:23 UTC), a README provenance section (2 Nov) and this sanitisation (2 Nov).
- Commit ids differ from the private repository. The mapping is kept privately.
- Three commits made by a cloud coding session were signed. The rewrite removed those signatures.
- A `Claude-Session:` trailer linking to a private session was removed from three commit messages.

### Code and documentation
- The private Godot studio's names are replaced by generic ones: `godot-studio` (directory), `godot-studio-mcp` (MCP entry
  point), `godot_studio` (Python package), `StudioBridge` (bridge class) and `GODOT_STUDIO_EXTRA_ROOT` (extra-root variable).
- An absolute path to the `uv` binary became `uv`. An external drive's label became `<external-volume>` in code and
  `<redacted:volume>` in documentation. Machine-specific path prefixes became `<repo>`, `<godot-studio>`, `<scratch>` and `~`,
  the placeholders the code itself writes.
- One deadline is now stated in UTC, which is the same instant. A reference to a pull request in the private repository and a
  merge-conflict marker naming a private branch were neutralised.
- One operational note was removed from `docs/BUILD_STATE.md` in every commit.
- Removed from every commit: six raw Claude Code session logs from a pre-build test (`docs/prior_evidence/2026-10-30/live_loop{1,2,3}.jsonl`
  and `loop{1,2,3}.txt`) and an internal pre-publication scanner. The author keeps private copies. The final bundles supersede those tests.
- In the 2 Nov commit, the studio's location, MCP entry point, extra-root variable name, `uv` path and any extra banned prompt
  terms come from the environment (`propriosam/local_config.py`, untracked `scripts/env.local.sh`). The live loop can therefore be
  pointed at any copy of the studio. With the author's local settings, the configuration equals what ran on 30 Oct (check 4 below).

### Recorded evidence
In `runs/`, `web/public/runs/` and `tests/fixtures/`:
- `<redacted:studio>` replaces the name of the author's private studio wherever a run recorded it:
  - in the environment-audit preview in all 21 `mcp_calls.jsonl` files, and a log-line preview in one of them;
  - in two transcripts, inside tool results Muse received: a project file it read and a runtime log line;
  - in the anti-cheat banned-term list recorded in 19 `prompt.json` files and 21 `run_manifest.json` files.
- `<redacted:volume>` replaces the label of a local external drive in those same banned-term lists.
- `environment.git.commit` in each `run_manifest.json` holds the rewritten id of the commit that produced the run. Each one
  resolves in this history and is an ancestor of the commit that added the bundle. Manifests are not part of their own hash lists.
- The superseded exploratory bundles in early commits, which are not in the final tree, received the same replacements.

`runs/SANITIZATION_LEDGER.json` lists every redacted file with its recorded and present hash, its marker counts and the JSON
location of every marker. 42 bundle files are redacted: 21 `mcp_calls.jsonl`, 19 `prompt.json` and 2 `transcript.json`.
The dashboard copies of the prompts and transcripts are the same files.

### Left as recorded
These are part of the reproduction context:
- hardware and OS strings (Apple M4 Pro, macOS 27) in the environment audit and in recorded Godot logs;
- Godot and Python versions;
- run ids and timestamps;
- Meta request ids, response ids, file ids and spend;
- the pre-existing test game's name, the excerpts of its source that Muse read through its tools, and footage of it.

## What did not change
Byte for byte, against the hashes the runs recorded: every clip and overlay, every raw SAM 3.1 response, every track and
verification, every contract, the hidden-truth files, the API call logs and Muse's patches and diffs. `runs/evaluation_summary.json`,
`docs/EVALUATION_REPORT.md` and the proof clip are also unchanged.

No marker sits in model-authored text. In the two redacted transcripts, the markers are inside tool results, never in Muse's
messages or tool calls. The prompt text Muse received is unchanged: each prompt's `prompt_sha256` recomputes from the published
`prompt.json`, using the tool specifications of the code at the commit that run recorded (`tests/unit/test_sanitization.py`).

## How verification treats redacted files
Manifests keep the hashes recorded at run time. These are the hashes of the private originals, and they were not updated.

A file whose present hash differs from its recorded hash is accepted only when both of these hold:
- It is a `mcp_calls.jsonl`, `prompt.json` or `transcript.json`.
- The ledger names both its recorded hash and its present hash.

Anything else that differs fails, and the ledger can never excuse a replay input.

`scripts/replay_run.py` reports these files as redacted copies, separately from byte-original files. The dashboard marks them
"redacted copy · matches the sanitisation ledger". `python -m scripts.build_sanitization_ledger --check` confirms that the ledger
matches the files.

What the public cannot verify is that a redacted file equals its original apart from the markers. The author checked that
against the private originals.

## Checks run against the private originals (2 Nov 2026)
1. Each of the 16 development commits was compared with the original history. Every file version equals the replacements
   listed above applied to the original, with commit ids remapped. Every message equals the original apart from the removed
   trailers. That is 5,045 file versions: 4,546 unchanged, 499 changed only by these rules, 0 differences. The later commits
   have no original counterpart.
2. The hashes recorded in the 21 manifests match the original files: 21 of 21 bundles, 0 differences.
3. In the final tree, 781 evidence files are byte-identical to the originals. The other 105 equal the rules applied to their
   original: the 42 redacted bundle files, the 21 manifests, and the dashboard copies of 42 of those files.
4. With the author's local settings, the configurable code reproduces the MCP launch command, the extra-root variable, the
   banned-term list, the baseline paths and the path scrubbing used on 30 Oct.
5. The banned-term screen was re-run on all 19 recorded prompts with the unredacted terms, as designed: the screen excludes
   Muse's own earlier patches, which it quotes back. It found no hits. None of the redacted strings appears anywhere in any
   prompt, including the quoted patches.
