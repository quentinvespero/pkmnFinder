"""Pokemon FireRed and LeafGreen game profiles."""

from __future__ import annotations

from pokefinder.games.base import GameProfile


class FireRedProfile(GameProfile):
    ROM_CODES = ("BPRE",)
    SYM_FILE = "pokefirered.sym"
    DISPLAY_NAME = "Pokemon FireRed"
    SUPPORTS_SOFT_RESET = True
    SUPPORTS_WILD_HUNT = True


class LeafGreenProfile(GameProfile):
    ROM_CODES = ("BPGE",)
    SYM_FILE = "pokeleafgreen.sym"
    DISPLAY_NAME = "Pokemon LeafGreen"
    SUPPORTS_SOFT_RESET = True
    SUPPORTS_WILD_HUNT = True
