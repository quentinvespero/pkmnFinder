"""InstanceGrid: scrollable grid of InstanceCards."""

from __future__ import annotations

import math

from PyQt6.QtWidgets import (
    QGridLayout,
    QScrollArea,
    QSizePolicy,
    QWidget,
)

from pokefinder.gui.instance_card import InstanceCard


class InstanceGrid(QWidget):
    """A scrollable grid that holds one InstanceCard per hunt instance.

    Cards are laid out in a grid with up to *columns_hint* columns.
    """

    COLUMNS_HINT = 4

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cards: dict[int, InstanceCard] = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        from PyQt6.QtWidgets import QVBoxLayout

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        outer.addWidget(self._scroll)

        self._container = QWidget()
        self._scroll.setWidget(self._container)
        self._grid = QGridLayout(self._container)
        self._grid.setSpacing(8)
        self._grid.setContentsMargins(8, 8, 8, 8)

    # ------------------------------------------------------------------
    # Card management
    # ------------------------------------------------------------------

    def setup_instances(self, count: int) -> None:
        """Remove existing cards and create *count* new ones."""
        # Clear existing
        for card in self._cards.values():
            self._grid.removeWidget(card)
            card.deleteLater()
        self._cards.clear()

        cols = min(self.COLUMNS_HINT, count)
        for i in range(count):
            row = i // cols
            col = i % cols
            card = InstanceCard(instance_id=i)
            self._cards[i] = card
            self._grid.addWidget(card, row, col)

        # Fill remaining cells with spacers so cards left-align
        if count % cols != 0:
            spacer_col = count % cols
            spacer_row = count // cols
            for c in range(spacer_col, cols):
                spacer = QWidget()
                spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
                self._grid.addWidget(spacer, spacer_row, c)

    def get_card(self, instance_id: int) -> InstanceCard | None:
        return self._cards.get(instance_id)

    # ------------------------------------------------------------------
    # Bulk updates (called from main thread)
    # ------------------------------------------------------------------

    def update_stats(self, instance_id: int, count: int, rate: float, state: str) -> None:
        card = self._cards.get(instance_id)
        if card:
            card.update_stats(count, rate, state)

    def mark_found(self, instance_id: int, pokemon_str: str) -> None:
        card = self._cards.get(instance_id)
        if card:
            card.set_found(pokemon_str)

    def update_frame(self, instance_id: int, data: bytes) -> None:
        card = self._cards.get(instance_id)
        if card:
            card.update_screen(data)
