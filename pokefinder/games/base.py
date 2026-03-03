"""GameProfile abstract base class.

Each supported game provides:
  - A set of 4-char ROM codes that identify it (from the GBA ROM header)
  - The path to its .sym file (relative to the symbols/ directory)
  - A human-readable name
  - Game-specific hunt method capabilities
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

_SYMBOLS_DIR = Path(__file__).parent / "symbols"


class GameProfile(ABC):
    """Abstract base for Gen 3 game profiles."""

    # 4-char GBA game codes that identify this game (e.g. "BPEE")
    ROM_CODES: tuple[str, ...]

    # Filename of the .sym file in pokefinder/games/symbols/
    SYM_FILE: str

    # Human-readable display name
    DISPLAY_NAME: str

    # Whether soft-reset hunts are supported (starter / legendary)
    SUPPORTS_SOFT_RESET: bool = True

    # Whether wild encounter hunts are supported
    SUPPORTS_WILD_HUNT: bool = True

    # ------------------------------------------------------------------
    # Symbol file access
    # ------------------------------------------------------------------

    @property
    def sym_path(self) -> Path:
        return _SYMBOLS_DIR / self.SYM_FILE

    # ------------------------------------------------------------------
    # Party/encounter struct size
    # ------------------------------------------------------------------

    # Party Pokemon slot size in bytes (always 100 for party)
    PARTY_SLOT_SIZE: int = 100

    # Number of slots in gPlayerParty / gEnemyParty
    PARTY_SIZE: int = 6

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def for_rom_code(cls, code: str) -> "GameProfile":
        """Return the GameProfile instance for the given ROM code."""
        from pokefinder.games.emerald import EmeraldProfile
        from pokefinder.games.ruby_sapphire import RubyProfile, SapphireProfile
        from pokefinder.games.firered_leafgreen import FireRedProfile, LeafGreenProfile

        profiles: list[GameProfile] = [
            EmeraldProfile(),
            RubyProfile(),
            SapphireProfile(),
            FireRedProfile(),
            LeafGreenProfile(),
        ]
        for profile in profiles:
            if code in profile.ROM_CODES:
                return profile
        raise ValueError(f"Unknown ROM code: {code!r}. Supported: BPEE, AXVE, AXPE, BPRE, BPGE")
