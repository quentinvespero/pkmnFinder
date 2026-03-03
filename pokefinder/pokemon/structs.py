"""Pokemon dataclass representing a fully-decoded Gen 3 party/box slot."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Pokemon:
    """A Gen 3 Pokemon decoded from RAM.

    All multi-byte integers are stored in their natural Python representation
    (i.e., already little-endian decoded from GBA memory).
    """

    # Identity
    pid: int = 0          # Personality ID (32-bit)
    tid: int = 0          # Trainer ID — lower 16 bits (public TID)
    sid: int = 0          # Secret ID — upper 16 bits of OT ID word

    # Species
    species_id: int = 0   # National Dex number (1-386 for Gen 3)
    species_name: str = ""

    # Stats summary (from Growth substructure)
    exp: int = 0
    level: int = 0

    # IVs (5 bits each, packed in Misc substructure)
    iv_hp: int = 0
    iv_atk: int = 0
    iv_def: int = 0
    iv_spd: int = 0
    iv_spa: int = 0
    iv_spd_special: int = 0  # SpDef

    # Shiny
    is_shiny: bool = False

    # Raw bytes (100 bytes for a party slot, 80 for box slot)
    raw: bytes = field(default_factory=bytes, repr=False)

    # ------------------------------------------------------------------
    # Derived helpers
    # ------------------------------------------------------------------

    @property
    def otid_word(self) -> int:
        """Combined TID/SID as a single 32-bit word (TID in low 16 bits)."""
        return self.tid | (self.sid << 16)

    def __str__(self) -> str:
        shiny_tag = " ✨SHINY✨" if self.is_shiny else ""
        return (
            f"#{self.species_id:03d} {self.species_name}{shiny_tag} "
            f"(PID={self.pid:#010x}, TID={self.tid}, SID={self.sid})"
        )
