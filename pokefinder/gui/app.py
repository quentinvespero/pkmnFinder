"""QApplication setup and high-DPI configuration."""

from __future__ import annotations

import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication


def create_app(argv: list[str] | None = None) -> QApplication:
    """Create and configure the QApplication.

    High-DPI scaling is enabled by default in PyQt6 — no explicit flags needed.
    """
    if argv is None:
        argv = sys.argv

    app = QApplication(argv)
    app.setApplicationName("Pokemon Finder")
    app.setApplicationVersion("0.1.0")
    app.setOrganizationName("pokefinder")

    # Apply a clean dark-ish palette
    app.setStyle("Fusion")

    return app
