"""Shared fixtures. Offscreen Qt platform so GUI tests run headless."""

import os
import tempfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


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
