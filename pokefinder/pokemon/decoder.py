"""Gen 3 Pokemon struct decoder: XOR decryption + 24-permutation substructures.

Gen 3 party Pokemon occupy 100 bytes in RAM:
    Offset 0x00–0x1F  : Unencrypted header (PID, OT ID, nickname, …)
    Offset 0x20–0x4F  : Encrypted substructure data (48 bytes / 4 substructs)
    Offset 0x50–0x63  : Unencrypted battle stats (party only, ignored here)

The 4 substructures (G, A, E, M) are arranged in one of 24 orderings
determined by (PID % 24). Each substructure is 12 bytes.

Substructure identifiers:
    G = Growth  (species, item, exp, pp_bonuses, friendship)
    A = Attacks (moves + pp)
    E = EVs & Condition
    M = Misc    (IVs, ribbons, obedience)

XOR key = PID XOR OT_ID  (repeated as a 4-byte little-endian pattern)

References:
    - Bulbapedia: Pokémon data structure (Generation III)
    - pret/pokeemerald source: include/pokemon.h
"""

from __future__ import annotations

import struct

from pokefinder.pokemon.shiny import is_shiny
from pokefinder.pokemon.species import species_name
from pokefinder.pokemon.structs import Pokemon

# 24 orderings of the 4 substructures (GAEM indexed 0–3)
# Index = PID % 24 → tuple of (G_pos, A_pos, E_pos, M_pos)
# Each value is the position (0–3) of that substructure.
# Equivalently: order[i] names which substructure is at slot i.
_SUBSTRUCTURE_ORDER: list[tuple[int, int, int, int]] = [
    (0, 1, 2, 3),  #  0: GAEM
    (0, 1, 3, 2),  #  1: GAME
    (0, 2, 1, 3),  #  2: GEAM
    (0, 3, 1, 2),  #  3: GEMA
    (0, 2, 3, 1),  #  4: GMAE  — wait, let's use the standard table below
    (0, 3, 2, 1),  #  5: GMEA
    (1, 0, 2, 3),  #  6: AGEM  — actually indices describe slot contents
    (1, 0, 3, 2),  #  7: AGME
    (2, 0, 1, 3),  #  8: EAGM
    (3, 0, 1, 2),  #  9: MAEG  — using the correct Bulbapedia table:
    (2, 0, 3, 1),  # 10: EGAM
    (3, 0, 2, 1),  # 11: MGAE
    (1, 2, 0, 3),  # 12: AEGM  — slot→substructure mapping
    (1, 3, 0, 2),  # 13: AMGE
    (2, 1, 0, 3),  # 14: EAGM
    (3, 1, 0, 2),  # 15: MAEG
    (2, 3, 0, 1),  # 16: EMGA
    (3, 2, 0, 1),  # 17: MEAG (corrected below with standard table)
    (1, 2, 3, 0),  # 18: AEGM
    (1, 3, 2, 0),  # 19: AMEG
    (2, 1, 3, 0),  # 20: EAMG
    (3, 1, 2, 0),  # 21: MAEG
    (2, 3, 1, 0),  # 22: EMAG
    (3, 2, 1, 0),  # 23: MEAG
]

# Standard Bulbapedia table (slot 0..3 → substructure name G/A/E/M = 0/1/2/3)
# This is the authoritative lookup used in pret source and all reference impls.
_ORDER_TABLE: list[tuple[int, int, int, int]] = [
    (0, 1, 2, 3),  #  0
    (0, 1, 3, 2),  #  1
    (0, 2, 1, 3),  #  2
    (0, 2, 3, 1),  #  3
    (0, 3, 1, 2),  #  4
    (0, 3, 2, 1),  #  5
    (1, 0, 2, 3),  #  6
    (1, 0, 3, 2),  #  7
    (1, 2, 0, 3),  #  8
    (1, 2, 3, 0),  #  9
    (1, 3, 0, 2),  # 10
    (1, 3, 2, 0),  # 11
    (2, 0, 1, 3),  # 12
    (2, 0, 3, 1),  # 13
    (2, 1, 0, 3),  # 14
    (2, 1, 3, 0),  # 15
    (2, 3, 0, 1),  # 16
    (2, 3, 1, 0),  # 17
    (3, 0, 1, 2),  # 18
    (3, 0, 2, 1),  # 19
    (3, 1, 0, 2),  # 20
    (3, 1, 2, 0),  # 21
    (3, 2, 0, 1),  # 22
    (3, 2, 1, 0),  # 23
]

# Substructure size in bytes
_SUBSTRUCT_SIZE = 12
# Start of encrypted data within the 100-byte party struct
_ENCRYPT_START = 32
_ENCRYPT_END = 80  # exclusive (48 bytes = 4 × 12)


def _xor_key_stream(pid: int, otid: int, length: int) -> bytes:
    """Generate the XOR keystream for Gen 3 Pokemon decryption.

    Key = (pid XOR otid), repeated as a 4-byte little-endian pattern.
    """
    key32 = (pid ^ otid) & 0xFFFFFFFF
    key_bytes = struct.pack("<I", key32)
    # Repeat to cover 'length' bytes
    reps = (length + 3) // 4
    stream = (key_bytes * reps)[:length]
    return stream


def _decrypt_substructs(data: bytes, pid: int, otid: int) -> bytes:
    """XOR-decrypt the 48-byte encrypted substructure block."""
    encrypted = data[_ENCRYPT_START:_ENCRYPT_END]
    key = _xor_key_stream(pid, otid, len(encrypted))
    decrypted = bytes(a ^ b for a, b in zip(encrypted, key))
    return decrypted


def _get_substruct(decrypted_48: bytes, slot: int) -> bytes:
    """Return the 12-byte substructure at *slot* (0–3) from the decrypted block."""
    start = slot * _SUBSTRUCT_SIZE
    return decrypted_48[start : start + _SUBSTRUCT_SIZE]


def _find_substruct(decrypted_48: bytes, pid: int, substruct_id: int) -> bytes:
    """Find the 12-byte substructure by its logical ID (0=G, 1=A, 2=E, 3=M).

    Uses the 24-permutation table to locate the physical slot.
    """
    order = _ORDER_TABLE[pid % 24]
    # order[slot] = substruct_id at that slot
    # We need: which slot contains substruct_id?
    slot = order.index(substruct_id)
    return _get_substruct(decrypted_48, slot)


# Substructure IDs
_G = 0  # Growth
_A = 1  # Attacks
_E = 2  # EVs / Condition
_M = 3  # Misc (IVs, ribbons)


def decode_pokemon(raw: bytes) -> Pokemon:
    """Decode a raw 100-byte (party) or 80-byte (box) Gen 3 Pokemon slot.

    Returns a populated Pokemon dataclass. For box Pokemon (80 bytes),
    battle stats are unavailable and level will be 0.

    Parameters
    ----------
    raw:
        Raw bytes read from gPlayerParty[n] or gEnemyParty[n].
    """
    if len(raw) < 80:
        raise ValueError(f"Pokemon data too short: {len(raw)} bytes (need ≥ 80)")

    # --- Unencrypted header (offsets from Bulbapedia / pokemon.h) ---
    pid = struct.unpack_from("<I", raw, 0x00)[0]
    otid_word = struct.unpack_from("<I", raw, 0x04)[0]
    tid = otid_word & 0xFFFF
    sid = (otid_word >> 16) & 0xFFFF

    # --- Decrypt substructures ---
    decrypted = _decrypt_substructs(raw, pid, otid_word)

    # --- Growth substructure (G) ---
    g = _find_substruct(decrypted, pid, _G)
    sp_id = struct.unpack_from("<H", g, 0x00)[0]   # species
    exp = struct.unpack_from("<I", g, 0x04)[0]

    # --- Misc substructure (M) ---
    m = _find_substruct(decrypted, pid, _M)
    # Offset 0x04 in M = packed IVs (32-bit word)
    iv_word = struct.unpack_from("<I", m, 0x04)[0]
    iv_hp  = (iv_word >> 0)  & 0x1F
    iv_atk = (iv_word >> 5)  & 0x1F
    iv_def = (iv_word >> 10) & 0x1F
    iv_spd = (iv_word >> 15) & 0x1F
    iv_spa = (iv_word >> 20) & 0x1F
    iv_spd_special = (iv_word >> 25) & 0x1F

    # --- Shiny ---
    shiny = is_shiny(pid, tid, sid)

    # --- Species name ---
    name = species_name(sp_id)

    return Pokemon(
        pid=pid,
        tid=tid,
        sid=sid,
        species_id=sp_id,
        species_name=name,
        exp=exp,
        level=0,  # compute from exp table if needed
        iv_hp=iv_hp,
        iv_atk=iv_atk,
        iv_def=iv_def,
        iv_spd=iv_spd,
        iv_spa=iv_spa,
        iv_spd_special=iv_spd_special,
        is_shiny=shiny,
        raw=bytes(raw[:80]),
    )
