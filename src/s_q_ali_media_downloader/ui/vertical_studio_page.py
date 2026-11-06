"""Vertical Studio: the 9:16 reframe and the shorts split over local files.

The download flow already makes these two versions after it saves a video.
This section is for the files it did not download — one from a phone, one
from the edits folder, one downloaded last week. The work itself is the same
code the download worker runs (`engine.run_post_leg`), reached through the
same options the Settings page holds.

Nothing here touches a source file: every output lands beside it.
"""

from __future__ import annotations

import os

from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from s_q_ali_media_downloader.engine import (
    DEFAULT_CLIPS,
    DEFAULT_SPLIT,
    SPLIT_CLIPS,
    SPLIT_OPTIONS,
    LocalVideoThread,
    default_output_dir,
)
from s_q_ali_media_downloader.theme import C
from s_q_ali_media_downloader.ui.settings_page import (
    MAX_CLIPS,
    MIN_CLIPS,
    _clip_count,
    _is_true,
    make_settings,
)

# The containers the tracker can open. Anything else in a drop is named and
# skipped rather than handed to ffmpeg and watched fail.
VIDEO_SUFFIXES = (
    ".mp4", ".m4v", ".mov", ".mkv", ".webm", ".avi", ".wmv", ".flv",
    ".mpg", ".mpeg", ".ts", ".mts", ".m2ts",
)

PICKER = "Videos (" + " ".join(f"*{suffix}" for suffix in VIDEO_SUFFIXES) + ")"

# The download options above are borrowed and read only; this key is the
# Studio's own, and the Studio is the only place that writes it.
RESULTS_KEY = "studio_output_dir"


def is_video_file(path: str) -> bool:
    """A regular file whose container the reframe can read."""
    return os.path.isfile(path) and os.path.splitext(path)[1].lower() in VIDEO_SUFFIXES


def can_write_to(folder: str) -> bool:
    """Whether a file can be made in this folder and taken out again.

    The run does exactly that, so the answer is worth having before ffmpeg
    starts on work that could never have landed: a read-only share, a path
    that is a file, a disk with nothing on it all say no here.
    """
    probe = os.path.join(folder, ".sq-studio-probe")
    try:
        os.makedirs(folder, exist_ok=True)
        with open(probe, "wb"):
            pass
        os.remove(probe)
    except OSError:
        return False
    return True


class VerticalStudioPage(QWidget):
    """One page for the whole local flow: drop → options → outputs beside it."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("VerticalStudioPage")
        self.paths: list[str] = []
        self._thread = None
        self._current = ""
        self._index = 0
        self._total = 0

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._build_header())
        outer.addWidget(self._build_body(), 1)

        self.setAcceptDrops(True)
        self._load_options()

    # ------------------------------------------------------------------ UI
    def _build_header(self):
        header = QFrame()
        header.setObjectName("WorkHeader")
        layout = QVBoxLayout(header)
        layout.setContentsMargins(24, 14, 24, 14)
        layout.setSpacing(4)
        title = QLabel("📐 Vertical Studio")
        title.setProperty("role", "pageTitle")
        hint = QLabel(
            "Drop videos here — or Browse to them — and the app makes the vertical 9:16 "
            "version and the shorts it would have made after a download. The outputs land "
            "beside each file and the source is never touched. Allow about four seconds "
            "of work per second of video."
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

        zone = QFrame()
        zone.setObjectName("DropZone")
        zone_layout = QVBoxLayout(zone)
        zone_layout.setContentsMargins(16, 18, 16, 18)
        zone_layout.setSpacing(2)
        zone_title = QLabel("Drop video files here")
        zone_title.setProperty("role", "section")
        zone_hint = QLabel("Or press Browse. Files only — folders and links are named and skipped.")
        zone_hint.setProperty("role", "hint")
        zone_layout.addWidget(zone_title)
        zone_layout.addWidget(zone_hint)
        # The zone takes the room the list does not: it is the thing the user
        # aims at, and a thin strip of it is hard to hit.
        layout.addWidget(zone, 1)

        self.files = QListWidget()
        self.files.setSelectionMode(QAbstractItemView.SingleSelection)
        self.files.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.files.setUniformItemSizes(True)
        self.files.setMaximumHeight(180)
        self.files.itemDoubleClicked.connect(self._remove_row)
        layout.addWidget(self.files)

        options = QHBoxLayout()
        options.setSpacing(8)
        self.vertical = QCheckBox("Make a vertical 9:16 version")
        self.vertical.setToolTip(
            "The 9:16 camera follows the subject and cuts the tall frame out of the picture."
        )
        options.addWidget(self.vertical)
        options.addSpacing(8)
        options.addWidget(QLabel("Shorts"))
        self.split = QComboBox()
        self.split.addItems(SPLIT_OPTIONS)
        self.split.setMaximumWidth(220)
        self.split.setToolTip(
            "Cut the file into shorts at the pauses. Off keeps the file whole."
        )
        options.addWidget(self.split)
        self.clips_label = QLabel("clips")
        self.clips_label.setProperty("role", "hint")
        self.clips = QSpinBox()
        self.clips.setRange(MIN_CLIPS, MAX_CLIPS)
        self.clips.setValue(DEFAULT_CLIPS)
        self.clips.setToolTip("How many clips the length is divided into.")
        options.addWidget(self.clips_label)
        options.addWidget(self.clips)
        options.addStretch(1)
        self.split.currentTextChanged.connect(self._show_clip_count)
        layout.addLayout(options)

        # The file is copied into this folder and worked on there, so the
        # folder ends up holding the film, its vertical and its shorts.
        where = QHBoxLayout()
        where.setSpacing(8)
        where.addWidget(QLabel("Save results to"))
        self.results = QLineEdit()
        self.results.setPlaceholderText("Beside each file")
        self.results.setToolTip(
            "The folder the vertical and the shorts go into, with a copy of "
            "each video beside them. Empty leaves everything where the video "
            "already is."
        )
        self.results.textChanged.connect(self._show_results_reset)
        where.addWidget(self.results, 1)
        self.btn_results = QPushButton("Change…")
        self.btn_results.setProperty("kind", "ghost")
        self.btn_results.clicked.connect(self.change_results_folder)
        where.addWidget(self.btn_results)
        self.btn_results_beside = QPushButton("Beside each file")
        self.btn_results_beside.setProperty("kind", "ghost")
        self.btn_results_beside.setToolTip(
            "Put the results back beside each video instead of in one folder."
        )
        self.btn_results_beside.clicked.connect(self.beside_each_file)
        where.addWidget(self.btn_results_beside)
        layout.addLayout(where)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.btn_browse = QPushButton("Browse…")
        self.btn_browse.setProperty("kind", "ghost")
        self.btn_browse.clicked.connect(self.browse)
        self.btn_remove = QPushButton("Remove")
        self.btn_remove.setProperty("kind", "ghost")
        self.btn_remove.setToolTip("Take the selected file out of the list. A double-click does it too.")
        self.btn_remove.clicked.connect(self.remove_selected)
        self.btn_clear = QPushButton("Clear")
        self.btn_clear.setProperty("kind", "ghost")
        self.btn_clear.clicked.connect(self.clear)
        self.btn_run = QPushButton("Run")
        self.btn_run.setProperty("kind", "primary")
        self.btn_run.clicked.connect(self.run)
        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop)
        for button in (
            self.btn_browse,
            self.btn_remove,
            self.btn_clear,
            self.btn_run,
            self.btn_stop,
        ):
            actions.addWidget(button)
        actions.addStretch(1)
        self.status = QLabel("Drop videos here, or press Browse, then Run.")
        self.status.setProperty("role", "meta")
        actions.addWidget(self.status)
        layout.addLayout(actions)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFixedHeight(62)
        self.log.setPlaceholderText("Activity appears here.")
        layout.addWidget(self.log)
        return body

    # ------------------------------------------------------------- options
    def _load_options(self):
        """The saved download options, read only — the studio never writes them.

        The results folder is the exception: it is this section's own choice,
        and empty means the outputs stay beside the file they came from.
        """
        stored = make_settings()
        self.vertical.setChecked(_is_true(stored.value("vertical")))
        split = stored.value("split")
        self.split.setCurrentText(split if split in SPLIT_OPTIONS else DEFAULT_SPLIT)
        self.clips.setValue(_clip_count(stored.value("clips")))
        self._show_clip_count(self.split.currentText())
        folder = str(stored.value(RESULTS_KEY, "") or "").strip()
        self.results.setText(folder)
        self._show_results_reset(folder)

    def _show_clip_count(self, choice: str):
        """The clip count only means something in the N clips mode."""
        counting = choice == SPLIT_CLIPS
        self.clips_label.setVisible(counting)
        self.clips.setVisible(counting)

    def _show_results_reset(self, choice=""):
        """The way back is only worth a button once there is something to undo."""
        self.btn_results_beside.setVisible(bool(str(choice).strip()))

    # -------------------------------------------------------- results folder
    def change_results_folder(self):
        """The app's own folder picker, for the reason Browse uses one.

        The native dialog is a separate top-level window: on a packaged build
        it can open where the app cannot see it.
        """
        start = self.results.text().strip() or default_output_dir()
        picked = QFileDialog.getExistingDirectory(
            self,
            "Choose where the results go",
            start,
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if picked:
            self._set_results_folder(picked)

    def beside_each_file(self):
        self._set_results_folder("")

    def _set_results_folder(self, folder: str):
        """The choice, shown and remembered where it was made."""
        self.results.setText(folder)
        stored = make_settings()
        if folder:
            stored.setValue(RESULTS_KEY, folder)
        else:
            stored.remove(RESULTS_KEY)
        self._say(
            f"Results go to {folder}." if folder else "Results stay beside each file."
        )

    # ----------------------------------------------------------- files in
    def add_paths(self, candidates):
        """Put every real video file in the list; name and skip the rest."""
        added = 0
        for path in candidates:
            if not is_video_file(path):
                self._log(f"Not a video file: {path}")
                continue
            # A drop spells a Windows path with forward slashes and the picker
            # spells it with backslashes; without this the same file lands in
            # the list twice.
            path = os.path.normpath(path)
            if path in self.paths:
                continue
            self.paths.append(path)
            item = QListWidgetItem(os.path.basename(path))
            item.setToolTip(path)
            self.files.addItem(item)
            added += 1
        if added:
            self._say(f"{len(self.paths)} file{'s' if len(self.paths) != 1 else ''} ready.")
        return added

    def browse(self):
        """The app's own picker, in this window.

        The native Windows one is a separate top-level window, and on a
        packaged build it can open behind the app - a Browse that shows
        nothing is not a Browse.
        """
        start = os.path.dirname(self.paths[-1]) if self.paths else default_output_dir()
        picked, _ = QFileDialog.getOpenFileNames(
            self,
            "Choose videos to reframe",
            start,
            PICKER,
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        self.add_paths(picked)

    def remove_selected(self):
        self._remove_row(self.files.currentItem())

    def _remove_row(self, item):
        if item is None or self.is_running():
            return
        row = self.files.row(item)
        self.files.takeItem(row)
        del self.paths[row]
        self._say(f"{len(self.paths)} file{'s' if len(self.paths) != 1 else ''} ready.")

    def clear(self):
        if self.is_running():
            return
        self.paths.clear()
        self.files.clear()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self._say("List cleared.")

    # ------------------------------------------------------------- dropping
    def _urls(self, event):
        return [
            url.toLocalFile() if url.isLocalFile() else url.toString()
            for url in event.mimeData().urls()
        ]

    def dragEnterEvent(self, event: QDragEnterEvent):
        # Only while this section is the one on screen: a drop meant for the
        # queue must not be eaten here.
        if not self.isVisible() or not any(is_video_file(path) for path in self._urls(event)):
            event.ignore()
            return
        event.acceptProposedAction()

    def dragMoveEvent(self, event: QDragMoveEvent):
        if self.isVisible() and any(is_video_file(path) for path in self._urls(event)):
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event: QDropEvent):
        if not self.isVisible():
            event.ignore()
            return
        event.acceptProposedAction()
        self.add_paths(self._urls(event))

    # ------------------------------------------------------------------ run
    def run(self):
        if self.is_running():
            return
        if not self.paths:
            self._say("Drop videos here, or press Browse, then Run.")
            return
        folder = self.results.text().strip()
        if folder and not can_write_to(folder):
            self._say(f"Nothing could be written to {folder}.", error=True)
            return
        self._total = len(self.paths)
        self._index = 0
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self._set_running(True)
        self._log(
            f"Running {len(self.paths)} file{'s' if len(self.paths) != 1 else ''}: "
            f"{'vertical 9:16' if self.vertical.isChecked() else 'no vertical'}"
            f" · shorts {self.split.currentText()}"
        )
        self._thread = LocalVideoThread(
            list(self.paths),
            vertical=self.vertical.isChecked(),
            split=self.split.currentText(),
            clips=self.clips.value(),
            out_dir=folder,
        )
        self._thread.file_started.connect(self._on_file_started)
        self._thread.progress.connect(self._on_progress)
        self._thread.log.connect(self._log)
        self._thread.finished_all.connect(self._on_finished)
        self._thread.start()

    def stop(self):
        if self._thread is not None and self._thread.isRunning():
            self._thread.stop()
            self._say("Stopping after the file in hand…")

    def is_running(self):
        return self._thread is not None and self._thread.isRunning()

    def _set_running(self, running):
        self.btn_run.setEnabled(not running)
        self.btn_stop.setEnabled(running)
        self.btn_browse.setEnabled(not running)
        self.btn_remove.setEnabled(not running)
        self.btn_clear.setEnabled(not running)
        self.vertical.setEnabled(not running)
        self.split.setEnabled(not running)
        self.clips.setEnabled(not running)
        self.results.setEnabled(not running)
        self.btn_results.setEnabled(not running)
        self.btn_results_beside.setEnabled(not running)

    def _on_file_started(self, index, path):
        self._current = os.path.basename(path)
        self._index = index
        self.progress.setValue(0)
        self._working()

    def _on_progress(self, percent, stage):
        self.progress.setValue(int(percent))
        self._working(stage)

    def _working(self, stage=""):
        """The file in hand, which one of the list it is, and the pass on it."""
        where = f" ({self._index + 1} of {self._total})" if self._total > 1 else ""
        self._say(f"Working: {self._current}{where}" + (f" · {stage}" if stage else ""))

    def _on_finished(self):
        self._thread = None
        self._current = ""
        self._total = 0
        self._set_running(False)
        self._say("Done. The versions are beside each file.")

    # ------------------------------------------------------------ feedback
    def _say(self, text, error=False):
        self.status.setText(text)
        self.status.setStyleSheet(f"color: {C['failed']};" if error else "")

    def _log(self, text):
        if text:
            self.log.appendPlainText(str(text))
