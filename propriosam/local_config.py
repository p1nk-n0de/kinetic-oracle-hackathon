"""Where the pre-existing Godot studio lives on this machine, and how to launch its MCP server.

The studio is a separate project, not part of this repository. Its location, MCP entry point and the variable
it reads for an extra project root come from the environment, with generic defaults. `scripts/env.sh` sources an
untracked `scripts/env.local.sh` for these settings. Offline replay, the tests and the dashboard need none of them."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

STUDIO = Path(os.environ.get("KO_GODOT_STUDIO", "~/Projects/godot-studio")).expanduser()
MCP_ENTRY = os.environ.get("KO_GODOT_MCP_ENTRY", "godot-studio-mcp")
EXTRA_ROOT_ENV = os.environ.get("KO_GODOT_EXTRA_ROOT_ENV", "GODOT_STUDIO_EXTRA_ROOT")
UV = os.environ.get("KO_UV") or shutil.which("uv") or "uv"
# Machine-specific strings that must never reach a model prompt, beyond the scenario's own list (os.pathsep-separated).
EXTRA_BANNED_TERMS = tuple(t for t in os.environ.get("KO_EXTRA_BANNED_TERMS", "").split(os.pathsep) if t)
