"""Offscreen GUI smoke tests against the real main window."""

import os

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMessageBox,
    QPushButton,
    QWidget,
)

from s_q_ali_media_downloader import __version__
from s_q_ali_media_downloader.theme import STYLESHEET, C
from s_q_ali_media_downloader.ui.main_window import MainWindow, resource
from s_q_ali_media_downloader.ui.widgets import Job, wordmark_pixmap


def test_main_window_smoke(qapp, isolated_appdata):
    window = MainWindow()
    title = window.windowTitle()
    assert "S-Q Creator Studio" in title
    assert __version__ in title

    labels = [label.text() for label in window.findChildren(QLabel)]
    assert "CREATOR STUDIO" in labels

    mark = window.findChild(QLabel, "Wordmark")
    assert mark.pixmap() is not None and not mark.pixmap().isNull()
    assert mark.accessibleName() == "S-Q-Ali", "a drawn name still needs a readable one"

    buttons = [button.text() for button in window.findChildren(QPushButton)]
    assert any("GitHub" in text for text in buttons)
    assert any("LinkedIn" in text for text in buttons)

    assert os.path.isfile(resource("icon.ico"))
    window.close()


def test_a_failed_job_keeps_the_error_out_of_the_size(qapp, isolated_appdata):
    """The engine emits (uid, status, size, error). The window used to read
    the last two the other way round, so the error became the size."""
    window = MainWindow()
    job = Job("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    window._add_job(job)

    window.on_result(job.uid, "Failed", "—", "HTTP 404")

    assert job.error == "HTTP 404"
    assert job.size != "HTTP 404"
    window.close()


def _mean_lightness(widget):
    """Average grey of what the widget actually paints, 0-255."""
    image = widget.grab().toImage()
    total = 0
    samples = 0
    for y in range(image.height()):
        for x in range(image.width()):
            rgb = image.pixelColor(x, y).getRgb()[:3]
            total += sum(rgb) / 3
            samples += 1
    return total / max(samples, 1)


def test_failed_and_completed_are_told_apart_without_colour(qapp, isolated_appdata):
    """A black-and-white screenshot of the queue still separates the two.

    The palette has no red, so a failure cannot be warm. It is instead the
    one inverted chip in the app: void text on a chalk fill, which reads
    bright against every other status in the list.
    """
    window = MainWindow()
    window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    window.setStyleSheet(STYLESHEET)
    window.resize(1440, 900)
    window.show()
    qapp.processEvents()

    failed = Job("https://www.tiktok.com/@creator/video/1234567890")
    done = Job("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    window._add_job(failed)
    window._add_job(done)
    window.on_result(failed.uid, "Failed", "—", "HTTP 403")
    window.on_result(done.uid, "Completed", "12 MB", "")

    chip = window.cards[failed.uid].status
    calm = window.cards[done.uid].status

    assert f"color: {C['bg']}" in chip.styleSheet()
    assert "background" not in calm.styleSheet()
    assert _mean_lightness(chip) - _mean_lightness(calm) > 60

    window.close()


def test_a_finished_bar_is_chalk_not_blue(qapp, isolated_appdata):
    """Blue means moving, chalk means finished.

    The bar is the widest thing in a row, and a full blue one under
    COMPLETED read as a download still running even though every label in
    the row said it had stopped.
    """
    window = MainWindow()
    done = Job("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    running = Job("https://www.tiktok.com/@creator/video/1234567890")
    window._add_job(done)
    window._add_job(running)
    window.on_result(done.uid, "Completed", "12 MB", "")
    window.on_started(running.uid, None)
    window.on_progress(running.uid, 42.0, "7.7 MB", "1.2 MB/s")

    assert C["done"] in window.cards[done.uid].bar.styleSheet()
    assert "chunk" not in window.cards[running.uid].bar.styleSheet()

    window.close()


def test_close_with_no_workers_accepts(qapp, isolated_appdata):
    window = MainWindow()
    event = QCloseEvent()

    window.closeEvent(event)

    assert event.isAccepted()


def test_close_waits_for_a_running_worker_without_blocking(
    qapp, isolated_appdata, monkeypatch
):
    window = MainWindow()

    class FakeThread:
        stopped = False

        def isRunning(self):
            return True

        def stop(self):
            self.stopped = True

    thread = FakeThread()
    window.thread = thread
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)

    event = QCloseEvent()
    window.closeEvent(event)

    assert thread.stopped
    assert window._close_pending
    assert not event.isAccepted()
    assert not window.isVisible()

    thread.isRunning = lambda: False
    window._finish_deferred_close()

    assert not window._close_pending
    assert not window.isVisible()


def test_close_can_be_cancelled(qapp, isolated_appdata, monkeypatch):
    window = MainWindow()

    class FakeThread:
        def isRunning(self):
            return True

        def stop(self):
            raise AssertionError("a cancelled close must not stop the worker")

    window.thread = FakeThread()
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.No)

    event = QCloseEvent()
    window.closeEvent(event)

    assert not event.isAccepted()
    assert not window._close_pending
    window.thread = None
    window.close()


def test_finish_deferred_close_quits_the_app(qapp, isolated_appdata, monkeypatch):
    window = MainWindow()
    calls = []
    monkeypatch.setattr(QApplication, "quit", lambda *a, **k: calls.append(True))
    window._close_pending = True

    window._finish_deferred_close()

    assert calls == [True]
    assert not window._close_pending


def test_a_pending_close_does_not_start_new_work(qapp, isolated_appdata):
    window = MainWindow()
    window._close_pending = True
    window._expand_queue = ["https://www.tiktok.com/@creator"]

    window._start_next_expand()

    assert window.expander is None


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


def test_add_links_accepts_facebook_and_instagram(qapp, isolated_appdata):
    window = MainWindow()
    window._start_next_expand = lambda: None  # don't spawn a real network thread
    window.links.setPlainText(
        "https://www.facebook.com/reel/1234567890\n"
        "https://www.instagram.com/reel/Cabc123/\n"
        "https://www.facebook.com/MrBeast\n"
    )
    window.add_links()

    urls = {job.url for job in window.jobs}
    assert urls == {
        "https://www.facebook.com/reel/1234567890",
        "https://www.instagram.com/reel/Cabc123/",
    }
    status = window.status_bar.text()
    assert "Added 2 links" in status
    # A page is expanded, not queued as a single download.
    assert window._expand_queue == ["https://www.facebook.com/MrBeast"]
    assert "Expanding 1" in status
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



# --------------------------------------------------------------------------- #
# Keyboard focus
# --------------------------------------------------------------------------- #
def _differing_pixels(before, after):
    return sum(
        1
        for y in range(min(before.height(), after.height()))
        for x in range(min(before.width(), after.width()))
        if before.pixelColor(x, y) != after.pixelColor(x, y)
    )


def test_keyboard_focus_paints_on_every_control_kind(qapp, isolated_appdata):
    """A ``:focus`` rule is a claim; the pixels are the proof.

    Qt settles a tie between two rules of equal specificity by taking the one
    that comes last, so a stylesheet can declare a ring for every control and
    paint none of them - which is what the workspace tabs and the checked
    checkbox did. Each kind here is focused for real and compared against its
    own calm pixels.
    """
    window = MainWindow()
    window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    window.setStyleSheet(STYLESHEET)
    window.resize(1440, 900)
    window.show()
    # An offscreen window is never activated by the desktop, and Qt only
    # hands out focus inside an active window: without this every control
    # reports hasFocus() False and the test proves nothing. The modern
    # equivalents - activateWindow() and windowHandle().requestActivate() -
    # are both no-ops on the offscreen platform.
    qapp.setActiveWindow(window)
    qapp.processEvents()

    buttons = window.findChildren(QPushButton)
    controls = {
        "primary": window.btn_start,
        "plain": next(b for b in buttons if b.property("kind") is None and b.isEnabled()),
        "workspace tab": window.btn_nav_queue,
        "ghost": next(b for b in buttons if b.property("kind") == "ghost"),
        "danger": next(b for b in buttons if b.property("kind") == "danger"),
        "the log": window.links,
        "a checked box": window.chk_shorts,
    }

    blind = []
    for name, control in controls.items():
        calm = control.grab().toImage()
        control.setFocus()
        qapp.processEvents()
        if _differing_pixels(calm, control.grab().toImage()) < 20:
            blind.append(name)
        control.clearFocus()
        qapp.processEvents()

    assert not blind, f"focus paints nothing on: {blind}"
    window.close()


# --------------------------------------------------------------------------- #
# The drawn wordmark
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("compact", (False, True))
def test_the_wordmark_is_drawn_and_fits_its_rail(qapp, isolated_appdata, compact):
    """The rail's name is a pixmap, so the layout cannot clip it.

    A QLabel typeset at 19px trusts a font that is not on every machine the
    app runs on; the drawn name is measured once, at the size the rail can
    actually give it, and the stripe and the margins are already spent.
    """
    window = MainWindow()
    window.settings_page.compact_check.setChecked(compact)
    window._apply_density()
    qapp.processEvents()

    rail = window.findChild(QWidget, "Rail")
    mark = window.findChild(QLabel, "Wordmark")
    available = rail.width() - 22 - 22 - 4 - 12  # margins, stripe, head spacing

    pm = mark.pixmap()
    assert pm is not None and not pm.isNull()
    ratio = pm.devicePixelRatio()
    assert pm.width() / ratio <= available
    assert pm.height() / ratio <= 40  # the height the stripe already sets
    window.close()


def test_the_wordmark_redraws_when_the_density_changes(qapp, isolated_appdata):
    """The title size is a density token, so the drawing has to follow it."""
    window = MainWindow()

    def painted_height() -> float:
        pm = window.wordmark.pixmap()
        return pm.height() / pm.devicePixelRatio()

    window.settings_page.compact_check.setChecked(True)
    window._apply_density()
    compact = painted_height()
    window.settings_page.compact_check.setChecked(False)
    window._apply_density()
    comfortable = painted_height()

    assert comfortable > compact
    window.close()


def test_the_wordmark_is_painted_once_and_reused(qapp):
    """A resize must not repaint the logotype: the pixmap is cached per size."""
    assert wordmark_pixmap(28) is wordmark_pixmap(28)
    assert wordmark_pixmap(28) is not wordmark_pixmap(17)
