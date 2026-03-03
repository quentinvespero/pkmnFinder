"""GBA button bitmask constants for mGBA key input."""

# mGBA uses the same bitmask layout as the GBA hardware register REG_KEYINPUT.
# Bits are active-HIGH in the mGBA Python API (unlike hardware which is active-LOW).

A = 0x0001
B = 0x0002
SELECT = 0x0004
START = 0x0008
RIGHT = 0x0010
LEFT = 0x0020
UP = 0x0040
DOWN = 0x0080
R = 0x0100
L = 0x0200

NONE = 0x0000

# Convenience combos
A_B = A | B
START_SELECT_A_B = START | SELECT | A | B  # Soft-reset combination
