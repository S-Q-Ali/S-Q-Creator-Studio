"""The tests that keep the suite itself portable.

Not app tests: these guard the three things the whole run leans on when it
lands on an OS nobody has tried it on yet - where the interface fonts come
from, that a run writes nothing into the real home, and that a worker which
will not stop is reported instead of killed.
"""

import os
import tempfile
import time
from pathlib import Path

from conftest import FONT_SOURCES, _stop_running_qthreads, system_font_files
from PySide6.QtCore import QThread

from s_q_ali_media_downloader import engine


# --------------------------------------------------------------------------- #
# E1: per-OS font sourcing
# --------------------------------------------------------------------------- #
def test_the_named_fonts_are_found_underneath_the_os_font_folders(tmp_path, monkeypatch):
    wanted = tmp_path / "truetype" / "DejaVuSans.ttf"
    wanted.parent.mkdir(parents=True)
    wanted.write_bytes(b"font")
    (wanted.parent / "readme.woff").write_bytes(b"not a font")
    monkeypatch.setitem(
        FONT_SOURCES,
        "linux",
        ((str(tmp_path / "gone"), str(tmp_path)), ("DejaVuSans.ttf", "NotHere.ttf")),
    )

    # A folder that is not there is skipped, a font that is not there is left
    # out, and the one found in a subfolder is the one loaded.
    assert system_font_files("linux") == [wanted]


def test_an_os_with_no_font_folders_to_read_reports_none(tmp_path, monkeypatch):
    monkeypatch.setitem(FONT_SOURCES, "linux", ((str(tmp_path / "gone"),), ("DejaVuSans.ttf",)))

    assert system_font_files("linux") == []


def test_every_os_the_suite_can_run_on_has_a_font_source():
    """An OS with no entry loses the real metrics without saying so."""
    assert {"win32", "darwin", "linux"} <= set(FONT_SOURCES)


# --------------------------------------------------------------------------- #
# E3: the run's app data lives in a temporary folder
# --------------------------------------------------------------------------- #
def test_a_run_resolves_its_app_folder_inside_the_temporary_appdata():
    """The acceptance for the app-data fixture: nothing lands in the home.

    Every path the app writes comes out of ``app_storage_dir()``, so the test
    is that it resolves inside the folder the session set up - the developer's
    own ``%LOCALAPPDATA%`` included none of it.
    """
    appdata = os.environ["LOCALAPPDATA"]
    storage = engine.app_storage_dir()

    assert appdata.startswith(str(Path(tempfile.gettempdir()) / "sqali_appdata_"))
    assert storage.startswith(appdata + os.sep)


# --------------------------------------------------------------------------- #
# E2: a worker that will not stop is reported, never killed
# --------------------------------------------------------------------------- #
class _Worker(QThread):
    """A thread like the app's own: it ends when its flag is set."""

    def __init__(self, seconds=30.0):
        super().__init__()
        self._stop = False
        self._seconds = seconds

    def run(self):
        ends = time.monotonic() + self._seconds
        while not self._stop and time.monotonic() < ends:
            time.sleep(0.01)

    def stop(self):
        self._stop = True


class _StubbornWorker(_Worker):
    def stop(self):
        pass  # ignores the request, like a test that forgot to write one


def _start(thread):
    """Run the thread and wait until it is actually up.

    The caller keeps the reference: a QThread wrapper that goes away while
    its thread is still running takes the whole process with it, and the run
    ends with no summary and a failure code.
    """
    thread.start()
    deadline = time.monotonic() + 2
    while not thread.isRunning() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert thread.isRunning(), "the worker never came up"
    return thread


def test_a_worker_that_cooperates_is_stopped_and_not_reported():
    worker = _start(_Worker(seconds=30.0))

    try:
        assert _stop_running_qthreads(timeout_ms=2000) == []
        assert not worker.isRunning()
    finally:
        worker.wait(5000)


def test_a_worker_that_ignores_the_stop_request_is_reported():
    worker = _start(_StubbornWorker(seconds=0.5))

    try:
        reported = _stop_running_qthreads(timeout_ms=10)
        # Reported, not killed: the helper has no terminate() left to call.
        assert [type(thread).__name__ for thread in reported] == ["_StubbornWorker"]
    finally:
        assert worker.wait(5000), "the worker has to end before the test does"
