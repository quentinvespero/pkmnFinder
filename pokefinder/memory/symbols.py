"""SymbolTable: parse .sym files from pret decompilation projects.

.sym file format (one symbol per line):
    <hex_address> <type_char> <symbol_name>

Example:
    0200c5e8 D gPlayerParty
    02024284 D gEnemyParty

Only 'D' (data) and 'T' (text/code) symbols are relevant. Lines that do not
match this pattern are silently ignored.
"""

from __future__ import annotations

import re
from pathlib import Path

# Matches 3-column "08000000 T _start" and 4-column "0200c5e8 g 00000001 gPlayerParty"
# The optional middle hex field is the symbol size (present in nm --print-size output).
_SYM_PATTERN = re.compile(r"^([0-9a-fA-F]+)\s+([A-Za-z])\s+(?:[0-9a-fA-F]+\s+)?(\S+)$")


class SymbolTable:
    """Parsed symbol table loaded from a .sym file."""

    def __init__(self) -> None:
        self._symbols: dict[str, int] = {}

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def from_file(cls, path: Path | str) -> "SymbolTable":
        """Parse a .sym file and return a populated SymbolTable."""
        table = cls()
        path = Path(path)
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                m = _SYM_PATTERN.match(line.strip())
                if m:
                    addr_str, _type_char, name = m.groups()
                    table._symbols[name] = int(addr_str, 16)
        return table

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def address(self, name: str) -> int:
        """Return the address for *name*, raising KeyError if not found."""
        return self._symbols[name]

    def get(self, name: str, default: int | None = None) -> int | None:
        """Return the address for *name*, or *default* if not found."""
        return self._symbols.get(name, default)

    def __contains__(self, name: str) -> bool:
        return name in self._symbols

    def __len__(self) -> int:
        return len(self._symbols)
