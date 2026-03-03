"""BattleStateReader: detect whether the game is in an active battle.

Detection strategy: compare gMain.callback1 (a function pointer stored in
the gMain struct at offset 0x00) against the address of BattleMainCB1 in
the symbol table.

This is more reliable than gBattleTypeFlags, which can hold stale values
between battles.

gMain struct layout (offset 0 = callback1):
    0x00 : callback1  (4 bytes, function pointer)
    0x04 : callback2  (4 bytes, function pointer)
    ...

All three game families place gMain in IWRAM (0x03xxxxxx).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pokefinder.memory.reader import MemoryReader
    from pokefinder.memory.symbols import SymbolTable


class BattleStateReader:
    """Reads battle state from GBA memory.

    Parameters
    ----------
    reader:
        Active MemoryReader connected to a running emulator.
    symbols:
        Symbol table for the loaded ROM.
    """

    def __init__(self, reader: "MemoryReader", symbols: "SymbolTable") -> None:
        self._reader = reader
        self._symbols = symbols
        self._battle_cb1_addr = symbols.address("BattleMainCB1")
        self._gmain_addr = symbols.address("gMain")

    def in_battle(self) -> bool:
        """Return True if the game is currently in a battle.

        Reads gMain.callback1 and compares it to BattleMainCB1.
        """
        # gMain.callback1 is at gMain + 0x00
        callback1 = self._reader.ptr(self._gmain_addr + 0x00)
        return callback1 == self._battle_cb1_addr

    def battle_type_flags(self) -> int:
        """Return the raw gBattleTypeFlags value (for extra context)."""
        addr = self._symbols.get("gBattleTypeFlags")
        if addr is None:
            return 0
        return self._reader.u32(addr)

    def is_wild_battle(self) -> bool:
        """Return True if the active battle is a wild encounter.

        Bit 0 of gBattleTypeFlags is NOT set in wild battles.
        (BATTLE_TYPE_TRAINER = bit 0)
        """
        flags = self.battle_type_flags()
        return (flags & 0x01) == 0
