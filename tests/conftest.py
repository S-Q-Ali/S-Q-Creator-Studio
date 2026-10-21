"""Shared fixtures. Offscreen Qt platform so GUI tests run headless."""

import os
import tempfile
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _running_qthreads() -> list:
    """The QThread objects that are still running.

    A running QThread does not show up in ``threading.enumerate()``
    (shiboken runs it outside the Python threading registry), so the live
    QThread objects are found through the garbage collector instead.
    """
    import gc

    from PySide6.QtCore import QThread

    found = []
    for obj in gc.get_objects():
        if isinstance(obj, QThread):
            try:
                if obj.isRunning():
                    found.append(obj)
            except RuntimeError:
                pass  # the C++ object is already gone
    return found


def _stop_running_qthreads(timeout_ms: int = 2000) -> None:
    """Stop every worker thread that is still running.

    A worker that outlives its test is a real problem: the monkeypatch that
    kept it away from the network is undone when the test ends, so the
    worker carries on with the real code — a discovery scan reaching
    YouTube from a background thread. That is also what used to crash the
    suite: PySide6 aborts the process when a running QThread is destroyed
    at exit, and a network worker crashing in a native library takes the
    whole run with it.
    """
    for thread in _running_qthreads():
        try:
            thread.requestInterruption()
        except RuntimeError:
            continue
        if not thread.wait(timeout_ms):
            try:
                thread.terminate()
                thread.wait(1000)
            except RuntimeError:
                pass


@pytest.fixture(autouse=True)
def _stop_workers_after_each_test():
    """No worker outlives the test that started it."""
    yield
    _stop_running_qthreads()
    _stop_thumb_loader()


def _stop_thumb_loader() -> None:
    """Stop the thumbnail loader, if one was ever created.

    The loader fetches over HTTP in a daemon thread. A request that is still
    in flight when the interpreter tears the modules down crashes the
    process with a native access violation in the SSL layer.
    """
    from s_q_ali_media_downloader.niche_research.ui import widgets

    widgets.shutdown_thumb_loader(timeout=2.0)


@pytest.fixture(scope="session", autouse=True)
def _no_network():
    """The test suite must not touch the network.

    A real HTTPS request that is still in flight when the process exits
    crashes it in the SSL layer, and a test that depends on YouTube
    answering is a test that fails for reasons that have nothing to do with
    the code under test.
    """
    from s_q_ali_media_downloader.niche_research.ui import widgets

    original = widgets._fetch_image_bytes
    widgets._fetch_image_bytes = lambda url, timeout=8.0: None
    yield
    widgets._fetch_image_bytes = original


@pytest.fixture(scope="session", autouse=True)
def _no_worker_left_running(qapp):
    """Leave no worker thread alive when the interpreter shuts down.

    The ``qapp`` argument is deliberate: this fixture has to be torn down
    *before* the QApplication is destroyed, and a fixture is finalized in
    the reverse order of its setup. Requesting ``qapp`` here puts this
    cleanup in front of it.
    """
    yield
    from PySide6.QtWidgets import QApplication

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and _running_qthreads():
        _stop_running_qthreads(timeout_ms=500)
        app = QApplication.instance()
        if app is not None:
            app.processEvents()
        time.sleep(0.05)
    # The thumbnail loader fetches over HTTP in a daemon thread. A daemon
    # thread that is inside a socket read when the interpreter tears the
    # modules down crashes the process with a native access violation.
    _stop_thumb_loader()
    # The GUI tests delete their widgets with deleteLater(). Those deferred
    # deletions are only processed when the event loop runs, so a widget
    # whose C++ object is already gone can be destroyed twice when the
    # QApplication is torn down. Flush them while the application is still
    # alive.
    from PySide6.QtCore import QEvent

    app = QApplication.instance()
    if app is not None:
        app.processEvents()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
    # Whatever is still running after the grace period is stopped for good:
    # the process is about to exit, and a live thread would abort it.
    for thread in _running_qthreads():
        try:
            thread.terminate()
            thread.wait(1000)
        except RuntimeError:
            pass


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="function")
def isolated_appdata():
    old = os.environ.get("LOCALAPPDATA")
    os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="sqali_test_")
    yield
    if old is None:
        os.environ.pop("LOCALAPPDATA", None)
    else:
        os.environ["LOCALAPPDATA"] = old
