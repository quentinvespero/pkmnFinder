"""HuntInstance: a single emulator hunt loop running as a QRunnable.

Each instance:
  1. Creates and owns a LibmgbaEmulator
  2. Loads the ROM + symbol table
  3. Runs the appropriate automation (wild or soft-reset)
  4. Emits Qt signals for stats updates and found events
  5. Respects the shared stop_event for clean shutdown

Threading model:
  - Runs in a QThreadPool worker thread
  - Emits signals (thread-safe via Qt's queued connection mechanism)
  - NEVER touches Qt widgets directly
"""

from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING

log = logging.getLogger(__name__)

from PyQt6.QtCore import QObject, QRunnable, pyqtSignal

from pokefinder.automation.actions import StopRequested
from pokefinder.automation.soft_reset import SoftResetAutomation, SoftResetStats
from pokefinder.automation.wild_hunt import WildHuntAutomation, WildHuntStats
from pokefinder.emulator.core import LibmgbaEmulator, MgbaNotInstalledError
from pokefinder.emulator.state import save_snapshot
from pokefinder.game_state.battle import BattleStateReader
from pokefinder.game_state.encounter import EncounterReader
from pokefinder.game_state.player import PlayerStateReader
from pokefinder.games.base import GameProfile
from pokefinder.hunt.config import HuntConfig, HuntMethod
from pokefinder.memory.reader import MemoryReader
from pokefinder.memory.symbols import SymbolTable
from pokefinder.pokemon.structs import Pokemon

if TYPE_CHECKING:
    pass


class InstanceSignals(QObject):
    """Qt signals emitted by HuntInstance worker threads.

    Must live in a QObject so the signal machinery works.
    """

    # (instance_id, encounter_count, rate_per_hour, state_label)
    stats_updated = pyqtSignal(int, int, float, str)

    # (instance_id, Pokemon) — emitted when a matching Pokemon is found
    found = pyqtSignal(int, object)

    # (instance_id, error_message)
    error = pyqtSignal(int, str)

    # (instance_id, raw_bytes) — periodic screen snapshot (240×160 XRGB8888, ~1fps)
    frame_updated = pyqtSignal(int, bytes)


class HuntInstance(QRunnable):
    """A single parallel hunt instance running in a QThreadPool worker thread.

    Parameters
    ----------
    instance_id:
        Zero-based index identifying this instance (used for display + filenames).
    config:
        Shared HuntConfig (read-only).
    stop_event:
        Shared threading.Event — set by the coordinator when any instance finds a match.
    emulator:
        Pre-created LibmgbaEmulator (created on the main thread to avoid macOS
        thread-safety issues with mGBA initialization). If None, a new one is
        created in the worker thread as a fallback.
    """

    def __init__(
        self,
        instance_id: int,
        config: HuntConfig,
        stop_event: threading.Event,
        emulator: LibmgbaEmulator | None = None,
    ) -> None:
        super().__init__()
        self.instance_id = instance_id
        self._config = config
        self._stop = stop_event
        self._emulator = emulator
        self.signals = InstanceSignals()
        self.setAutoDelete(True)

    # ------------------------------------------------------------------
    # QRunnable.run() — called by QThreadPool in a worker thread
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Main hunt loop. Runs until a match is found or stop_event is set."""
        log.info("Instance #%d started in thread %s", self.instance_id, threading.current_thread().name)
        try:
            self._run_hunt()
        except MgbaNotInstalledError as e:
            log.error("Instance #%d: mgba not installed: %s", self.instance_id, e)
            self.signals.error.emit(self.instance_id, str(e))
        except StopRequested:
            log.info("Instance #%d: stopped by stop_event", self.instance_id)
        except Exception as e:
            log.exception("Instance #%d: unexpected error", self.instance_id)
            self.signals.error.emit(self.instance_id, f"Unexpected error: {e}")
        finally:
            log.info("Instance #%d exiting", self.instance_id)

    def _run_hunt(self) -> None:
        cfg = self._config

        # Signal the GUI immediately so the card doesn't sit on "idle"
        self.signals.stats_updated.emit(self.instance_id, 0, 0.0, "loading")

        # --- Use pre-created emulator (created on main thread) or create one ---
        if self._emulator is not None:
            emulator = self._emulator
            rom_code = emulator.rom_code
            log.info("Instance #%d: using pre-created emulator, rom_code=%r", self.instance_id, rom_code)
        else:
            log.debug("Instance #%d: creating emulator in worker thread (fallback)", self.instance_id)
            emulator = LibmgbaEmulator(cfg.rom_path)
            rom_code = emulator.rom_code
            log.info("Instance #%d: ROM loaded — code=%r", self.instance_id, rom_code)

        # --- Load symbol table ---
        log.debug("Instance #%d: loading game profile for %r", self.instance_id, rom_code)
        profile = GameProfile.for_rom_code(rom_code)
        log.debug("Instance #%d: loading symbols from %s", self.instance_id, profile.sym_path)
        symbols = SymbolTable.from_file(profile.sym_path)
        log.debug("Instance #%d: %d symbols loaded", self.instance_id, len(symbols))
        reader = MemoryReader(emulator, symbols)

        # --- Build state readers ---
        log.debug("Instance #%d: building state readers", self.instance_id)
        battle_reader = BattleStateReader(reader, symbols)
        encounter_reader = EncounterReader(reader, symbols)
        player_reader = PlayerStateReader(reader, symbols)
        log.info("Instance #%d: state readers ready — starting automation", self.instance_id)

        # --- Intercept run_frame to capture the screen ~1/sec for the GUI ---
        _frame_count = [0]
        _orig_run_frame = emulator.run_frame

        def _capturing_run_frame() -> None:
            _orig_run_frame()
            _frame_count[0] += 1
            if _frame_count[0] % 60 == 0:
                self.signals.frame_updated.emit(self.instance_id, emulator.get_screen_bytes())

        emulator.run_frame = _capturing_run_frame

        # --- Track timing for rate calculation ---
        start_time = time.monotonic()

        def on_stats(stats) -> None:
            elapsed = time.monotonic() - start_time
            count = getattr(stats, "encounter_count", None) or getattr(stats, "reset_count", 0)
            rate = (count / elapsed * 3600) if elapsed > 0 else 0.0
            state_label = stats.state.value
            self.signals.stats_updated.emit(self.instance_id, count, rate, state_label)

        # --- Run automation ---
        if cfg.method == HuntMethod.WILD:
            automation = WildHuntAutomation(
                emulator=emulator,
                battle_reader=battle_reader,
                encounter_reader=encounter_reader,
                player_reader=player_reader,
                target_species_id=cfg.target_species_id,
                shiny_only=cfg.shiny_only,
                stop_event=self._stop,
                on_stats_update=on_stats,
            )
            final_stats = automation.run()
            found_pokemon = final_stats.found_pokemon

        else:  # SOFT_RESET
            if cfg.state_path is None:
                raise ValueError("state_path is required for soft reset hunt")
            automation = SoftResetAutomation(
                emulator=emulator,
                battle_reader=battle_reader,
                encounter_reader=encounter_reader,
                state_path=cfg.state_path,
                target_species_id=cfg.target_species_id,
                shiny_only=cfg.shiny_only,
                stop_event=self._stop,
                on_stats_update=on_stats,
            )
            final_stats = automation.run()
            found_pokemon = final_stats.found_pokemon

        # --- Emit found signal if we found the target ---
        if found_pokemon is not None:
            # Save the winning state
            try:
                cfg.save_dir.mkdir(parents=True, exist_ok=True)
                save_snapshot(emulator, found_pokemon.species_name, self.instance_id)
            except Exception:
                pass  # Non-fatal — don't block the found signal

            self.signals.found.emit(self.instance_id, found_pokemon)
