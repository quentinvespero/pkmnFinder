"""Species ID ↔ name lookup for Gen 3 (National Dex #1–386).

Data is loaded lazily from data/species_names.json on first access.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_DATA_FILE = Path(__file__).parent.parent.parent / "data" / "species_names.json"


@lru_cache(maxsize=1)
def _load_table() -> dict[int, str]:
    """Load and cache the species ID → name mapping."""
    with _DATA_FILE.open("r", encoding="utf-8") as f:
        raw: dict[str, str] = json.load(f)
    return {int(k): v for k, v in raw.items()}


def species_name(dex_id: int) -> str:
    """Return the species name for *dex_id*, or '???' if unknown."""
    return _load_table().get(dex_id, f"???({dex_id})")


def species_id(name: str) -> int | None:
    """Return the National Dex ID for a given name (case-insensitive), or None."""
    name_lower = name.lower()
    for dex_id, sp_name in _load_table().items():
        if sp_name.lower() == name_lower:
            return dex_id
    return None


def all_species() -> list[tuple[int, str]]:
    """Return all (dex_id, name) pairs sorted by dex ID."""
    return sorted(_load_table().items())
