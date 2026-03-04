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

import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING

# mgba's mCoreFind is not thread-safe: concurrent calls corrupt the mCore
# struct (null function pointers).  Serialize all emulator init calls.
_init_lock = threading.Lock()

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)

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

        with _init_lock:
            log.debug("mgba: silencing log")
            # Silence mGBA's default stderr logging.
            mgba.log.silence()

            _lib = mgba.core.lib
            _ffi = mgba.core.ffi

            log.debug("mgba: calling mCoreFind()")
            native = _lib.mCoreFind(str(self._rom_path).encode("UTF-8"))
            if native == _ffi.NULL:
                raise RomLoadError(f"mGBA could not identify ROM type: {self._rom_path}")
            log.debug("mgba: mCoreFind() OK — calling core.init()")

            core = _ffi.gc(native, native.deinit)
            if not bool(core.init(core)):
                raise RomLoadError(f"mGBA core.init() failed: {self._rom_path}")
            log.debug("mgba: core.init() OK — calling mCoreInitConfig()")

            _lib.mCoreInitConfig(core, _ffi.NULL)
            log.debug("mgba: mCoreInitConfig() OK — calling load_file()")

            self._core = mgba.core.Core._detect(core)
            if not self._core.load_file(str(self._rom_path)):
                raise RomLoadError(f"mGBA could not load ROM: {self._rom_path}")
            log.debug("mgba: load_file() OK")

        # Allocate a GBA-sized framebuffer (240×160) for headless operation.
        log.debug("mgba: creating 240×160 framebuffer")
        self._screen = mgba.image.Image(240, 160)
        log.debug("mgba: setting video buffer")
        self._core.set_video_buffer(self._screen)

        log.debug("mgba: calling reset()")
        self._core.reset()
        log.debug("mgba: reset OK")

        if self._save_path and self._save_path.exists():
            log.debug("mgba: loading save %s", self._save_path)
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
        self._core.set_keys(raw=keys)

    def clear_inputs(self) -> None:
        """Release all buttons."""
        self._core.set_keys(raw=0)

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
        state = self._core.save_raw_state()
        if state is None:
            raise RuntimeError(f"mGBA failed to save state to {path}")
        path.write_bytes(bytes(state))

    def load_state(self, path: Path | str) -> None:
        """Restore emulator state from *path*."""
        path = Path(path)
        data = bytearray(path.read_bytes())
        self._core.load_raw_state(data)

    def load_save(self, path: Path | str) -> None:
        """Load a battery-backed save (.sav) file."""
        import mgba.vfs
        path = Path(path)
        vf = mgba.vfs.open_path(str(path), "r")
        if vf is None:
            raise RuntimeError(f"mGBA could not open save file: {path}")
        self._core.load_save(vf)

    # ------------------------------------------------------------------
    # ROM info
    # ------------------------------------------------------------------

    def get_screen_bytes(self) -> bytes:
        """Return the current framebuffer as raw bytes (240×160, 4 bytes/pixel, XRGB8888).

        Safe to call right after run_frame() in the same thread.
        Returns a zero-filled buffer on error.
        """
        try:
            return bytes(mgba.core.ffi.buffer(self._screen.buffer, 240 * 160 * 4))
        except Exception:
            return bytes(240 * 160 * 4)

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
        code = self._core.game_code
        # mGBA prefixes the code with the platform identifier 'AGB-'
        if code.startswith("AGB-"):
            return code[4:]
        return code
