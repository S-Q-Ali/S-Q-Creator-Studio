"""Offscreen GUI smoke tests against the real main window."""

import os

from PySide6.QtWidgets import QLabel, QPushButton

from s_q_ali_media_downloader.ui.main_window import MainWindow, resource
from s_q_ali_media_downloader.ui.widgets import Job


def test_main_window_smoke(qapp, isolated_appdata):
    window = MainWindow()
    title = window.windowTitle()
    assert "S-Q-Ali Media Downloader" in title
    assert "2.0.0" in title

    labels = [label.text() for label in window.findChildren(QLabel)]
    assert "S-Q-Ali" in labels
    assert "MEDIA DOWNLOADER" in labels

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


def test_rail_auto_collapses_on_research(qapp, isolated_appdata):
    window = MainWindow()
    window.show()
    qapp.processEvents()
    assert window.rail.isVisible()
    window.btn_nav_research.click()
    qapp.processEvents()
    assert not window.rail.isVisible()
    window.btn_nav_queue.click()
    qapp.processEvents()
    assert window.rail.isVisible()
    window.research_tab.stop_poller()
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
