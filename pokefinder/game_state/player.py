"""PlayerStateReader: read the player avatar state from GBA memory.

The gPlayerAvatar struct tracks the player's current activity.
The key field is `flags` (or `state`), which tells us whether the
player is currently controllable (i.e., not in a menu, cutscene, etc.).

gPlayerAvatar struct layout (from pret source):
    Offset 0x00: flags (u8)  — bitmask of avatar state flags
    Offset 0x01: runningState (u8)  — movement state
    Offset 0x02: tileTransitionState (u8)
    Offset 0x03: mapObjectId (u8)

The PLAYER_AVATAR_FLAG_CONTROLLABLE bit is defined differently per game.
In Emerald/FR/LG: bit 1 (0x02) means "on foot" / controllable.
In Ruby/Sapphire: similar.

Robust strategy: treat the player as controllable when neither the
battle callback is active nor a scripted movement is in progress.
We check `runningState` == 0 (RUNNING_STATE_NOT_MOVING) or == 2 as a
proxy for controllability.

For practical automation, we simply gate all inputs on "not in battle"
and "flags != 0xFF (warp in progress)".
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pokefinder.memory.reader import MemoryReader
    from pokefinder.memory.symbols import SymbolTable


# The "on foot, can accept input" bitmask for gPlayerAvatar.flags.
# Source: pokeemerald/include/player_pc.h, PLAYER_AVATAR_FLAG_ON_FOOT = 0x01
_FLAG_ON_FOOT = 0x01
_FLAG_SURFING = 0x02
_FLAG_UNDERWATER = 0x04
_FLAG_MACH_BIKE = 0x08
_FLAG_ACRO_BIKE = 0x10


class PlayerStateReader:
    """Reads the player avatar state from GBA memory.

    Parameters
    ----------
    reader:
        Active MemoryReader.
    symbols:
        Symbol table for the loaded ROM.
    """

    def __init__(self, reader: "MemoryReader", symbols: "SymbolTable") -> None:
        self._reader = reader
        self._player_avatar_addr = symbols.address("gPlayerAvatar")

    def avatar_flags(self) -> int:
        """Return the raw gPlayerAvatar.flags byte."""
        return self._reader.u8(self._player_avatar_addr + 0x00)

    def running_state(self) -> int:
        """Return gPlayerAvatar.runningState."""
        return self._reader.u8(self._player_avatar_addr + 0x01)

    def tile_transition_state(self) -> int:
        """Return gPlayerAvatar.tileTransitionState."""
        return self._reader.u8(self._player_avatar_addr + 0x02)

    def is_on_foot(self) -> bool:
        """Return True if the player is on foot (not on a bike or surfing)."""
        flags = self.avatar_flags()
        return bool(flags & _FLAG_ON_FOOT)

    def is_controllable(self) -> bool:
        """Return True when the player avatar can accept movement inputs.

        A player is considered controllable when:
          - They are on foot (flag 0x01 is set)
          - No tile transition is in progress (tileTransitionState == 0)

        This is the condition we gate all automation inputs on.
        """
        if not self.is_on_foot():
            return False
        return self.tile_transition_state() == 0
