"""Application entry point for S-Q Creator Studio."""

import logging
import os
import re
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PySide6.QtCore import QStandardPaths, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from s_q_ali_media_downloader.engine import APP_NAME
from s_q_ali_media_downloader.ui.main_window import ORG, MainWindow, resource

_SECRET_RE = re.compile(
    r"(?i)\b(api[_-]?key|key|token|access[_-]?token|secret|password)=([^&\s\"']+)"
)


class RedactSecrets(logging.Filter):
    """Strip API keys and tokens out of log messages.

    The log file sits next to the user's data and is what people attach to
    bug reports, so a credential must never reach it — not even inside a
    request URL that a third-party library logged on our behalf.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _SECRET_RE.sub(r"\1=***", record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(
                _SECRET_RE.sub(r"\1=***", arg) if isinstance(arg, str) else arg
                for arg in record.args
            )
        elif isinstance(record.args, str):
            record.args = _SECRET_RE.sub(r"\1=***", record.args)
        return True


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
        file_handler.addFilter(RedactSecrets())
        root = logging.getLogger()
        root.setLevel(logging.INFO)
        root.addHandler(file_handler)
        # httpx logs every request URL at INFO — that is where a key in a
        # query string would have ended up on disk.
        logging.getLogger("httpx").setLevel(logging.WARNING)
        if not getattr(sys, "frozen", False):
            console = logging.StreamHandler()
            console.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
            console.addFilter(RedactSecrets())
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
    
    # Apply neon theme by default
    from s_q_ali_media_downloader.ui.themes import apply_neon_theme
    apply_neon_theme(app)
    
    setup_logging()
    sys.excepthook = _excepthook

    icon_path = resource("icon.ico")
    if os.path.isfile(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = MainWindow()
    window.show()
    QTimer.singleShot(0, lambda: window.folder_edit.setCursorPosition(0))
    return app.exec()
