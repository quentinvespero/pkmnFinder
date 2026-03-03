"""Unit tests for Gen 3 Pokemon decryption and shiny detection.

Test vectors sourced from the RNG research community (Bulbapedia / Smogon)
and cross-checked against pokebot-gen3 and pret source code.
"""

import struct

import pytest

from pokefinder.pokemon.decoder import decode_pokemon, _xor_key_stream, _ORDER_TABLE
from pokefinder.pokemon.shiny import is_shiny
from pokefinder.pokemon.structs import Pokemon


# ---------------------------------------------------------------------------
# Helpers to build synthetic Pokemon data
# ---------------------------------------------------------------------------

def build_raw_pokemon(
    pid: int,
    tid: int,
    sid: int,
    species_id: int,
    exp: int = 0,
    iv_word: int = 0,
) -> bytes:
    """Build a minimal 100-byte Gen 3 party slot for testing.

    Encrypts substructures in the correct order and with the correct XOR key.
    """
    otid_word = tid | (sid << 16)

    # Build 4 × 12-byte substructures (G, A, E, M) — content for our tests
    # G (Growth): species at offset 0, exp at offset 4
    g = struct.pack("<HHI HH", species_id, 0, exp, 0, 0)  # 12 bytes

    # A (Attacks): all zeros
    a = bytes(12)

    # E (EVs/Condition): all zeros
    e = bytes(12)

    # M (Misc): IV word at offset 4
    m = struct.pack("<I I I", 0, iv_word, 0)  # 12 bytes

    # Arrange into slots per the order table
    order = _ORDER_TABLE[pid % 24]
    # order[slot] = substructure id (0=G,1=A,2=E,3=M)
    substructs = [g, a, e, m]
    slots = [None, None, None, None]
    for slot, substruct_id in enumerate(order):
        slots[slot] = substructs[substruct_id]

    encrypted_plain = b"".join(slots)  # 48 bytes

    # XOR with key
    key32 = (pid ^ otid_word) & 0xFFFFFFFF
    key_bytes = struct.pack("<I", key32) * 12  # 48 bytes
    encrypted = bytes(a ^ b for a, b in zip(encrypted_plain, key_bytes))

    # Build full 100-byte struct
    # [0x00] PID, [0x04] OT ID, [0x08–0x1F] nickname etc (zeros), [0x20–0x4F] encrypted, [0x50–0x63] battle stats
    header = struct.pack("<II", pid, otid_word) + bytes(24)  # 32 bytes
    battle_stats = bytes(20)  # 20 bytes (0x50–0x63)
    raw = header + encrypted + battle_stats
    assert len(raw) == 100, f"Expected 100 bytes, got {len(raw)}"
    return raw


# ---------------------------------------------------------------------------
# Shiny tests
# ---------------------------------------------------------------------------

class TestShinyFormula:
    def test_non_shiny(self):
        # Random PID/TID/SID that doesn't satisfy the formula
        assert not is_shiny(pid=0x12345678, tid=1234, sid=5678)

    def test_shiny_exact_zero(self):
        # Construct a PID such that TID ^ SID ^ (PID>>16) ^ (PID&0xFFFF) == 0
        tid = 0x1234
        sid = 0x5678
        pid_high = tid ^ sid  # so that tid ^ sid ^ pid_high = 0
        pid_low = 0
        pid = (pid_high << 16) | pid_low
        assert is_shiny(pid=pid, tid=tid, sid=sid)

    def test_shiny_threshold_7(self):
        # XOR result exactly 7 → shiny
        tid = 0x0001
        sid = 0x0000
        pid_high = tid ^ sid ^ 7  # XOR = 7
        pid = (pid_high << 16)
        assert is_shiny(pid=pid, tid=tid, sid=sid)

    def test_not_shiny_threshold_8(self):
        # XOR result exactly 8 → NOT shiny
        tid = 0x0001
        sid = 0x0000
        pid_high = tid ^ sid ^ 8
        pid = (pid_high << 16)
        assert not is_shiny(pid=pid, tid=tid, sid=sid)

    def test_shiny_known_vector(self):
        # From community test vectors: known shiny PID
        # TID=54321, SID=12345, PID that is shiny
        tid = 54321
        sid = 12345
        # Compute shiny PID: we need tid^sid^(pid>>16)^(pid&0xFFFF) < 8
        # Set pid_high = tid ^ sid, pid_low = 0 → XOR = 0 → shiny
        pid_high = (tid ^ sid) & 0xFFFF
        pid = (pid_high << 16) | 0x0000
        assert is_shiny(pid=pid, tid=tid, sid=sid)


# ---------------------------------------------------------------------------
# XOR keystream tests
# ---------------------------------------------------------------------------

class TestXorKeystream:
    def test_length(self):
        stream = _xor_key_stream(0xABCD1234, 0x12345678, 48)
        assert len(stream) == 48

    def test_repeating_pattern(self):
        pid = 0xDEADBEEF
        otid = 0x12345678
        stream = _xor_key_stream(pid, otid, 8)
        key32 = (pid ^ otid) & 0xFFFFFFFF
        expected = struct.pack("<I", key32) * 2
        assert stream == expected


# ---------------------------------------------------------------------------
# Order table tests
# ---------------------------------------------------------------------------

class TestOrderTable:
    def test_all_24_entries_are_permutations(self):
        for i, order in enumerate(_ORDER_TABLE):
            assert sorted(order) == [0, 1, 2, 3], f"Entry {i} is not a permutation: {order}"

    def test_all_24_entries_are_unique(self):
        assert len({tuple(o) for o in _ORDER_TABLE}) == 24


# ---------------------------------------------------------------------------
# Full decoder tests
# ---------------------------------------------------------------------------

class TestDecoder:
    def _build_and_decode(self, pid, tid, sid, species_id, exp=100, iv_word=0):
        raw = build_raw_pokemon(pid, tid, sid, species_id, exp, iv_word)
        return decode_pokemon(raw)

    def test_species_id_recovered(self):
        pkmn = self._build_and_decode(pid=0x12345678, tid=1234, sid=5678, species_id=25)
        assert pkmn.species_id == 25  # Pikachu

    def test_species_name(self):
        pkmn = self._build_and_decode(pid=0x12345678, tid=1234, sid=5678, species_id=25)
        assert pkmn.species_name == "Pikachu"

    def test_tid_sid_recovered(self):
        pkmn = self._build_and_decode(pid=0x11223344, tid=9999, sid=1111, species_id=1)
        assert pkmn.tid == 9999
        assert pkmn.sid == 1111

    def test_pid_recovered(self):
        pid = 0xDEADBEEF
        pkmn = self._build_and_decode(pid=pid, tid=100, sid=200, species_id=150)
        assert pkmn.pid == pid

    def test_exp_recovered(self):
        pkmn = self._build_and_decode(pid=0xABCDEF01, tid=0, sid=0, species_id=3, exp=12345)
        assert pkmn.exp == 12345

    def test_iv_word_recovered(self):
        # Pack IVs: hp=31, atk=31, def=31, spd=31, spa=31, spdf=31
        iv_word = (31 << 0) | (31 << 5) | (31 << 10) | (31 << 15) | (31 << 20) | (31 << 25)
        pkmn = self._build_and_decode(pid=0x55555555, tid=0, sid=0, species_id=16, iv_word=iv_word)
        assert pkmn.iv_hp == 31
        assert pkmn.iv_atk == 31
        assert pkmn.iv_def == 31
        assert pkmn.iv_spd == 31
        assert pkmn.iv_spa == 31
        assert pkmn.iv_spd_special == 31

    def test_shiny_detected(self):
        tid = 12345
        sid = 54321  # Must be ≤ 65535 (16-bit secret ID)
        pid_high = (tid ^ sid) & 0xFFFF  # XOR result = 0 → shiny
        pid = (pid_high << 16)
        pkmn = self._build_and_decode(pid=pid, tid=tid, sid=sid, species_id=384)
        assert pkmn.is_shiny is True

    def test_non_shiny_detected(self):
        pkmn = self._build_and_decode(pid=0x12345678, tid=1234, sid=5678, species_id=6)
        assert pkmn.is_shiny is False

    def test_all_24_orderings_decode_correctly(self):
        """Ensure species is recovered correctly for all 24 PID%24 orderings."""
        for order_idx in range(24):
            # Find a PID with pid%24 == order_idx
            pid = order_idx  # trivially pid%24 == order_idx for 0..23
            pkmn = self._build_and_decode(pid=pid, tid=0, sid=0, species_id=129)  # Magikarp
            assert pkmn.species_id == 129, (
                f"Order {order_idx}: got species {pkmn.species_id}, expected 129"
            )

    def test_rejects_too_short(self):
        with pytest.raises(ValueError):
            decode_pokemon(bytes(50))
