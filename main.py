"""Pokemon Finder — entry point."""

import sys

from PyQt6.QtWidgets import QApplication

from pokefinder.gui.app import create_app
from pokefinder.gui.main_window import MainWindow


def main() -> None:
    app = create_app(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
