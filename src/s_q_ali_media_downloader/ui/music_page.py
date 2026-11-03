"""Music workspace: paste links, resolve them, download tagged audio."""

from __future__ import annotations

import os

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from s_q_ali_media_downloader.core import settings_store
from s_q_ali_media_downloader.core.music_source import (
    MusicTrack,
    classify_url,
    track_label,
)
from s_q_ali_media_downloader.engine import (
    DEFAULT_MUSIC_FORMAT,
    MUSIC_FORMATS,
    MusicDownloadThread,
    MusicResolveThread,
    default_output_dir,
)
from s_q_ali_media_downloader.theme import C

COLUMNS = ("#", "Track", "Source", "Status", "Progress", "Quality")


class MusicPage(QWidget):
    """One page for the whole music flow: links → queue → tagged files."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MusicPage")
        self.tracks: list[MusicTrack] = []
        self._row_by_uid: dict[int, int] = {}
        self._bars: dict[int, QProgressBar] = {}
        self._resolver = None
        self._thread = None
        self._done = 0
        self._failed = 0

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._build_header())
        outer.addWidget(self._build_body(), 1)
        self._load_settings()

    # ------------------------------------------------------------------ UI
    def _build_header(self):
        header = QFrame()
        header.setObjectName("WorkHeader")
        layout = QVBoxLayout(header)
        layout.setContentsMargins(24, 14, 24, 14)
        layout.setSpacing(4)
        title = QLabel("🎵 Music Downloader")
        title.setProperty("role", "pageTitle")
        hint = QLabel(
            "Paste YouTube, YouTube Music, SoundCloud or Spotify links — one per line. "
            "Spotify links resolve to the matching YouTube audio; no account needed."
        )
        hint.setProperty("role", "hint")
        hint.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(hint)
        return header

    def _build_body(self):
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(24, 14, 24, 20)
        layout.setSpacing(10)

        self.urls = QPlainTextEdit()
        self.urls.setPlaceholderText(
            "https://open.spotify.com/playlist/…\nhttps://www.youtube.com/watch?v=…"
        )
        self.urls.setFixedHeight(90)
        layout.addWidget(self.urls)

        options = QHBoxLayout()
        options.setSpacing(8)
        options.addWidget(QLabel("Format"))
        self.format = QComboBox()
        self.format.addItems(list(MUSIC_FORMATS))
        options.addWidget(self.format, 0)
        options.addSpacing(8)
        options.addWidget(QLabel("Folder"))
        self.folder = QLineEdit()
        options.addWidget(self.folder, 1)
        browse = QPushButton("Browse…")
        browse.setProperty("kind", "ghost")
        browse.clicked.connect(self._browse)
        options.addWidget(browse)
        self.cookies = QCheckBox("Chrome cookies")
        self.cookies.setToolTip(
            "Use Chrome's cookies when YouTube asks to confirm you are not a bot. "
            "Close Chrome first."
        )
        options.addWidget(self.cookies)
        layout.addLayout(options)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.btn_add = QPushButton("Add to queue")
        self.btn_add.setProperty("kind", "primary")
        self.btn_add.clicked.connect(self.add_links)
        self.btn_start = QPushButton("Start")
        self.btn_start.clicked.connect(self.start)
        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop)
        self.btn_clear = QPushButton("Clear")
        self.btn_clear.setProperty("kind", "ghost")
        self.btn_clear.clicked.connect(self.clear)
        for button in (self.btn_add, self.btn_start, self.btn_stop, self.btn_clear):
            actions.addWidget(button)
        actions.addStretch(1)
        self.status = QLabel("Ready.")
        self.status.setProperty("role", "meta")
        actions.addWidget(self.status)
        layout.addLayout(actions)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        for column in (0, 2, 3, 4, 5):
            self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeToContents)
        layout.addWidget(self.table, 1)

        self.overall = QProgressBar()
        self.overall.setRange(0, 100)
        self.overall.setValue(0)
        self.overall.setTextVisible(False)
        layout.addWidget(self.overall)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFixedHeight(62)
        self.log.setPlaceholderText("Activity appears here.")
        layout.addWidget(self.log)
        return body

    # ------------------------------------------------------------ settings
    def _load_settings(self):
        stored = settings_store.get_setting("music_format")
        self.format.setCurrentText(stored if stored in MUSIC_FORMATS else DEFAULT_MUSIC_FORMAT)
        folder = settings_store.get_setting("music_output_dir") or default_output_dir()
        self.folder.setText(folder)
        self.format.currentTextChanged.connect(self._save_settings)
        self.folder.editingFinished.connect(self._save_settings)

    def _save_settings(self):
        settings_store.set_setting("music_format", self.format.currentText())
        settings_store.set_setting("music_output_dir", self.folder.text().strip())

    def _browse(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Choose where music is saved", self.folder.text().strip() or default_output_dir()
        )
        if folder:
            self.folder.setText(folder)
            self._save_settings()

    # ------------------------------------------------------------- resolving
    def add_links(self):
        if self._resolver is not None and self._resolver.isRunning():
            return
        lines = [line.strip() for line in self.urls.toPlainText().splitlines() if line.strip()]
        valid, skipped = [], []
        for line in lines:
            (valid if classify_url(line) else skipped).append(line)
        for line in skipped:
            self._log(f"Skipped (not a music link): {line}")
        if not valid:
            self._say("Paste at least one music link." if not lines else "No music links found.")
            return
        self._say("Resolving links…")
        self.btn_add.setEnabled(False)
        self._resolver = MusicResolveThread(valid, use_cookies=self.cookies.isChecked())
        self._resolver.resolved.connect(self._on_resolved)
        self._resolver.failed.connect(self._on_resolve_failed)
        self._resolver.note.connect(self._log)
        self._resolver.finished.connect(self._on_resolve_finished)
        self._resolver.start()

    def _on_resolved(self, tracks):
        added = 0
        for track in tracks:
            if any(
                existing.source == track.source
                and existing.title == track.title
                and existing.artist == track.artist
                for existing in self.tracks
            ):
                continue
            self._add_track(track)
            added += 1
        self._log(f"{added} track{'s' if added != 1 else ''} added to the queue.")
        self._say(f"{len(self.tracks)} track{'s' if len(self.tracks) != 1 else ''} in the queue.")

    def _on_resolve_failed(self, message):
        self._say(message, error=True)

    def _on_resolve_finished(self):
        self.btn_add.setEnabled(True)
        self._resolver = None

    # -------------------------------------------------------------- queue UI
    def _add_track(self, track):
        self.tracks.append(track)
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
        title = QTableWidgetItem(track_label(track))
        title.setToolTip(track.url)
        self.table.setItem(row, 1, title)
        self.table.setItem(row, 2, QTableWidgetItem(track.source.title()))
        self.table.setItem(row, 3, QTableWidgetItem("Queued"))
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(0)
        bar.setTextVisible(False)
        bar.setFixedHeight(14)
        self.table.setCellWidget(row, 4, bar)
        self.table.setItem(row, 5, QTableWidgetItem("—"))
        self._row_by_uid[row + 1] = row
        self._bars[row + 1] = bar

    def _row(self, uid):
        return self._row_by_uid.get(uid)

    # ------------------------------------------------------------ downloading
    def start(self):
        if self._thread is not None and self._thread.isRunning():
            return
        if not self.tracks:
            self._say("Add some links first.")
            return
        folder = self.folder.text().strip() or default_output_dir()
        self.folder.setText(folder)
        os.makedirs(folder, exist_ok=True)
        self._save_settings()
        self._done = 0
        self._failed = 0
        self.overall.setRange(0, len(self.tracks))
        self.overall.setValue(0)
        for row in range(self.table.rowCount()):
            self.table.item(row, 3).setText("Queued")
            self.table.item(row, 5).setText("—")
            bar = self.table.cellWidget(row, 4)
            if bar is not None:
                bar.setValue(0)
        self._set_running(True)
        self._say(f"Downloading {len(self.tracks)} track(s)…")
        self._log(f"Format: {MUSIC_FORMATS[self.format.currentText()]} → {folder}")
        self._thread = MusicDownloadThread(
            list(self.tracks),
            folder,
            MUSIC_FORMATS[self.format.currentText()],
            use_cookies=self.cookies.isChecked(),
        )
        self._thread.track_started.connect(self._on_started)
        self._thread.track_progress.connect(self._on_progress)
        self._thread.track_result.connect(self._on_result)
        self._thread.log.connect(self._log)
        self._thread.finished_all.connect(self._on_finished)
        self._thread.start()

    def _set_running(self, running):
        self.btn_start.setEnabled(not running)
        self.btn_add.setEnabled(not running)
        self.btn_stop.setEnabled(running)
        self.btn_clear.setEnabled(not running)
        self.format.setEnabled(not running)
        self.folder.setEnabled(not running)
        self.cookies.setEnabled(not running)

    def _on_started(self, uid, label):
        row = self._row(uid)
        if row is None:
            return
        self.table.item(row, 3).setText("Downloading")
        self.table.item(row, 5).setText("—")

    def _on_progress(self, uid, percent, size, speed):
        bar = self._bars.get(uid)
        if bar is not None:
            bar.setValue(int(percent))

    def _on_result(self, uid, status, path, detail):
        row = self._row(uid)
        if row is None:
            return
        self.table.item(row, 3).setText(status)
        self.table.item(row, 5).setText(detail)
        if path and path != "—":
            self.table.item(row, 5).setToolTip(path)
        bar = self._bars.get(uid)
        if bar is not None:
            bar.setValue(100 if status == "Done" else 0)
        if status == "Done":
            self._done += 1
        else:
            self._failed += 1
        self.overall.setValue(self._done + self._failed)
        self._log(f"{status}: {self.table.item(row, 1).text()}" + (f" — {detail}" if status != "Done" else ""))

    def _on_finished(self):
        self._thread = None
        self._set_running(False)
        stopped = False
        for row in range(self.table.rowCount()):
            if self.table.item(row, 3).text() in ("Queued", "Downloading"):
                self.table.item(row, 3).setText("Stopped")
                stopped = True
        self.overall.setValue(self._done + self._failed)
        prefix = "Stopped" if stopped else "Done"
        self._say(f"{prefix} · {self._done} saved, {self._failed} failed.")

    def stop(self):
        if self._resolver is not None and self._resolver.isRunning():
            self._resolver.stop()
        if self._thread is not None and self._thread.isRunning():
            self._thread.stop()
            self._say("Stopping after the current track…")

    def is_running(self):
        resolving = self._resolver is not None and self._resolver.isRunning()
        downloading = self._thread is not None and self._thread.isRunning()
        return resolving or downloading

    def clear(self):
        if self.is_running():
            return
        self.tracks.clear()
        self._row_by_uid.clear()
        self._bars.clear()
        self.table.setRowCount(0)
        self.overall.setRange(0, 100)
        self.overall.setValue(0)
        self._say("Queue cleared.")

    # -------------------------------------------------------------- feedback
    def _say(self, text, error=False):
        self.status.setText(text)
        self.status.setStyleSheet(f"color: {C['failed']};" if error else "")

    def _log(self, text):
        if text:
            self.log.appendPlainText(str(text))
