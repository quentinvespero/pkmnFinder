"""Pokemon Ruby and Sapphire game profiles."""

from __future__ import annotations

from pokefinder.games.base import GameProfile


class RubyProfile(GameProfile):
    ROM_CODES = ("AXVE",)
    SYM_FILE = "pokeruby.sym"
    DISPLAY_NAME = "Pokemon Ruby"
    SUPPORTS_SOFT_RESET = True
    SUPPORTS_WILD_HUNT = True


class SapphireProfile(GameProfile):
    ROM_CODES = ("AXPE",)
    SYM_FILE = "pokesapphire.sym"
    DISPLAY_NAME = "Pokemon Sapphire"
    SUPPORTS_SOFT_RESET = True
    SUPPORTS_WILD_HUNT = True
