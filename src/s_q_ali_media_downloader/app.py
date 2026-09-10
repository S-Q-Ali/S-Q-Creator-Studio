"""Application entry point for S-Q-Ali Media Downloader."""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PySide6.QtCore import QStandardPaths, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from s_q_ali_media_downloader.engine import APP_NAME
from s_q_ali_media_downloader.theme import STYLESHEET
from s_q_ali_media_downloader.ui.main_window import ORG, MainWindow, resource


def setup_logging() -> None:
    """Rotating file log (1 MB x 3) plus console while running from source.

    Uses the same per-user local-app-data folder as the settings store, so
    support logs live next to the user's data instead of next to the EXE.
    """
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
    log_dir = Path(base) if base else Path.home() / ".s_q_ali_media_downloader"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_dir / "app.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        root = logging.getLogger()
        root.setLevel(logging.INFO)
        root.addHandler(file_handler)
        if not getattr(sys, "frozen", False):
            console = logging.StreamHandler()
            console.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
            root.addHandler(console)
    except OSError:
        pass  # logging must never take the app down
    logging.captureWarnings(True)
    root.info("app starting")


def _excepthook(exc_type, exc_value, exc_tb) -> None:
    logging.getLogger(__name__).error("Unhandled exception", exc_info=(exc_type, exc_value, exc_tb))
    sys.__excepthook__(exc_type, exc_value, exc_tb)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG)
    app.setStyleSheet(STYLESHEET)
    setup_logging()
    sys.excepthook = _excepthook

    icon_path = resource("icon.ico")
    if os.path.isfile(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = MainWindow()
    window.show()
    QTimer.singleShot(0, lambda: window.folder_edit.setCursorPosition(0))
    return app.exec()
