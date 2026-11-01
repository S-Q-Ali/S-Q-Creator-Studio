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
