"""InstanceCard: per-instance status card in the hunt grid.

Displays:
  - Instance ID
  - Current state (walking / in_battle / fleeing / found / stopped)
  - Encounter/reset count
  - Rate (encounters or resets per hour)
  - Last seen Pokemon
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QGridLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget


class InstanceCard(QWidget):
    """Status card for a single hunt instance."""

    def __init__(self, instance_id: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.instance_id = instance_id
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setMinimumWidth(180)
        self.setMaximumWidth(260)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        # Use a framed box
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setFrameShadow(QFrame.Shadow.Raised)
        outer.addWidget(frame)

        layout = QGridLayout(frame)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # Title row
        title = QLabel(f"Instance #{self.instance_id + 1}")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(title, 0, 0, 1, 2)

        # State
        layout.addWidget(QLabel("State:"), 1, 0)
        self._state_label = QLabel("idle")
        self._state_label.setStyleSheet("color: gray;")
        layout.addWidget(self._state_label, 1, 1)

        # Count
        layout.addWidget(QLabel("Encounters:"), 2, 0)
        self._count_label = QLabel("0")
        layout.addWidget(self._count_label, 2, 1)

        # Rate
        layout.addWidget(QLabel("Rate:"), 3, 0)
        self._rate_label = QLabel("—")
        layout.addWidget(self._rate_label, 3, 1)

        # Last seen
        layout.addWidget(QLabel("Last:"), 4, 0)
        self._last_label = QLabel("—")
        self._last_label.setWordWrap(True)
        layout.addWidget(self._last_label, 4, 1)

        layout.setColumnStretch(1, 1)

    # ------------------------------------------------------------------
    # Update methods (called from main thread via signal connections)
    # ------------------------------------------------------------------

    def update_stats(self, count: int, rate: float, state: str) -> None:
        """Update the displayed stats."""
        self._count_label.setText(str(count))
        self._rate_label.setText(f"{rate:.0f}/hr" if rate > 0 else "—")

        state_display = state.replace("_", " ").title()
        self._state_label.setText(state_display)

        # Color-code state
        color_map = {
            "walking": "#2a9d8f",
            "in_battle": "#e9c46a",
            "fleeing": "#f4a261",
            "found": "#06d6a0",
            "stopped": "#aaa",
            "loading": "#8ecae6",
            "waiting": "#e9c46a",
            "in_encounter": "#f4a261",
        }
        color = color_map.get(state, "#ccc")
        self._state_label.setStyleSheet(f"color: {color}; font-weight: bold;")

    def update_last_pokemon(self, name: str, is_shiny: bool = False) -> None:
        """Update the last-seen Pokemon name."""
        text = f"{'✨' if is_shiny else ''}{name}"
        self._last_label.setText(text)

    def set_found(self, pokemon_str: str) -> None:
        """Mark this card as the winner."""
        self._state_label.setText("FOUND!")
        self._state_label.setStyleSheet("color: #06d6a0; font-weight: bold; font-size: 14px;")
        self._last_label.setText(pokemon_str)
        self.setStyleSheet("background-color: #1a3a2a;")
