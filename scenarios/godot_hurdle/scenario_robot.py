"""The same hurdle objective on the real game build, whose player is a small dark
robot model, not a capsule. Used as a generalisation check: same frozen rule,
visually different mover, freshly compiled contract."""
from __future__ import annotations

from .scenario import (BANNED_PROMPT_TERMS, CAPTURE_EVERY_TICKS, DEFECT_BASELINE, FPS, FRAME_COUNT, FRAME_SIZE,  # noqa: F401
                       KNOWN_GOOD_BASELINE, OBJECTIVE, SETTLE_TICKS, SIDESTEP_TICKS, SOURCE_ALLOW_DIRS,
                       SOURCE_ALLOW_SUFFIXES, SOURCE_DENY_DIRS, SOURCE_DENY_NAMES)

SCENE_BRIEF = (
    "Third-person chase camera behind and above the player. The player is a small dark robot with a round head and "
    "a boxy body that stays near the same screen position because the camera follows it. The corridor runs away from "
    "the camera; obstacles ahead first appear near the top of the frame and move down the frame toward the player's "
    "feet as the player approaches them. Visible objects: the small robot (player), a yellow bar lying across the "
    "corridor (a low hurdle about 0.55 m high), a small yellow plate further away (a pressure plate), an orange "
    "beacon at the far end, dark cubes, cyan floor edge lines, and white HUD text at the top-left and bottom-left. "
    "Action under test: the player walks straight forward for 240 physics ticks starting about 12 m before the "
    "hurdle, never jumping; one frame is captured every 3 ticks (80 frames).")

CONCEPT_VOCABULARY = ["small robot", "yellow bar", "yellow plate", "orange beacon", "dark cube"]
