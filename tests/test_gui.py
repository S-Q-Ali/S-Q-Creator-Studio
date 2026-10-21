"""Offscreen GUI smoke tests against the real main window."""

import os

from PySide6.QtWidgets import QLabel, QPushButton

from s_q_ali_media_downloader import __version__
from s_q_ali_media_downloader.ui.main_window import MainWindow, resource
from s_q_ali_media_downloader.ui.widgets import Job


def test_main_window_smoke(qapp, isolated_appdata):
    window = MainWindow()
    title = window.windowTitle()
    assert "S-Q Creator Studio" in title
    assert __version__ in title

    labels = [label.text() for label in window.findChildren(QLabel)]
    assert "S-Q-Ali" in labels
    assert "CREATOR STUDIO" in labels

    buttons = [button.text() for button in window.findChildren(QPushButton)]
    assert any("GitHub" in text for text in buttons)
    assert any("LinkedIn" in text for text in buttons)

    assert os.path.isfile(resource("icon.ico"))
    window.close()


def test_queue_add_and_remove(qapp, isolated_appdata):
    window = MainWindow()
    job = Job("https://www.tiktok.com/@user/video/123")
    window._add_job(job)
    assert len(window.jobs) == 1
    assert window.cards[job.uid] is not None
    window._remove_jobs(lambda j: True)
    assert len(window.jobs) == 0
    window.close()


def test_add_links_classifies(qapp, isolated_appdata):
    window = MainWindow()
    window.links.setPlainText(
        "https://www.tiktok.com/@user/video/123\n"
        "https://www.youtube.com/watch?v=abc\n"
        "https://example.com/not-media\n"
    )
    window.add_links()
    assert len(window.jobs) == 2
    status = window.status_bar.text()
    assert "Added 2 links" in status
    assert "skipped" in status
    window.close()


def test_add_links_routes_tiktok_profile_to_expand_queue(qapp, isolated_appdata):
    window = MainWindow()
    window._start_next_expand = lambda: None  # don't spawn a real network thread
    window.links.setPlainText(
        "https://www.tiktok.com/@creator\n"
        "https://www.tiktok.com/@owner/video/123\n"
    )
    window.add_links()
    assert window._expand_queue and window._expand_queue[0] == "https://www.tiktok.com/@creator"
    assert len(window.jobs) == 1
    status = window.status_bar.text()
    assert "Expanding" in status
    assert "skipped" not in status
    window.close()


def test_expand_thread_for_picks_account_thread_for_tiktok_profile(qapp, isolated_appdata):
    from s_q_ali_media_downloader.engine import AccountFetchThread, YouTubeFetchThread

    window = MainWindow()
    account = window._expand_thread_for("https://www.tiktok.com/@creator")
    assert isinstance(account, AccountFetchThread)
    playlist = window._expand_thread_for("https://www.youtube.com/playlist?list=abc")
    assert isinstance(playlist, YouTubeFetchThread)
    window.close()


def test_rail_toggle_button(qapp, isolated_appdata):
    window = MainWindow()
    window.show()
    qapp.processEvents()
    assert window.rail.isVisible()
    window.btn_toggle_rail.click()
    qapp.processEvents()
    assert not window.rail.isVisible()
    window.btn_toggle_rail.click()
    qapp.processEvents()
    assert window.rail.isVisible()
    window.close()


# --------------------------------------------------------------------------- #
# Regression (2026-10): the Agent tab's queue button must work
# --------------------------------------------------------------------------- #
def test_agent_urls_reach_the_download_queue(qapp, isolated_appdata):
    """The Agent tab calls _handle_agent_urls, which used a method that did
    not exist — every "Queue" click raised AttributeError."""
    window = MainWindow()
    window._handle_agent_urls(["https://www.youtube.com/watch?v=dQw4w9WgXcQ"])
    assert len(window.jobs) == 1
    assert window.jobs[0].url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    window.close()

