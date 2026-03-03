"""Pokemon Emerald game profile (ROM code BPEE)."""

from __future__ import annotations

from pokefinder.games.base import GameProfile


class EmeraldProfile(GameProfile):
    ROM_CODES = ("BPEE",)
    SYM_FILE = "pokeemerald.sym"
    DISPLAY_NAME = "Pokemon Emerald"
    SUPPORTS_SOFT_RESET = True
    SUPPORTS_WILD_HUNT = True
