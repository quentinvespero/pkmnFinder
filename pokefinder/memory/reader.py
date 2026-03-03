"""MemoryReader: typed memory access helpers backed by a LibmgbaEmulator.

Provides u8/u16/u32/bytes/pointer reads and symbol-addressed reads.
Pointer reads handle Gen 3's pointer encoding: GBA pointers are stored
as 32-bit little-endian values; addresses in ROM/EWRAM need masking.
"""

from __future__ import annotations

import struct
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pokefinder.emulator.core import LibmgbaEmulator
    from pokefinder.memory.symbols import SymbolTable

# GBA memory map masks
_EWRAM_BASE = 0x02000000
_IWRAM_BASE = 0x03000000
_ROM_BASE = 0x08000000

# The GBA pointer bus address mask — strip the upper byte used by mGBA for
# memory region routing, keeping the raw 24-bit offset within the region.
_ADDR_MASK = 0x0FFFFFFF


def _mask(addr: int) -> int:
    """Strip mGBA's upper routing byte, return the canonical bus address."""
    return addr & 0x0FFFFFFF | (addr & 0xF0000000)


class MemoryReader:
    """Read typed values from GBA address space via a LibmgbaEmulator.

    Parameters
    ----------
    emulator:
        Active LibmgbaEmulator instance.
    symbols:
        Optional SymbolTable for symbol-addressed reads.
    """

    def __init__(
        self,
        emulator: "LibmgbaEmulator",
        symbols: "SymbolTable | None" = None,
    ) -> None:
        self._emu = emulator
        self._symbols = symbols

    # ------------------------------------------------------------------
    # Raw reads
    # ------------------------------------------------------------------

    def u8(self, address: int) -> int:
        return self._emu.read_u8(address)

    def u16(self, address: int) -> int:
        return self._emu.read_u16(address)

    def u32(self, address: int) -> int:
        return self._emu.read_u32(address)

    def read_bytes(self, address: int, length: int) -> bytes:
        return self._emu.read_bytes(address, length)

    # ------------------------------------------------------------------
    # Struct reads
    # ------------------------------------------------------------------

    def s8(self, address: int) -> int:
        v = self.u8(address)
        return v if v < 0x80 else v - 0x100

    def s16(self, address: int) -> int:
        v = self.u16(address)
        return v if v < 0x8000 else v - 0x10000

    # ------------------------------------------------------------------
    # Pointer reads
    # ------------------------------------------------------------------

    def ptr(self, address: int) -> int:
        """Read a 32-bit GBA pointer and return the address it points to.

        Returns 0 for null pointers.
        """
        value = self.u32(address)
        if value == 0:
            return 0
        # GBA pointers encode the memory region in the upper byte.
        # Keep it as-is — mGBA uses the full 32-bit address.
        return value

    def deref_ptr(self, address: int, offset: int = 0) -> int:
        """Read pointer at *address*, then read u32 from (ptr + offset)."""
        p = self.ptr(address)
        if p == 0:
            return 0
        return self.u32(p + offset)

    # ------------------------------------------------------------------
    # Symbol-addressed reads
    # ------------------------------------------------------------------

    def _sym_addr(self, name: str) -> int:
        if self._symbols is None:
            raise RuntimeError("MemoryReader has no SymbolTable attached.")
        return self._symbols.address(name)

    def sym_u8(self, name: str, offset: int = 0) -> int:
        return self.u8(self._sym_addr(name) + offset)

    def sym_u16(self, name: str, offset: int = 0) -> int:
        return self.u16(self._sym_addr(name) + offset)

    def sym_u32(self, name: str, offset: int = 0) -> int:
        return self.u32(self._sym_addr(name) + offset)

    def sym_bytes(self, name: str, length: int, offset: int = 0) -> bytes:
        return self.read_bytes(self._sym_addr(name) + offset, length)

    def sym_ptr(self, name: str) -> int:
        """Read the pointer stored at symbol *name*."""
        return self.ptr(self._sym_addr(name))
