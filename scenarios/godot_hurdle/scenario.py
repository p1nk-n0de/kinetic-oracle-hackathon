"""'The Agent That Believed Its Tool' — the Godot hurdle scenario definition.
Everything Muse is told about the scene lives here, so it can be audited for
ground-truth leakage. Nothing below names the fault."""
from __future__ import annotations

from propriosam.local_config import EXTRA_BANNED_TERMS, STUDIO

DEFECT_BASELINE = STUDIO / "tests/fixtures/pg_defect_hurdle"      # path never shown to Muse
KNOWN_GOOD_BASELINE = STUDIO / "example_game/proving_ground"

OBJECTIVE = ("Walking straight forward without jumping, the player must be physically stopped by the low hurdle "
             "lying across the corridor; it must not pass through or over it.")

SCENE_BRIEF = (
    "Third-person chase camera behind and above the player. The player is a small pale blue capsule that stays near "
    "the same screen position because the camera follows it. The corridor runs away from the camera; obstacles "
    "ahead first appear near the top of the frame and move down the frame toward the player's feet as the player "
    "approaches them. Visible objects: the pale blue capsule (player), a yellow bar lying across the corridor (a low "
    "hurdle about 0.55 m high), a small yellow plate further away (a pressure plate), an orange beacon at the far end, "
    "dark cubes, cyan floor edge lines, and white HUD text at the top-left and bottom-left. Action under test: the "
    "player walks straight forward for 240 physics ticks starting about 12 m before the hurdle, never jumping; one "
    "frame is captured every 3 ticks (80 frames).")

# Concept phrases the SAM 3.1 tracker was calibrated on for this scene (prior evidence: 'capsule' and 'yellow bar'
# track; 'robot', 'blue capsule' and 'game character' return nothing).
CONCEPT_VOCABULARY = ["capsule", "yellow bar", "yellow plate", "orange beacon", "dark cube"]

FRAME_COUNT, FPS, FRAME_SIZE = 80, 20, (960, 540)
CAPTURE_EVERY_TICKS, SETTLE_TICKS, SIDESTEP_TICKS = 3, 40, 25

# Source files Muse may list/read inside the staged project (relative, allowlist by suffix and directory).
SOURCE_ALLOW_DIRS = ("scripts", "scenes")
SOURCE_ALLOW_SUFFIXES = (".gd", ".tscn", ".godot")
SOURCE_DENY_NAMES = ("DEFECT_FIXTURE.md", "README.md", "oracle.yaml")
SOURCE_DENY_DIRS = ("scenarios", "addons", ".godot", "assets")

# Strings that must never appear in anything sent to Muse (prompt, evidence, tool results we author).
# (Source filenames Muse itself discovered and patched may legitimately appear in later turns' prompts, so no
# filename is banned; the anti-cheat test additionally asserts that the turn-1 prompt names no source file at all.)
BANNED_PROMPT_TERMS = ("defect", "defective", "pg_defect", "DEFECT_FIXTURE", "collision_layer", "collision_mask",
                       "layer 2", '"layer": 2', "hurdle_blocks_walking", "truth_hidden", "truth.json",
                       str(DEFECT_BASELINE), STUDIO.name, *EXTRA_BANNED_TERMS)
