"""EncounterReader: read the enemy party Pokemon from GBA memory.

gEnemyParty[0] holds the wild Pokemon encountered in battle.
gPlayerParty[0] holds the first slot of the player's party.

Each party slot is 100 bytes (PARTY_SLOT_SIZE).
We read 80 bytes (the encrypted header + substructs) which is enough
for full decryption — the remaining 20 bytes are battle-only stats.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pokefinder.pokemon.decoder import decode_pokemon
from pokefinder.pokemon.structs import Pokemon

if TYPE_CHECKING:
    from pokefinder.memory.reader import MemoryReader
    from pokefinder.memory.symbols import SymbolTable


# Bytes needed from each party slot for full decryption (header + 4 substructs)
_DECODE_SIZE = 80

# Full party slot size in RAM
_PARTY_SLOT_SIZE = 100


class EncounterReader:
    """Reads and decodes wild encounter Pokemon from GBA memory.

    Parameters
    ----------
    reader:
        Active MemoryReader.
    symbols:
        Symbol table for the loaded ROM.
    """

    def __init__(self, reader: "MemoryReader", symbols: "SymbolTable") -> None:
        self._reader = reader
        self._enemy_party_addr = symbols.address("gEnemyParty")
        self._player_party_addr = symbols.address("gPlayerParty")

    def read_enemy_slot(self, slot: int = 0) -> Pokemon:
        """Read and decode gEnemyParty[slot].

        The wild Pokemon is always at slot 0 in a wild encounter.
        """
        addr = self._enemy_party_addr + slot * _PARTY_SLOT_SIZE
        raw = self._reader.read_bytes(addr, _DECODE_SIZE)
        return decode_pokemon(raw)

    def read_player_slot(self, slot: int = 0) -> Pokemon:
        """Read and decode gPlayerParty[slot]."""
        addr = self._player_party_addr + slot * _PARTY_SLOT_SIZE
        raw = self._reader.read_bytes(addr, _DECODE_SIZE)
        return decode_pokemon(raw)

    def wild_pokemon(self) -> Pokemon:
        """Convenience: return the current wild encounter (enemy slot 0)."""
        return self.read_enemy_slot(0)
