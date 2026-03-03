"""HuntCoordinator: spawn N parallel hunt instances, stop all when one finds the target.

The coordinator owns the shared stop_event and the QThreadPool. It:
  1. Creates N HuntInstance runnables
  2. Wires their signals to the GUI (caller provides callbacks)
  3. Starts all instances via QThreadPool
  4. Stops all instances when any emits the `found` signal

Threading model:
  - Coordinator runs in the main thread
  - HuntInstances run in QThreadPool worker threads
  - stop_event is the cross-thread shutdown mechanism
  - Qt signal connections use Qt.ConnectionType.AutoConnection (queued when
    crossing thread boundaries), so GUI callbacks are always called in the
    main thread
"""

from __future__ import annotations

import threading
from typing import Callable

from PyQt6.QtCore import QThreadPool

from pokefinder.hunt.config import HuntConfig
from pokefinder.hunt.instance import HuntInstance
from pokefinder.pokemon.structs import Pokemon


class HuntCoordinator:
    """Manages N parallel HuntInstance workers.

    Parameters
    ----------
    config:
        HuntConfig shared across all instances.
    on_stats_update:
        Called when any instance emits stats_updated.
        Signature: (instance_id: int, count: int, rate: float, state: str) -> None
    on_found:
        Called when any instance emits found.
        Signature: (instance_id: int, pokemon: Pokemon) -> None
    on_error:
        Called when any instance emits error.
        Signature: (instance_id: int, message: str) -> None
    """

    def __init__(
        self,
        config: HuntConfig,
        on_stats_update: Callable[[int, int, float, str], None] | None = None,
        on_found: Callable[[int, Pokemon], None] | None = None,
        on_error: Callable[[int, str], None] | None = None,
    ) -> None:
        self._config = config
        self._on_stats = on_stats_update
        self._on_found = on_found
        self._on_error = on_error

        self._stop_event = threading.Event()
        self._pool = QThreadPool.globalInstance()
        self._instances: list[HuntInstance] = []
        self._running = False

    # ------------------------------------------------------------------
    # Control
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Spawn all instances and start the hunt."""
        if self._running:
            return

        self._stop_event.clear()
        self._instances = []
        self._running = True

        for i in range(self._config.num_instances):
            instance = HuntInstance(
                instance_id=i,
                config=self._config,
                stop_event=self._stop_event,
            )
            # Wire signals
            instance.signals.stats_updated.connect(self._handle_stats)
            instance.signals.found.connect(self._handle_found)
            instance.signals.error.connect(self._handle_error)

            self._instances.append(instance)
            self._pool.start(instance)

    def stop(self) -> None:
        """Signal all instances to stop gracefully."""
        self._stop_event.set()
        self._running = False

    def wait_for_done(self, timeout_ms: int = 30_000) -> None:
        """Block until all pool threads finish (used in tests)."""
        self._pool.waitForDone(timeout_ms)

    @property
    def is_running(self) -> bool:
        return self._running and not self._stop_event.is_set()

    # ------------------------------------------------------------------
    # Signal handlers (called in main thread via Qt queued connections)
    # ------------------------------------------------------------------

    def _handle_stats(self, instance_id: int, count: int, rate: float, state: str) -> None:
        if self._on_stats:
            self._on_stats(instance_id, count, rate, state)

    def _handle_found(self, instance_id: int, pokemon: Pokemon) -> None:
        # Stop all other instances
        self._stop_event.set()
        self._running = False

        if self._on_found:
            self._on_found(instance_id, pokemon)

    def _handle_error(self, instance_id: int, message: str) -> None:
        if self._on_error:
            self._on_error(instance_id, message)
