# Evidence and media: terms

These terms apply, instead of the MIT licence in `LICENSE`, to:
- `runs/`: the 21 run bundles, the evaluation summary, the sanitisation ledger and the proof clip
  `runs/kinetic_oracle_demo_proof.mp4`
- `web/public/runs/`: the dashboard's copies of those bundles
- `tests/fixtures/`: recorded run data used by the tests
- the KINETIC-ORACLE demo video published with this entry

Copyright (c) 2026 p1nk-n0de, except as stated below. All rights are reserved, except that anyone may:
1. view, download and run these files, and replay and analyse the bundles, to review, verify or reproduce the results
   reported in this repository;
2. quote or show reasonable excerpts, including stills and short clips, in reviews, reports, articles and research, with
   attribution to KINETIC-ORACLE (https://github.com/p1nk-n0de/kinetic-oracle-hackathon);
3. redistribute unmodified copies with these terms, including in a deployment of the dashboard in `web/`.

These terms do not permit using the files to train, fine-tune or otherwise improve AI models. They do not limit the rights
that GitHub's Terms of Service give other GitHub users while this repository is public (viewing it and forking it on
GitHub), or any licence the author grants the hackathon organisers with the entry.

## What these files contain, and terms that also apply

**Outputs of Meta models.** The following were obtained through the Meta Model API:
- SAM 3.1 responses (`sam/*.json`, `tests/fixtures/*/*.txt`);
- Muse Spark and Muse Wonder messages and tool calls (`transcript.json`);
- patches written by Muse (`patches.json`, `diff.patch`);
- the contract values Muse compiled (`contract.json`).

Under the Meta Model API Terms of Service (last updated 2 October 2026, section 4.1), the author owns these outputs as
between the author and Meta, to the extent applicable law allows. They are included under the terms above only to the
extent the author holds rights in them. Those Terms continue to govern the author's use. For example, section 10.1(ix)
prohibits using outputs to train, fine-tune, distil or otherwise improve AI models that compete with Meta's. Nothing here
grants more than the author holds.

**A pre-existing test game.** The clips, overlays and proof clip record a Godot test game that the author built before
the hackathon. The transcripts contain excerpts of its source code, which Muse read through its tools. The game is not
part of the entry. It is included only as evidence, under the terms above.

**Third-party material.**
- Godot engine log lines in the bundles are reproduced as logged.
- The demo video's captions are rendered in Apple's San Francisco system font, and the proof clip's in Helvetica, on macOS.
  No font file is distributed.
- The demo video's music is generated procedurally by its build script.

**Redacted copies.** Some files are published with identity strings replaced by `<redacted:…>` markers. See
`docs/SANITIZATION.md`.

These files are provided "as is", without warranty of any kind.
