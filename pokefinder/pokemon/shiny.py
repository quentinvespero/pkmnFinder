"""Gen 3 shiny detection formula.

A Pokemon is shiny if:
    (TID XOR SID XOR (PID >> 16) XOR (PID & 0xFFFF)) < 8

Reference: Bulbapedia — Personality value#Shininess
"""

from __future__ import annotations


def is_shiny(pid: int, tid: int, sid: int) -> bool:
    """Return True if the given PID / TID / SID combination is shiny.

    Parameters
    ----------
    pid:
        32-bit personality ID.
    tid:
        16-bit public trainer ID (lower 16 bits of the OT ID word).
    sid:
        16-bit secret ID (upper 16 bits of the OT ID word).
    """
    xor = tid ^ sid ^ (pid >> 16) ^ (pid & 0xFFFF)
    return xor < 8
