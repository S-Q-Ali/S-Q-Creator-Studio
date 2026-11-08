"""Offscreen smoke tests for the Music workspace."""

from PySide6.QtWidgets import QPushButton

from s_q_ali_media_downloader.core.music_source import MusicTrack
from s_q_ali_media_downloader.engine import DEFAULT_MUSIC_FORMAT, MUSIC_FORMATS
from s_q_ali_media_downloader.ui.main_window import MainWindow
from s_q_ali_media_downloader.ui.music_page import MusicPage


def test_page_offers_every_format(qapp):
    page = MusicPage()
    assert page.format.count() == len(MUSIC_FORMATS)
    assert page.format.currentText() == DEFAULT_MUSIC_FORMAT
    page.deleteLater()


def test_queue_row_tracks_the_download(qapp):
    page = MusicPage()
    page._add_track(
        MusicTrack(url="https://youtu.be/x", title="Song", artist="Artist", source="youtube")
    )
    assert page.table.rowCount() == 1

    page._on_started(1, "Artist — Song")
    assert page.table.item(0, 3).text() == "Downloading"

    page._on_progress(1, 55, "10 MB", "1 MB/s")
    assert page._bars[1].value() == 55

    page._on_result(1, "Done", "C:/Music/x.flac", "FLAC · 44.1 kHz · 16-bit")
    assert page.table.item(0, 3).text() == "Done"
    assert "FLAC" in page.table.item(0, 5).text()

    page._on_finished()
    assert page.btn_start.isEnabled()
    page.deleteLater()


def test_a_stopped_run_does_not_look_finished(qapp):
    page = MusicPage()
    for title in ("One", "Two"):
        page._add_track(MusicTrack(url=f"https://youtu.be/{title}", title=title, source="youtube"))
    page.overall.setRange(0, 2)

    page._on_started(1, "One")
    page._on_result(1, "Done", "C:/Music/one.flac", "FLAC")
    page._on_started(2, "Two")
    page._on_finished()

    assert page.table.item(1, 3).text() == "Stopped"
    assert page.overall.value() == 1
    assert page.status.text().startswith("Stopped")
    page.deleteLater()


def test_resolving_links_counts_as_running_for_close(qapp):
    page = MusicPage()

    class Busy:
        def isRunning(self):
            return True

    page._resolver = Busy()
    assert page.is_running()
    page.deleteLater()


def test_main_window_has_music_workspace(qapp, isolated_appdata):
    window = MainWindow()
    labels = [button.text() for button in window.findChildren(QPushButton)]
    assert any("Music" in text for text in labels)
    assert isinstance(window.music_page, MusicPage)
    assert window.workspace_stack.count() >= 4
    window.close()


def test_say_uses_role_property_instead_of_inline_stylesheet(qapp):
    page = MusicPage()
    page._say("Boom", error=True)
    assert page.status.property("role") == "error"
    assert page.status.styleSheet() == ""
    page._say("Ready")
    assert page.status.property("role") == "meta"
    assert page.status.styleSheet() == ""
    page.deleteLater()


def test_running_state_disables_browse_button(qapp):
    page = MusicPage()
    page._set_running(True)
    assert not page.btn_browse.isEnabled()
    page._set_running(False)
    assert page.btn_browse.isEnabled()
    page.deleteLater()


def test_browse_uses_non_native_dialog(qapp, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    from s_q_ali_media_downloader.ui import music_page as mp

    captured = {}

    def fake_dir(*args, **kwargs):
        captured.update(kwargs)
        return ""

    monkeypatch.setattr(mp.QFileDialog, "getExistingDirectory", fake_dir)
    page = MusicPage()
    page._browse()
    assert captured.get("options") == QFileDialog.Option.DontUseNativeDialog
    page.deleteLater()


def test_music_page_has_empty_state_alternating_rows_and_log_cap(qapp):
    page = MusicPage()
    assert hasattr(page, "empty_state")
    assert page.table_stack.currentWidget() is page.empty_state
    assert page.table.alternatingRowColors() is True
    assert page.table.showGrid() is False
    assert page.log.maximumBlockCount() == 500

    page._add_track(
        MusicTrack(url="https://youtu.be/x", title="Song", artist="Artist", source="youtube")
    )
    assert page.table_stack.currentWidget() is page.table

    page.clear()
    assert page.table_stack.currentWidget() is page.empty_state
    page.deleteLater()
