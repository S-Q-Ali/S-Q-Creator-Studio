"""Shared fixtures. Offscreen Qt platform so GUI tests run headless."""

import os
import sys
import tempfile
import time
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

#: The font folders and the files each OS keeps its interface faces in. The
#: offscreen platform starts with no font database at all, so the tests load
#: the machine's own — the same files the app renders with. A name that is
#: not on this machine is skipped: a missing font is measured the way the
#: user's machine would measure it.
FONT_SOURCES: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "win32": (
        (os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"),),
        (
            "segoeui.ttf",
            "segoeuib.ttf",
            "segoeuii.ttf",
            "seguisb.ttf",
            "seguisym.ttf",
            "consola.ttf",
            "seguiemj.ttf",
        ),
    ),
    "darwin": (
        (
            "/System/Library/Fonts",
            "/System/Library/Fonts/Supplemental",
            "/Library/Fonts",
            os.path.expanduser("~/Library/Fonts"),
        ),
        ("Helvetica.ttc", "Arial.ttf", "Menlo.ttc", "DejaVuSans.ttf"),
    ),
    "linux": (
        (
            "/usr/share/fonts",
            "/usr/local/share/fonts",
            os.path.expanduser("~/.local/share/fonts"),
            os.path.expanduser("~/.fonts"),
        ),
        (
            "DejaVuSans.ttf",
            "DejaVuSansMono.ttf",
            "LiberationSans-Regular.ttf",
            "LiberationMono-Regular.ttf",
            "NotoSans-Regular.ttf",
            "Ubuntu-R.ttf",
        ),
    ),
}

FONT_SUFFIXES = (".ttf", ".otf", ".ttc")


def system_font_files(platform: str | None = None) -> list[Path]:
    """The font files of this OS that the interface asks for, in order."""
    dirs, names = FONT_SOURCES.get(platform or sys.platform, ((), ()))
    index: dict[str, Path] = {}
    for folder in dirs:
        root = Path(folder)
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if path.suffix.lower() in FONT_SUFFIXES:
                index.setdefault(path.name.lower(), path)
    return [index[name.lower()] for name in names if name.lower() in index]


@pytest.fixture(autouse=True)
def _delete_the_leftovers(qapp):
    """Delete the widgets a test left behind, while they are still whole.

    A widget that is deleted with ``deleteLater`` has its C++ object gone
    before its Python wrapper is collected. The wrapper then frees it a
    second time, and the heap is corrupted - the run ends with every test
    passed, a failure code and no summary.

    Deleting them here, while the wrappers are still alive, keeps the two
    in step.
    """
    yield
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        return
    for widget in app.topLevelWidgets():
        widget.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()


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


def _stop_running_qthreads(timeout_ms: int = 2000) -> list:
    """Ask every running worker to stop; return the ones that would not.

    A worker that outlives its test is a real problem: the monkeypatch that
    kept it away from the network is undone when the test ends, so the
    worker carries on with the real code — a discovery scan reaching
    YouTube from a background thread. That is also what used to crash the
    suite: PySide6 aborts the process when a running QThread is destroyed
    at exit, and a network worker crashing in a native library takes the
    whole run with it.

    The app's own threads stop on a flag they check between jobs and inside
    every wait, so ``stop()`` ends them in a fraction of a second; Qt's
    interruption is asked for as well, for a thread that has no flag. What
    is deliberately *not* done here is ``terminate()``: it is unsupported
    off Windows, and where it does work it kills the thread mid-call with
    a lock possibly held. A thread that will not stop is reported instead.
    """
    stuck = []
    for thread in _running_qthreads():
        try:
            stop = getattr(thread, "stop", None)
            if callable(stop):
                stop()
            thread.requestInterruption()
        except RuntimeError:
            continue  # the C++ object is already gone
        if not thread.wait(timeout_ms):
            stuck.append(thread)
    return stuck


def _describe(threads: list) -> str:
    return ", ".join(sorted({type(thread).__name__ for thread in threads}))


@pytest.fixture(autouse=True)
def _stop_workers_after_each_test():
    """No worker outlives the test that started it."""
    yield
    stuck = _stop_running_qthreads()
    if stuck:
        pytest.fail(
            f"{len(stuck)} worker thread(s) survived the test and ignored the "
            f"stop request ({_describe(stuck)}). A test that starts a worker "
            "has to stop it; leaving one running means it keeps working with "
            "the real code after its patches are undone."
        )


@pytest.fixture(scope="session", autouse=True)
def _app_data_for_the_run():
    """One app-data folder for the whole run, nowhere near the real home.

    Every path the app writes - the queue, the downloads, the settings
    database, the browser profile, the log - comes out of
    ``engine.app_storage_dir()``, which reads ``LOCALAPPDATA`` and off Windows
    falls back to the OS data location under the home directory. A GUI test
    that opens the window would otherwise create all of that in the
    developer's own folders.

    Session-scoped: ``isolated_appdata`` still hands a test a clean folder
    when it wants one, and the plain environment stays untouched outside the
    run.
    """
    folder = tempfile.mkdtemp(prefix="sqali_appdata_")
    old = os.environ.get("LOCALAPPDATA")
    os.environ["LOCALAPPDATA"] = folder
    yield
    if old is None:
        os.environ.pop("LOCALAPPDATA", None)
    else:
        os.environ["LOCALAPPDATA"] = old


@pytest.fixture(scope="session", autouse=True)
def _isolated_settings(qapp):
    """Keep the tests out of the user's own settings.

    On Windows the preferences live in the registry. Every test that opened
    the window and closed it again wrote the test's own paths over the
    user's real preferences - the download folder included. The app reads
    ``SQ_SETTINGS_FILE`` and points its preferences at a file in a
    temporary folder instead.

    The folder is made with ``mkdtemp`` and not with pytest's own factory:
    pytest removes its folders when the session ends, and a settings file
    that is flushed after its folder is gone takes the process down with
    it.
    """
    folder = tempfile.mkdtemp(prefix="sqali_settings_")
    os.environ["SQ_SETTINGS_FILE"] = os.path.join(folder, "settings.ini")


@pytest.fixture(scope="function", autouse=True)
def _isolated_secret_store(tmp_path):
    """Keep the tests out of the user's own secret store.

    The API keys live in a SQLite file under LOCALAPPDATA. A test that read
    the user's real Gemini key would spend their quota and a test that
    wrote one would overwrite it, so every test gets its own empty store.
    """
    from s_q_ali_media_downloader.core import settings_store

    settings_store.configure(str(tmp_path / "niche_research.db"))
    yield


@pytest.fixture(scope="session", autouse=True)
def _real_fonts(qapp):
    """Give the offscreen platform a font database.

    The offscreen plugin has none of its own: every label renders as a box
    and, worse, its metrics are wrong - a label measured 30% wider than it
    really is, so the layout tests reported clipping that was not there and
    missed clipping that was. The system's own fonts are loaded instead, so
    the interface is measured with the type it is actually drawn in.

    On Linux and macOS Qt already reads the fonts through the platform, so
    there is usually nothing to add. On a machine that has none of these
    files the fixture loads nothing and says so, rather than measuring
    against a font the user will never see.

    The fonts are handed back before the application is torn down. An
    application font that is still registered when the font database is
    destroyed takes the process down with it on the way out.
    """
    from PySide6.QtGui import QFontDatabase

    if QFontDatabase.families():
        yield
        return

    loaded = 0
    for path in system_font_files():
        if QFontDatabase.addApplicationFont(str(path)) >= 0:
            loaded += 1
    if not loaded:
        print(
            f"conftest: no interface fonts found for {sys.platform}; "
            "label widths are Qt's fallback metrics, not the user's"
        )

    yield


@pytest.fixture(scope="session", autouse=True)
def _no_worker_left_running(qapp):
    """Leave no worker thread alive when the interpreter shuts down.

    The ``qapp`` argument is deliberate: this fixture has to be torn down
    *before* the QApplication is destroyed, and a fixture is finalized in
    the reverse order of its setup. Requesting ``qapp`` here puts this
    cleanup in front of it.

    A worker that is still running here got past the per-test cleanup, so it
    is reported: killing it with ``terminate()`` is not on the table - it is
    unsupported off Windows and, where it runs, it stops the thread mid-call
    with a lock possibly held.
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
    stuck = _running_qthreads()
    if stuck:
        pytest.fail(
            f"{len(stuck)} worker thread(s) were still running when the session "
            f"ended ({_describe(stuck)}). PySide6 aborts the process for a QThread "
            "destroyed while running, so this is the last chance to name the test "
            "that left it alive."
        )


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
