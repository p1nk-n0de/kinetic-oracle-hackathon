# Third-party notices

This repository contains no third-party source code. The components below are installed separately, used as services or
used as tools. Their own licences apply.

## Python dependencies (`pyproject.toml`; installed by pip, not included)
| Package | Version tested | Licence |
|---|---|---|
| mcp | 2.3.0 | MIT |
| pydantic | 2.14.2 | MIT |
| pillow | 13.0.0 | MIT-CMU |
| numpy | 2.5.4 | BSD-3-Clause, with 0BSD, MIT, Zlib and CC0-1.0 parts |
| pyyaml | 6.0.3 | MIT |
| meta-sam-parser (Meta Platforms, Inc.) | 0.1.0 | SAM License (Meta; not an open-source licence) |
| pytest (development only) | 9.2.0 | MIT |

**SAM acknowledgement.** KINETIC-ORACLE uses Meta's SAM 3.1, through the Meta Model API, and Meta's `meta-sam-parser`
library for video segmentation and tracking. The SAM License (last updated 19 November 2025) requires research submitted
for publication using the SAM Materials to acknowledge that use; this paragraph and the README do so. It requires a copy of
the licence with any redistribution of the SAM Materials. This repository does not redistribute `meta-sam-parser`; it only
imports it. The licence also restricts certain uses, including military, warfare and nuclear
applications and uses subject to trade controls. Anyone installing `meta-sam-parser` accepts that licence.

## Web dashboard (`web/package.json`, `web/package-lock.json`; installed by npm, not included)
- **Direct dependencies:**
  - react and react-dom 19.3.1 (MIT)
  - vite 8.3.5 (MIT)
  - tailwindcss and @tailwindcss/vite 4.3.3 (MIT)
  - @vitejs/plugin-react 6.1.2 (MIT)
  - typescript 5.9.3 (Apache-2.0)
  - @types/react and @types/react-dom (MIT)
- **The full lockfile** has 86 packages: 57 MIT, 24 MPL-2.0, 2 Apache-2.0, 2 ISC and 1 BSD-3-Clause. The 24 MPL-2.0 packages
  are `lightningcss` and its platform binaries, which are build tools and are not bundled.
- **A built dashboard** (`web/dist`, not in this repository) bundles React and React DOM (MIT) with their licence comments
  removed. Include their MIT notice when you distribute a build.

## Services
Meta Model API: SAM 3.1, Muse Spark 1.3 and Muse Wonder 1.0. Use is governed by the Meta Model API Terms of Service (last
updated 2 October 2026). Outputs recorded in `runs/` are covered by `EVIDENCE_AND_MEDIA.md`.

## Tools used but not distributed
- Godot 4.6.2 (MIT), the engine of the pre-existing test game
- ffmpeg (LGPL-2.1-or-later, with GPL parts depending on the build)
- uv
- Claude Code, used for development only; no runtime call goes to it
