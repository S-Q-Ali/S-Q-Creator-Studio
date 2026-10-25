"""The queue file must survive anything that happens while it is written.

The queue is the user's work: the links they pasted and the state of every
download. It is written to disk on every change, so a crash in the middle
of a write must not be able to take it away.
"""

import json
import os

import pytest

from s_q_ali_media_downloader.ui.main_window import MainWindow, queue_file
from s_q_ali_media_downloader.ui.widgets import Job

A_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
B_URL = "https://www.tiktok.com/@someone/video/999"


def _read_queue() -> list[dict]:
    with open(queue_file(), "r", encoding="utf-8") as handle:
        return json.load(handle).get("items", [])


@pytest.fixture
def window(qapp, isolated_appdata):
    win = MainWindow()
    yield win
    win.close()


def test_a_failed_write_leaves_the_old_queue_readable(window, monkeypatch):
    """A write that dies halfway must not empty the file.

    The queue was written straight into the file it lives in, so a disk
    that filled up or a crash during the write left half a JSON behind and
    the next start found nothing.
    """
    window._add_job(Job(A_URL))
    window._save_queue()
    assert len(_read_queue()) == 1

    def full_disk(*args, **kwargs):
        raise OSError("no space left on device")

    monkeypatch.setattr(json, "dump", full_disk)
    window._save_queue()

    assert len(_read_queue()) == 1, "the queue was lost by a failed write"


def test_saving_keeps_a_link_another_window_added(window, qapp, isolated_appdata):
    """Two windows, one file: the second save must not erase the first.

    Nothing stops the app from being opened twice. The window that closes
    last writes the list it knows about, and the links the other window
    added in the meantime were gone with it.
    """
    window._add_job(Job(A_URL))
    window._save_queue()

    other = MainWindow()
    other._add_job(Job(B_URL))
    other._save_queue()
    other.close()

    urls = {item["url"] for item in _read_queue()}
    assert A_URL in urls, "the first window's link was erased"
    assert B_URL in urls


def test_a_link_removed_in_one_window_stays_removed(window, qapp, isolated_appdata):
    """Merging must not bring back a link the user deleted."""
    window._add_job(Job(A_URL))
    window._add_job(Job(B_URL))
    window._save_queue()

    other = MainWindow()
    other._remove_jobs(lambda job: job.url == A_URL)
    other._save_queue()
    other.close()

    urls = {item["url"] for item in _read_queue()}
    assert A_URL not in urls, "a removed link came back"
    assert B_URL in urls


def test_the_queue_file_is_replaced_not_rewritten(window):
    """The write goes to a temporary file and moves it into place.

    That is what makes the write atomic: a reader sees either the old
    queue or the new one, never half of one. The lock file is the one
    expected leftover; it is the handle writers serialize on.
    """
    window._add_job(Job(A_URL))
    window._save_queue()

    leftovers = [
        name
        for name in os.listdir(os.path.dirname(queue_file()))
        if name.startswith("queue.json")
        and name not in ("queue.json", "queue.json.lock")
    ]
    assert not leftovers, f"the temporary file was left behind: {leftovers}"


def test_a_save_writes_the_queue_instead_of_only_the_temp_file(window):
    """Regression: the live queue used to stay at 0 bytes on Windows.

    The old writer opened queue.json as its own lock, so the atomic replace
    was refused and the JSON stayed in queue.json.tmp.
    """
    window._add_job(Job(A_URL))
    window._save_queue()

    assert os.path.getsize(queue_file()) > 0, "queue.json was left empty"
    assert _read_queue()[0]["url"] == A_URL
