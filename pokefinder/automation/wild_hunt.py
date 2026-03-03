"""WildHuntAutomation: state machine for wild encounter shiny hunting.

Strategy:
  1. Walk in grass (alternate LEFT/RIGHT) until a battle starts
  2. Once in battle, read gEnemyParty[0] to get the wild Pokemon
  3. If it matches the target: signal found and stop
  4. Otherwise: navigate to RUN and escape, increment counter, repeat

State machine states:
    WALKING       — walking in grass, waiting for an encounter
    IN_BATTLE     — battle detected, reading Pokemon
    FLEEING       — navigating the battle menu to run away
    FOUND         — target Pokemon detected (terminal state)
    STOPPED       — stop_event was set (terminal state)
"""

from __future__ import annotations

import enum
import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

from pokefinder.automation.actions import (
    StopRequested,
    dpad,
    run_away,
    wait_frames,
    wait_until,
)
from pokefinder.emulator import buttons
from pokefinder.pokemon.structs import Pokemon

if TYPE_CHECKING:
    from pokefinder.emulator.core import LibmgbaEmulator
    from pokefinder.game_state.battle import BattleStateReader
    from pokefinder.game_state.encounter import EncounterReader
    from pokefinder.game_state.player import PlayerStateReader


class WildState(enum.Enum):
    WALKING = "walking"
    IN_BATTLE = "in_battle"
    FLEEING = "fleeing"
    FOUND = "found"
    STOPPED = "stopped"


@dataclass
class WildHuntStats:
    encounter_count: int = 0
    state: WildState = WildState.WALKING
    last_pokemon: Pokemon | None = None
    found_pokemon: Pokemon | None = None


class WildHuntAutomation:
    """Drives a single emulator instance to hunt for a wild Pokemon.

    Parameters
    ----------
    emulator:
        LibmgbaEmulator instance.
    battle_reader:
        BattleStateReader for the loaded ROM.
    encounter_reader:
        EncounterReader for the loaded ROM.
    player_reader:
        PlayerStateReader for the loaded ROM.
    target_species_id:
        National Dex ID to hunt for.
    shiny_only:
        If True, only stop on a shiny specimen.
    stop_event:
        threading.Event set by the coordinator when any instance finds a match.
    on_stats_update:
        Optional callback called after each encounter with the current stats.
    """

    # Frames to walk in one direction before alternating
    WALK_FRAMES = 16
    # Max frames to wait for an encounter to start
    ENCOUNTER_WAIT_FRAMES = 300
    # Max frames to wait to return to overworld after fleeing
    OVERWORLD_WAIT_FRAMES = 300

    def __init__(
        self,
        emulator: "LibmgbaEmulator",
        battle_reader: "BattleStateReader",
        encounter_reader: "EncounterReader",
        player_reader: "PlayerStateReader",
        target_species_id: int,
        shiny_only: bool,
        stop_event: threading.Event,
        on_stats_update: Callable[[WildHuntStats], None] | None = None,
    ) -> None:
        self._emu = emulator
        self._battle = battle_reader
        self._encounter = encounter_reader
        self._player = player_reader
        self._target_id = target_species_id
        self._shiny_only = shiny_only
        self._stop = stop_event
        self._on_stats = on_stats_update
        self.stats = WildHuntStats()
        self._direction = buttons.LEFT

    def run(self) -> WildHuntStats:
        """Run the hunt loop until a match is found or stop_event is set.

        Returns the final stats.
        """
        try:
            while not self._stop.is_set():
                self._step()
        except StopRequested:
            self.stats.state = WildState.STOPPED
        return self.stats

    def _step(self) -> None:
        state = self.stats.state

        if state == WildState.WALKING:
            self._do_walk()
        elif state == WildState.IN_BATTLE:
            self._do_battle()
        elif state == WildState.FLEEING:
            self._do_flee()

    # ------------------------------------------------------------------
    # WALKING state
    # ------------------------------------------------------------------

    def _do_walk(self) -> None:
        """Walk one step in the current direction, then check for a battle."""
        if not self._player.is_controllable():
            wait_frames(self._emu, 4, stop_event=self._stop)
            return

        # Take a step
        dpad(self._emu, self._direction, hold_frames=self.WALK_FRAMES, stop_event=self._stop)

        # Alternate direction
        self._direction = buttons.RIGHT if self._direction == buttons.LEFT else buttons.LEFT

        # Check if a battle started
        if self._battle.in_battle():
            self.stats.state = WildState.IN_BATTLE
            return

        # Wait for the encounter check (mGBA runs encounter RNG during the step)
        encountered = wait_until(
            self._emu,
            self._battle.in_battle,
            max_frames=self.ENCOUNTER_WAIT_FRAMES,
            poll_interval=4,
            stop_event=self._stop,
        )
        if encountered:
            self.stats.state = WildState.IN_BATTLE

    # ------------------------------------------------------------------
    # IN_BATTLE state
    # ------------------------------------------------------------------

    def _do_battle(self) -> None:
        """Read the wild Pokemon and decide whether to stop or flee."""
        # Wait for the battle intro animations to finish before reading
        # (Bulbapedia: data is set up ~40 frames into the battle)
        wait_frames(self._emu, 40, stop_event=self._stop)

        pkmn = self._encounter.wild_pokemon()
        self.stats.encounter_count += 1
        self.stats.last_pokemon = pkmn

        is_target = pkmn.species_id == self._target_id
        is_shiny_match = (not self._shiny_only) or pkmn.is_shiny

        if is_target and is_shiny_match:
            self.stats.found_pokemon = pkmn
            self.stats.state = WildState.FOUND
            self._stop.set()
        else:
            self.stats.state = WildState.FLEEING

        if self._on_stats:
            self._on_stats(self.stats)

    # ------------------------------------------------------------------
    # FLEEING state
    # ------------------------------------------------------------------

    def _do_flee(self) -> None:
        """Run away from the current battle and return to overworld."""
        run_away(self._emu, stop_event=self._stop)

        # Wait to return to the overworld
        wait_until(
            self._emu,
            self._player.is_controllable,
            max_frames=self.OVERWORLD_WAIT_FRAMES,
            poll_interval=8,
            stop_event=self._stop,
        )
        self.stats.state = WildState.WALKING
