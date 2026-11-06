"""The Vertical Studio page: files in, options set, the passes run.

The worker is faked: nothing here decodes a video. What is proved is that
files get in by drop and by Browse, that junk gets refused with a sentence,
and that the page hands the list and its options to the worker.
"""

from __future__ import annotations

import os

import pytest
from PySide6.QtCore import QMimeData, QPoint, QSettings, Qt, QThread, QUrl, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QFileDialog

from s_q_ali_media_downloader.ui import vertical_studio_page as module
from s_q_ali_media_downloader.ui.vertical_studio_page import VerticalStudioPage


def _mime(local, links):
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(path) for path in local] + [QUrl(link) for link in links])
    return mime


def _event(cls, local, links):
    """A drag event holding its own mime data: Qt does not own it, so
    without the attribute below the object is collected and the event
    is left pointing at freed memory."""
    mime = _mime(local, links)
    event = cls(QPoint(10, 10), Qt.CopyAction, mime, Qt.NoButton, Qt.NoModifier)
    event.mime = mime
    return event


def _enter(page, local=(), links=()):
    event = _event(QDragEnterEvent, local, links)
    page.dragEnterEvent(event)
    return event


def _drop_on(page, local=(), links=()):
    event = _event(QDropEvent, local, links)
    page.dropEvent(event)
    return event


def _videos(tmp_path, *names):
    made = []
    for name in names:
        path = tmp_path / name
        path.write_bytes(b"x")
        made.append(str(path))
    return made


def _fake_worker(monkeypatch):
    """A worker that records the run and answers to the test's own signals."""
    seen = {"calls": [], "threads": []}

    class Thread(QThread):
        file_started = Signal(int, str)
        progress = Signal(float, str)
        log = Signal(str)
        finished_all = Signal()

        def __init__(self, files, **options):
            super().__init__()
            self.files = list(files)
            self.options = options
            self.running = False
            self.stopped = False
            seen["threads"].append(self)

        def start(self):
            seen["calls"].append((self.files, self.options))
            self.running = True

        def stop(self):
            self.stopped = True
            self.running = False

        def isRunning(self):
            return self.running

    monkeypatch.setattr(module, "LocalVideoThread", Thread)
    return seen


@pytest.fixture()
def page(qapp):
    widget = VerticalStudioPage()
    widget.show()
    yield widget
    widget.close()


def test_a_drop_of_video_files_lands_in_the_list(page, tmp_path):
    first, second = _videos(tmp_path, "one.mp4", "two.mkv")

    assert _enter(page, local=[first]).isAccepted()
    _drop_on(page, local=[first, second])

    assert page.paths == [first, second]
    assert page.files.item(0).text() == "one.mp4"
    assert page.files.item(1).toolTip() == second


def test_a_folder_or_a_link_in_the_drop_is_refused_with_a_sentence(page, tmp_path):
    video = _videos(tmp_path, "one.mp4")[0]
    folder = tmp_path / "edits"
    folder.mkdir()

    _drop_on(page, local=[video, str(folder)], links=["https://youtu.be/abc"])

    assert page.paths == [video]
    lines = page.log.toPlainText()
    # A drop spells the path Qt's way; the sentence names what was dropped.
    assert "edits" in lines and "Not a video file" in lines
    assert "https://youtu.be/abc" in lines


def test_a_drop_reaches_the_page_only_while_it_is_the_visible_one(page, tmp_path):
    video = _videos(tmp_path, "one.mp4")[0]

    page.hide()
    assert _enter(page, local=[video]).isAccepted() is False
    assert _drop_on(page, local=[video]).isAccepted() is False

    page.show()
    assert _enter(page, local=[video]).isAccepted()
    assert page.paths == []


def test_the_same_file_dropped_twice_is_listed_once(page, tmp_path):
    video = _videos(tmp_path, "one.mp4")[0]

    _drop_on(page, local=[video])
    _drop_on(page, local=[video])

    assert page.paths == [video]
    assert page.files.count() == 1


def test_browse_adds_what_the_picker_returns(page, tmp_path, monkeypatch):
    """The picker is the app's own widget rather than the native Windows
    window, which on a packaged build can open where the app cannot see it -
    a Browse that appears to do nothing."""
    video = _videos(tmp_path, "one.mp4")[0]
    asked = {}

    def picker(cls, *args, **kwargs):
        asked["args"] = args
        asked["kwargs"] = kwargs
        return [video], ""

    monkeypatch.setattr(QFileDialog, "getOpenFileNames", classmethod(picker))

    page.browse()

    assert page.paths == [video]
    assert asked["args"][1] == "Choose videos to reframe"
    assert asked["kwargs"]["options"] == QFileDialog.Option.DontUseNativeDialog


def test_browse_starts_where_the_last_file_came_from(page, tmp_path, monkeypatch):
    """The studio works on files from anywhere, so the picker opens at the
    folder of the last one in the list instead of somewhere the user has to
    find again."""
    asked = []
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileNames",
        classmethod(lambda cls, *args, **kwargs: asked.append(args) or ([], "")),
    )
    video = _videos(tmp_path, "one.mp4")[0]
    _drop_on(page, local=[video])

    page.browse()

    assert asked[0][2] == os.path.dirname(video)


def test_the_options_are_seeded_from_the_saved_settings(tmp_path, monkeypatch):
    store = str(tmp_path / "prefs.ini")
    monkeypatch.setenv("SQ_SETTINGS_FILE", store)
    saved = QSettings(store, QSettings.IniFormat)
    saved.setValue("vertical", "true")
    saved.setValue("split", "N clips")
    saved.setValue("clips", 9)
    saved.sync()

    page = VerticalStudioPage()
    page.show()

    assert page.vertical.isChecked() is True
    assert page.split.currentText() == "N clips"
    assert page.clips.value() == 9
    assert page.clips.isHidden() is False

    # The studio borrows the download defaults; it never overwrites them.
    page.vertical.setChecked(False)
    assert QSettings(store, QSettings.IniFormat).value("vertical") == "true"


def test_the_clip_count_shows_only_in_the_n_clips_mode(page):
    assert page.clips.isHidden()

    page.split.setCurrentText("N clips")
    assert page.clips.isHidden() is False

    page.split.setCurrentText("60 s")
    assert page.clips.isHidden()


def test_remove_and_a_double_click_take_an_entry_out(page, tmp_path):
    first, second = _videos(tmp_path, "one.mp4", "two.mp4")
    _drop_on(page, local=[first, second])

    page.files.setCurrentItem(page.files.item(0))
    page.remove_selected()
    assert page.paths == [second]

    page.files.itemDoubleClicked.emit(page.files.item(0))
    assert page.paths == []


def test_run_hands_the_list_and_the_options_to_the_worker(page, tmp_path, monkeypatch):
    seen = _fake_worker(monkeypatch)
    first, second = _videos(tmp_path, "one.mp4", "two.mp4")
    _drop_on(page, local=[first, second])
    page.vertical.setChecked(True)
    page.split.setCurrentText("N clips")
    page.clips.setValue(4)

    page.run()

    assert seen["calls"] == [
        (
            [first, second],
            {"vertical": True, "split": "N clips", "clips": 4, "out_dir": ""},
        )
    ]
    assert page.btn_run.isEnabled() is False
    assert page.btn_stop.isEnabled() is True


def test_run_needs_something_to_work_on(page, monkeypatch):
    seen = _fake_worker(monkeypatch)

    page.run()

    assert seen["calls"] == []
    assert "Drop" in page.status.text()


def test_the_worker_talks_and_the_page_shows_it(page, tmp_path, monkeypatch):
    seen = _fake_worker(monkeypatch)
    video = _videos(tmp_path, "one.mp4")[0]
    _drop_on(page, local=[video])

    page.run()
    thread = seen["threads"][0]
    thread.file_started.emit(0, video)
    thread.progress.emit(40.0, "finding the subject")
    thread.log.emit("The vertical version is beside it.")

    assert "one.mp4" in page.status.text()
    assert "finding the subject" in page.status.text()
    assert page.progress.value() == 40
    assert "The vertical version is beside it." in page.log.toPlainText()

    thread.finished_all.emit()
    assert page.btn_run.isEnabled() is True
    assert page.is_running() is False


def test_the_bar_is_the_file_in_hand_and_the_line_says_which(page, tmp_path, monkeypatch):
    """A ten-file list is ten separate jobs, and one of them can be an hour
    of film: the bar measures the file being worked on, and the line names it
    with its place in the list, so a run that has only reached the second
    file never looks like it has finished the tenth."""
    seen = _fake_worker(monkeypatch)
    first, second = _videos(tmp_path, "one.mp4", "two.mp4")
    _drop_on(page, local=[first, second])

    page.run()
    thread = seen["threads"][0]
    thread.file_started.emit(1, second)

    assert page.progress.maximum() == 100
    assert page.progress.value() == 0

    thread.progress.emit(37.5, "writing the vertical")

    assert page.progress.value() == 37
    assert page.status.text() == "Working: two.mp4 (2 of 2) · writing the vertical"


def test_stop_asks_the_worker_and_says_the_file_in_hand_finishes(page, tmp_path, monkeypatch):
    seen = _fake_worker(monkeypatch)
    _drop_on(page, local=_videos(tmp_path, "one.mp4"))

    page.run()
    page.stop()

    assert seen["threads"][0].stopped is True
    assert "Stopping" in page.status.text()


# ------------------------------------------------------------- results folder


@pytest.fixture()
def stored(tmp_path, monkeypatch):
    """A preferences file of the test's own, and the page built on it.

    The page writes the results folder the moment it is picked, so these
    tests may not touch the owner's real preferences.
    """
    store = str(tmp_path / "prefs.ini")
    monkeypatch.setenv("SQ_SETTINGS_FILE", store)
    return QSettings(store, QSettings.IniFormat)


def _picker(monkeypatch, reply):
    asked = {}

    def choose(cls, *args, **kwargs):
        asked["args"] = args
        asked["kwargs"] = kwargs
        return reply

    monkeypatch.setattr(QFileDialog, "getExistingDirectory", classmethod(choose))
    return asked


def test_an_empty_field_promises_the_files_own_folder(stored, qapp):
    page = VerticalStudioPage()
    page.show()

    assert page.results.text() == ""
    assert page.results.placeholderText() == "Beside each file"
    assert page.btn_results_beside.isHidden()


def test_a_saved_results_folder_is_back_where_it_was_left(tmp_path, monkeypatch):
    """The folder is chosen once and remembered, so a creator who works in
    one place does not point the app at it every session."""
    store = str(tmp_path / "prefs.ini")
    monkeypatch.setenv("SQ_SETTINGS_FILE", store)
    QSettings(store, QSettings.IniFormat).setValue("studio_output_dir", str(tmp_path / "results"))
    QSettings(store, QSettings.IniFormat).sync()

    page = VerticalStudioPage()
    page.show()

    assert page.results.text() == str(tmp_path / "results")
    assert page.btn_results_beside.isHidden() is False


def test_choosing_a_folder_shows_it_and_stores_it(page, tmp_path, monkeypatch, stored):
    folder = tmp_path / "results"
    folder.mkdir()
    asked = _picker(monkeypatch, str(folder))

    page.change_results_folder()

    assert page.results.text() == str(folder)
    assert stored.value("studio_output_dir") == str(folder)
    assert asked["args"][1] == "Choose where the results go"
    assert asked["kwargs"]["options"] == QFileDialog.Option.DontUseNativeDialog

    page.beside_each_file()

    assert page.results.text() == ""
    assert stored.value("studio_output_dir", "") == ""
    assert page.btn_results_beside.isHidden()


def test_canceling_the_folder_picker_leaves_the_choice_alone(
    page, tmp_path, monkeypatch, stored
):
    folder = tmp_path / "results"
    folder.mkdir()
    page.results.setText(str(folder))
    _picker(monkeypatch, "")

    page.change_results_folder()

    assert page.results.text() == str(folder)


def test_the_folder_reaches_the_worker_with_the_rest_of_the_options(
    page, tmp_path, monkeypatch
):
    seen = _fake_worker(monkeypatch)
    folder = tmp_path / "results"
    folder.mkdir()
    _drop_on(page, local=_videos(tmp_path, "one.mp4"))
    page.vertical.setChecked(True)
    page.split.setCurrentText("Off")
    page.clips.setValue(3)
    page.results.setText(str(folder))

    page.run()

    assert seen["calls"][0][1] == {
        "vertical": True,
        "split": "Off",
        "clips": 3,
        "out_dir": str(folder),
    }


def test_a_folder_that_cannot_hold_a_file_stops_the_run_before_it_starts(
    page, tmp_path, monkeypatch, stored
):
    """A path that is a file is not a folder, and a read-only share refuses a
    write: either way the owner is told before ffmpeg starts work that could
    never have landed anywhere."""
    seen = _fake_worker(monkeypatch)
    blocker = tmp_path / "blocker"
    blocker.write_text("not a folder")
    _drop_on(page, local=_videos(tmp_path, "one.mp4"))
    page.results.setText(str(blocker))

    page.run()

    assert seen["calls"] == []
    assert page.status.text() == f"Nothing could be written to {blocker}."
    assert blocker.is_file()


def test_the_results_row_is_locked_while_a_run_is_underway(
    page, tmp_path, monkeypatch
):
    seen = _fake_worker(monkeypatch)
    folder = tmp_path / "results"
    folder.mkdir()
    _drop_on(page, local=_videos(tmp_path, "one.mp4"))
    page.results.setText(str(folder))

    page.run()

    assert page.results.isEnabled() is False
    assert page.btn_results.isEnabled() is False

    seen["threads"][0].finished_all.emit()

    assert page.results.isEnabled() is True
