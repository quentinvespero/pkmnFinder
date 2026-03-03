"""SoftResetAutomation: state machine for soft-reset hunting (starters/legendaries).

Strategy:
  1. Load from a pre-positioned save state (player standing in front of
     the starter or legendary, save state taken just before the encounter)
  2. Wait for the encounter to be generated (poll for battle state)
  3. Read gEnemyParty[0] / gPlayerParty[0] depending on game phase
  4. If match: signal found; otherwise: reload state and repeat

The user must provide a save state (.ss1) positioned at the last moment
before the encounter is generated. For:
  - Starters: stand in front of the bag/briefcase, state saved before
    pressing A on the Pokemon
  - Legendaries: save state in front of the legendary Pokemon, before
    pressing A to interact

State machine states:
    LOADING       — loading save state
    WAITING       — waiting for the encounter (poll for battle flag)
    IN_ENCOUNTER  — encounter is active, reading Pokemon
    FOUND         — target Pokemon detected (terminal state)
    STOPPED       — stop_event was set (terminal state)
"""

from __future__ import annotations

import enum
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from pokefinder.automation.actions import (
    StopRequested,
    load_state_reset,
    press_a,
    wait_frames,
    wait_until,
)
from pokefinder.pokemon.structs import Pokemon

if TYPE_CHECKING:
    from pokefinder.emulator.core import LibmgbaEmulator
    from pokefinder.game_state.battle import BattleStateReader
    from pokefinder.game_state.encounter import EncounterReader
    from pokefinder.game_state.player import PlayerStateReader


class SoftResetState(enum.Enum):
    LOADING = "loading"
    WAITING = "waiting"
    IN_ENCOUNTER = "in_encounter"
    FOUND = "found"
    STOPPED = "stopped"


class SoftResetStats:
    def __init__(self) -> None:
        self.reset_count: int = 0
        self.state: SoftResetState = SoftResetState.LOADING
        self.last_pokemon: Pokemon | None = None
        self.found_pokemon: Pokemon | None = None


class SoftResetAutomation:
    """Drives a single emulator instance to soft-reset hunt a starter or legendary.

    Parameters
    ----------
    emulator:
        LibmgbaEmulator instance.
    battle_reader:
        BattleStateReader for the loaded ROM.
    encounter_reader:
        EncounterReader for the loaded ROM.
    state_path:
        Path to a pre-positioned .ss1 save state file.
    target_species_id:
        National Dex ID to hunt for.
    shiny_only:
        If True, only stop on a shiny specimen.
    stop_event:
        threading.Event set by the coordinator when any instance finds a match.
    on_stats_update:
        Optional callback called after each reset with the current stats.
    use_player_party:
        If True, read from gPlayerParty[0] instead of gEnemyParty[0].
        Use this for starter selection (the Pokemon appears in your party).
    """

    # Max frames to wait for battle to start after loading state
    BATTLE_WAIT_FRAMES = 1200  # ~20 seconds at 60fps

    def __init__(
        self,
        emulator: "LibmgbaEmulator",
        battle_reader: "BattleStateReader",
        encounter_reader: "EncounterReader",
        state_path: Path | str,
        target_species_id: int,
        shiny_only: bool,
        stop_event: threading.Event,
        on_stats_update: Callable[[SoftResetStats], None] | None = None,
        use_player_party: bool = False,
    ) -> None:
        self._emu = emulator
        self._battle = battle_reader
        self._encounter = encounter_reader
        self._state_path = Path(state_path)
        self._target_id = target_species_id
        self._shiny_only = shiny_only
        self._stop = stop_event
        self._on_stats = on_stats_update
        self._use_player_party = use_player_party
        self.stats = SoftResetStats()

    def run(self) -> SoftResetStats:
        """Run the soft-reset loop until a match is found or stop_event is set."""
        try:
            while not self._stop.is_set():
                self._cycle()
        except StopRequested:
            self.stats.state = SoftResetState.STOPPED
        return self.stats

    def _cycle(self) -> None:
        """One full reset cycle: load → wait → check → decide."""
        # --- Load state ---
        self.stats.state = SoftResetState.LOADING
        load_state_reset(self._emu, self._state_path, stop_event=self._stop)
        self.stats.reset_count += 1

        # --- Trigger the encounter (press A to interact) ---
        self.stats.state = SoftResetState.WAITING
        press_a(self._emu, hold_frames=2, release_frames=4, stop_event=self._stop)

        # --- Wait for battle to start ---
        battle_started = wait_until(
            self._emu,
            self._battle.in_battle,
            max_frames=self.BATTLE_WAIT_FRAMES,
            poll_interval=8,
            stop_event=self._stop,
        )
        if not battle_started:
            # Timed out — the state may not be positioned correctly.
            # Just reload and try again.
            return

        # --- Read the Pokemon ---
        self.stats.state = SoftResetState.IN_ENCOUNTER
        # Wait for encounter animation to complete before reading data
        wait_frames(self._emu, 40, stop_event=self._stop)

        if self._use_player_party:
            pkmn = self._encounter.read_player_slot(0)
        else:
            pkmn = self._encounter.wild_pokemon()

        self.stats.last_pokemon = pkmn

        # --- Check for match ---
        is_target = pkmn.species_id == self._target_id
        is_shiny_match = (not self._shiny_only) or pkmn.is_shiny

        if is_target and is_shiny_match:
            self.stats.found_pokemon = pkmn
            self.stats.state = SoftResetState.FOUND
            self._stop.set()

        if self._on_stats:
            self._on_stats(self.stats)
