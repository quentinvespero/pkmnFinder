"""Pokemon Finder — entry point."""

import faulthandler
import logging
import sys
from pathlib import Path

from pokefinder.gui.app import create_app
from pokefinder.gui.main_window import MainWindow

LOG_FILE = Path(__file__).parent / "pokefinder.log"


def _setup_logging() -> None:
    LOG_FILE.unlink(missing_ok=True)
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(
        level=logging.DEBUG,
        format=fmt,
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(sys.stderr),
        ],
    )

    # Catch unhandled Python exceptions
    def _excepthook(exc_type, exc_value, exc_tb):
        logging.critical("Unhandled exception", exc_info=(exc_type, exc_value, exc_tb))
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = _excepthook


_fault_log_fh = None  # kept open for faulthandler


def main() -> None:
    global _fault_log_fh
    _setup_logging()

    # faulthandler writes a traceback on SIGSEGV/SIGABRT (native crashes).
    # Keep the file handle open for the lifetime of the process.
    _fault_log_fh = LOG_FILE.open("ab")
    faulthandler.enable(_fault_log_fh)

    log = logging.getLogger("main")
    log.info("Starting Pokemon Finder")

    app = create_app(sys.argv)
    window = MainWindow()
    window.show()
    log.info("GUI ready — entering event loop")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
