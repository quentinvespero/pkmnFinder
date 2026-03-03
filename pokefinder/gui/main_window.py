"""MainWindow: the top-level application window.

Layout:
  Left panel  : HuntConfigPanel (fixed width ~280px)
  Right panel : InstanceGrid (scrollable, expands)

Wire-up:
  - Config panel hunt_started → start coordinator
  - Config panel hunt_stopped → stop coordinator
  - Coordinator stats_updated → grid card updates
  - Coordinator found → found dialog + snapshot save
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QWidget,
)
from PyQt6.QtCore import Qt

from pokefinder.gui.hunt_config_panel import HuntConfigPanel
from pokefinder.gui.instance_grid import InstanceGrid
from pokefinder.hunt.config import HuntConfig
from pokefinder.hunt.coordinator import HuntCoordinator
from pokefinder.pokemon.structs import Pokemon


class MainWindow(QMainWindow):
    """The main application window."""

    def __init__(self) -> None:
        super().__init__()
        self._coordinator: HuntCoordinator | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowTitle("Pokemon Finder")
        self.resize(1024, 600)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        # Left: config panel
        self._config_panel = HuntConfigPanel()
        self._config_panel.setFixedWidth(300)
        self._config_panel.hunt_started.connect(self._on_hunt_started)
        self._config_panel.hunt_stopped.connect(self._on_hunt_stopped)
        splitter.addWidget(self._config_panel)

        # Right: instance grid
        self._grid = InstanceGrid()
        splitter.addWidget(self._grid)
        splitter.setStretchFactor(1, 1)

    # ------------------------------------------------------------------
    # Hunt lifecycle
    # ------------------------------------------------------------------

    def _on_hunt_started(self, config: HuntConfig) -> None:
        """Called when the user clicks Start."""
        # Tear down any existing coordinator
        if self._coordinator is not None:
            self._coordinator.stop()

        # Set up instance grid
        self._grid.setup_instances(config.num_instances)

        # Create and start coordinator
        self._coordinator = HuntCoordinator(
            config=config,
            on_stats_update=self._on_stats_update,
            on_found=self._on_found,
            on_error=self._on_error,
        )
        self._coordinator.start()

    def _on_hunt_stopped(self) -> None:
        """Called when the user clicks Stop."""
        if self._coordinator is not None:
            self._coordinator.stop()
            self._coordinator = None

    # ------------------------------------------------------------------
    # Coordinator signal handlers (main thread)
    # ------------------------------------------------------------------

    def _on_stats_update(self, instance_id: int, count: int, rate: float, state: str) -> None:
        self._grid.update_stats(instance_id, count, rate, state)

    def _on_found(self, instance_id: int, pokemon: Pokemon) -> None:
        """Handle a found event: update the grid and show a dialog."""
        self._grid.mark_found(instance_id, str(pokemon))
        self._config_panel.set_hunt_stopped()

        shiny_tag = " ✨ SHINY ✨" if pokemon.is_shiny else ""
        msg = (
            f"<b>Pokemon Found!</b><br><br>"
            f"Instance #{instance_id + 1} found:<br>"
            f"<b>#{pokemon.species_id:03d} {pokemon.species_name}{shiny_tag}</b><br><br>"
            f"PID: {pokemon.pid:#010x}<br>"
            f"TID: {pokemon.tid} | SID: {pokemon.sid}<br>"
            f"IVs: {pokemon.iv_hp}/{pokemon.iv_atk}/{pokemon.iv_def}/"
            f"{pokemon.iv_spa}/{pokemon.iv_spd_special}/{pokemon.iv_spd}<br><br>"
            f"The winning save state has been saved to the <tt>saves/</tt> directory."
        )
        QMessageBox.information(self, "Target Found!", msg)

    def _on_error(self, instance_id: int, message: str) -> None:
        """Handle an instance error."""
        QMessageBox.critical(
            self,
            f"Error — Instance #{instance_id + 1}",
            message,
        )
        # Stop everything if mGBA is not installed
        if "mgba" in message.lower():
            if self._coordinator:
                self._coordinator.stop()
            self._config_panel.set_hunt_stopped()

    def closeEvent(self, event) -> None:
        """Stop all instances when the window is closed."""
        if self._coordinator is not None:
            self._coordinator.stop()
        event.accept()
