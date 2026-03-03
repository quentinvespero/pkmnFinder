"""LibmgbaEmulator: thin wrapper around the mgba Python bindings.

The mgba module must be installed separately — see README for instructions.
Each instance of LibmgbaEmulator owns a single mGBA Core object and is
intended to be used from a single thread.

mGBA releases the GIL during run_frame(), allowing true parallelism when
multiple instances run concurrently in QThreadPool worker threads. If this
turns out not to be the case on your platform, switch to multiprocessing
(see coordinator.py).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

try:
    import mgba.core
    import mgba.image
    import mgba.log

    _MGBA_AVAILABLE = True
except ImportError:
    _MGBA_AVAILABLE = False


class MgbaNotInstalledError(RuntimeError):
    """Raised when the mgba Python bindings are not installed."""

    def __init__(self) -> None:
        super().__init__(
            "The 'mgba' Python package is not installed.\n"
            "See README.md for platform-specific installation instructions."
        )


class RomLoadError(RuntimeError):
    """Raised when a ROM cannot be loaded by mGBA."""


class LibmgbaEmulator:
    """Headless mGBA emulator instance.

    Parameters
    ----------
    rom_path:
        Absolute path to the .gba ROM file.
    save_path:
        Optional path to a .sav file to load. mGBA will create one
        alongside the ROM if not provided.
    """

    def __init__(self, rom_path: Path | str, save_path: Path | str | None = None) -> None:
        if not _MGBA_AVAILABLE:
            raise MgbaNotInstalledError()

        self._rom_path = Path(rom_path)
        self._save_path = Path(save_path) if save_path else None

        # Silence mGBA's default stderr logging.
        mgba.log.silence()

        self._core: mgba.core.Core = mgba.core.load_path(str(self._rom_path))
        if self._core is None:
            raise RomLoadError(f"mGBA could not load ROM: {self._rom_path}")

        # Allocate a minimal 1×1 framebuffer — we don't need video output.
        self._screen = mgba.image.Image(1, 1)
        self._core.set_video_buffer(self._screen)

        self._core.reset()

        if self._save_path and self._save_path.exists():
            self.load_save(self._save_path)

    # ------------------------------------------------------------------
    # Core emulation
    # ------------------------------------------------------------------

    def run_frame(self) -> None:
        """Advance emulation by exactly one video frame (~16.7 ms game time).

        mGBA releases the GIL here, so multiple threads can run in parallel.
        """
        self._core.run_frame()

    def run_frames(self, count: int) -> None:
        """Run *count* frames."""
        for _ in range(count):
            self._core.run_frame()

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def set_inputs(self, keys: int) -> None:
        """Set the GBA key state bitmask (use constants from buttons.py).

        Calling with ``keys=0`` releases all buttons.
        """
        self._core.set_keys(keys)

    def clear_inputs(self) -> None:
        """Release all buttons."""
        self._core.set_keys(0)

    # ------------------------------------------------------------------
    # Memory access
    # ------------------------------------------------------------------

    def read_bytes(self, address: int, length: int) -> bytes:
        """Read *length* raw bytes from GBA address space."""
        return bytes(self._core.memory.u8[address : address + length])

    def read_u8(self, address: int) -> int:
        return self._core.memory.u8[address]

    def read_u16(self, address: int) -> int:
        lo = self._core.memory.u8[address]
        hi = self._core.memory.u8[address + 1]
        return lo | (hi << 8)

    def read_u32(self, address: int) -> int:
        b0 = self._core.memory.u8[address]
        b1 = self._core.memory.u8[address + 1]
        b2 = self._core.memory.u8[address + 2]
        b3 = self._core.memory.u8[address + 3]
        return b0 | (b1 << 8) | (b2 << 16) | (b3 << 24)

    # ------------------------------------------------------------------
    # Save states
    # ------------------------------------------------------------------

    def save_state(self, path: Path | str) -> None:
        """Persist the current emulator state to *path* (.ss1 file)."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        state = self._core.save_state_buffer()
        path.write_bytes(state)

    def load_state(self, path: Path | str) -> None:
        """Restore emulator state from *path*."""
        path = Path(path)
        data = path.read_bytes()
        self._core.load_state_buffer(data)

    def load_save(self, path: Path | str) -> None:
        """Load a battery-backed save (.sav) file."""
        path = Path(path)
        # mGBA stores save data in the core's save buffer; load via VFile.
        # Simplest approach: pass the path and let mGBA handle it.
        self._core.load_raw_save(str(path))

    # ------------------------------------------------------------------
    # ROM info
    # ------------------------------------------------------------------

    @property
    def rom_title(self) -> str:
        """12-char ASCII game title embedded in the ROM header."""
        return self._core.game_title

    @property
    def rom_code(self) -> str:
        """4-char game code (e.g. 'BPEE' for Emerald)."""
        return self._core.game_code
