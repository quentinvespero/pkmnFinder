"""HuntConfigPanel: ROM picker, target species, shiny checkbox, instance count, Start/Stop."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pokefinder.hunt.config import HuntConfig, HuntMethod
from pokefinder.pokemon.species import all_species


class HuntConfigPanel(QWidget):
    """Configuration panel for setting up a new hunt.

    Emits:
        hunt_started(HuntConfig) — when Start is clicked with valid config
        hunt_stopped()           — when Stop is clicked
    """

    hunt_started = pyqtSignal(object)  # HuntConfig
    hunt_stopped = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rom_path: Path | None = None
        self._state_path: Path | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # --- ROM Group ---
        rom_group = QGroupBox("ROM")
        rom_layout = QHBoxLayout(rom_group)
        self._rom_label = QLabel("No ROM selected")
        self._rom_label.setWordWrap(True)
        rom_layout.addWidget(self._rom_label, stretch=1)
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_rom)
        rom_layout.addWidget(browse_btn)
        root.addWidget(rom_group)

        # --- Hunt Options Group ---
        opts_group = QGroupBox("Hunt Options")
        form = QFormLayout(opts_group)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)

        # Species search
        species_row = QHBoxLayout()
        self._species_search = QLineEdit()
        self._species_search.setPlaceholderText("Search…")
        self._species_search.textChanged.connect(self._filter_species)
        species_row.addWidget(self._species_search)
        self._species_combo = QComboBox()
        self._species_combo.setMinimumWidth(180)
        self._populate_species()
        species_row.addWidget(self._species_combo, stretch=1)
        form.addRow("Target species:", species_row)

        # Shiny only
        self._shiny_checkbox = QCheckBox("Shiny only")
        self._shiny_checkbox.setChecked(True)
        form.addRow("", self._shiny_checkbox)

        # Method
        self._method_combo = QComboBox()
        self._method_combo.addItem("Wild encounters (grass)", HuntMethod.WILD)
        self._method_combo.addItem("Soft resets (starters/legendaries)", HuntMethod.SOFT_RESET)
        self._method_combo.currentIndexChanged.connect(self._on_method_changed)
        form.addRow("Method:", self._method_combo)

        # Save state (soft reset only)
        self._state_row_widget = QWidget()
        state_row = QHBoxLayout(self._state_row_widget)
        state_row.setContentsMargins(0, 0, 0, 0)
        self._state_label = QLabel("No state selected")
        self._state_label.setWordWrap(True)
        state_row.addWidget(self._state_label, stretch=1)
        state_browse_btn = QPushButton("Browse…")
        state_browse_btn.clicked.connect(self._browse_state)
        state_row.addWidget(state_browse_btn)
        form.addRow("Save state:", self._state_row_widget)
        self._state_row_widget.setVisible(False)

        # Instance count
        self._instance_spin = QSpinBox()
        self._instance_spin.setRange(1, 16)
        self._instance_spin.setValue(4)
        self._instance_spin.setSuffix(" instances")
        form.addRow("Parallel instances:", self._instance_spin)

        root.addWidget(opts_group)

        # --- Start / Stop buttons ---
        btn_row = QHBoxLayout()
        self._start_btn = QPushButton("Start Hunt")
        self._start_btn.setFixedHeight(36)
        self._start_btn.clicked.connect(self._on_start)
        self._stop_btn = QPushButton("Stop Hunt")
        self._stop_btn.setFixedHeight(36)
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._on_stop)
        btn_row.addWidget(self._start_btn)
        btn_row.addWidget(self._stop_btn)
        root.addLayout(btn_row)

        root.addStretch()

    # ------------------------------------------------------------------
    # Species combo
    # ------------------------------------------------------------------

    def _populate_species(self, filter_text: str = "") -> None:
        self._species_combo.blockSignals(True)
        self._species_combo.clear()
        filter_lower = filter_text.lower()
        for dex_id, name in all_species():
            if filter_lower in name.lower() or filter_lower in str(dex_id):
                self._species_combo.addItem(f"#{dex_id:03d} {name}", dex_id)
        self._species_combo.blockSignals(False)

    def _filter_species(self, text: str) -> None:
        self._populate_species(text)

    # ------------------------------------------------------------------
    # File dialogs
    # ------------------------------------------------------------------

    def _browse_rom(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select GBA ROM", str(Path("roms")), "GBA ROMs (*.gba);;All files (*)"
        )
        if path:
            self._rom_path = Path(path)
            self._rom_label.setText(self._rom_path.name)

    def _browse_state(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Save State", str(Path("saves")), "Save States (*.ss1 *.state);;All files (*)"
        )
        if path:
            self._state_path = Path(path)
            self._state_label.setText(self._state_path.name)

    # ------------------------------------------------------------------
    # Method selection
    # ------------------------------------------------------------------

    def _on_method_changed(self, _: int) -> None:
        method = self._method_combo.currentData()
        self._state_row_widget.setVisible(method == HuntMethod.SOFT_RESET)

    # ------------------------------------------------------------------
    # Start / Stop
    # ------------------------------------------------------------------

    def _on_start(self) -> None:
        config = self._build_config()
        if config is None:
            return

        errors = config.validate()
        if errors:
            QMessageBox.warning(self, "Invalid Configuration", "\n".join(errors))
            return

        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self.hunt_started.emit(config)

    def _on_stop(self) -> None:
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self.hunt_stopped.emit()

    def _build_config(self) -> HuntConfig | None:
        if self._rom_path is None:
            QMessageBox.warning(self, "Missing ROM", "Please select a GBA ROM file.")
            return None

        dex_id = self._species_combo.currentData()
        if dex_id is None:
            QMessageBox.warning(self, "Missing Species", "Please select a target species.")
            return None

        method = self._method_combo.currentData()
        from pokefinder.pokemon.species import species_name

        return HuntConfig(
            rom_path=self._rom_path,
            target_species_id=dex_id,
            target_species_name=species_name(dex_id),
            shiny_only=self._shiny_checkbox.isChecked(),
            method=method,
            num_instances=self._instance_spin.value(),
            state_path=self._state_path,
        )

    def set_hunt_stopped(self) -> None:
        """Call from the main window when the hunt stops (e.g., target found)."""
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
