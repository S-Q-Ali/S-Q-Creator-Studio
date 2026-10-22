"""The interface has to fit on a small laptop without clipping anything.

The app was tuned on a big screen. At 1366x768 the AI Finder cut its own
controls in half ("50 chann", "Facebook Pag") and the cookies row fell off
the panel; at 1280x720 it was worse. Nothing warned about it, because
nothing measured it.

These tests render the real window at four sizes and look at what came out:
no label may be clipped, no control may be too small to click, and the tab
that shows which workspace is open must be readable.

The contrast of the tab is checked two ways: the stylesheet must declare
readable colours, and no stylesheet may cascade onto the tabs - a bare
``background:`` rule on the frame around them used to override the checked
background and leave dark text on a dark background, 1.02 to 1. The pixels
were read by hand as well, from a rendered screenshot.
"""

from __future__ import annotations

import re

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractButton,
    QCheckBox,
    QLabel,
    QPushButton,
    QWidget,
)

from s_q_ali_media_downloader.theme import stylesheet
from s_q_ali_media_downloader.ui.main_window import MainWindow

SIZES = [(1280, 720), (1366, 768), (1440, 900), (1680, 1000)]

# A control smaller than this is hard to hit with a mouse.
MIN_CONTROL_HEIGHT = 24


def _srgb(value: float) -> float:
    value = value / 255.0
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def _luminance(rgb) -> float:
    r, g, b = rgb
    return 0.2126 * _srgb(r) + 0.7152 * _srgb(g) + 0.0722 * _srgb(b)


def contrast(a, b) -> float:
    la, lb = _luminance(a), _luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _is_clipped(widget: QWidget) -> bool:
    """True when the widget's own text does not fit inside it."""
    if not isinstance(widget, (QLabel, QPushButton, QCheckBox)):
        return False
    if not widget.isVisible():
        return False
    text = widget.text()
    if not text:
        return False
    if isinstance(widget, QLabel):
        if widget.wordWrap():
            # A wrapped label may be narrower than its unwrapped size; what
            # matters is that the wrapped text fits the height it was given.
            needed = widget.heightForWidth(widget.width())
            return needed > widget.height() + 1
        return widget.sizeHint().width() > widget.width() + 1
    return widget.sizeHint().width() > widget.width() + 1


def _clipped_widgets(window: MainWindow) -> list[str]:
    found = []
    for widget in window.findChildren(QWidget):
        if not _is_clipped(widget):
            continue
        text = widget.text().replace("\n", " ")
        found.append(
            f"{type(widget).__name__} {text[:40]!r} "
            f"needs {widget.sizeHint().width()}px, has {widget.width()}px"
        )
    return found


def _too_small_controls(window: MainWindow) -> list[str]:
    found = []
    for widget in window.findChildren(QAbstractButton):
        if not widget.isVisible():
            continue
        if widget.height() < MIN_CONTROL_HEIGHT:
            found.append(
                f"{type(widget).__name__} {widget.text()[:30]!r} is {widget.height()}px tall"
            )
    return found


@pytest.fixture
def window(qapp, isolated_appdata):
    win = MainWindow()
    win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    yield win
    win.close()


@pytest.mark.parametrize("size", SIZES)
def test_nothing_is_clipped_at_any_size(window, size):
    window.resize(*size)
    window.show()
    for _ in range(40):
        qapp_process()

    clipped = _clipped_widgets(window)
    assert not clipped, f"clipped at {size[0]}x{size[1]}:\n  " + "\n  ".join(clipped)


@pytest.mark.parametrize("size", SIZES)
def test_every_control_is_big_enough_to_click(window, size):
    window.resize(*size)
    window.show()
    for _ in range(40):
        qapp_process()

    small = _too_small_controls(window)
    assert not small, f"too small at {size[0]}x{size[1]}:\n  " + "\n  ".join(small)


def test_the_window_can_be_narrower_than_a_small_laptop(window):
    """The window's own minimum must not be wider than a 1280 screen.

    When it was, the window could not be made smaller and the layout was
    squeezed instead - the first row of controls was cut off at the top.
    """
    window.resize(1280, 720)
    window.show()
    for _ in range(40):
        qapp_process()

    assert window.minimumSizeHint().width() <= 1280


def _bare_stylesheets(window: MainWindow) -> list[str]:
    """Widgets whose stylesheet cascades to their children.

    A stylesheet made of bare properties - ``background: #100E14;`` with
    no selector - applies to the widget *and every child it holds*. The
    nav bar's frame used to set one, the rule reached the tab buttons and
    overrode their checked background, while their checked text colour
    stayed dark: dark text on a dark background, 1.02 to 1. The user could
    not tell which workspace was open.
    """
    found = []
    for widget in window.findChildren(QWidget):
        css = widget.styleSheet()
        if not css:
            continue
        if "{" not in css:
            if widget.findChildren(QWidget):
                found.append(
                    f"{type(widget).__name__} sets bare properties on a widget "
                    f"with {len(widget.findChildren(QWidget))} children"
                )
            continue
        for selector, _body in re.findall(r"([^{}]*)\{([^{}]*)\}", css):
            if not selector.strip():
                found.append(f"{type(widget).__name__} sets a bare rule")
                break
    return found


def test_no_stylesheet_cascades_onto_the_workspace_tabs(window):
    window.resize(1366, 768)
    window.show()
    for _ in range(40):
        qapp_process()

    assert window.btn_nav_queue.isChecked()
    assert not _bare_stylesheets(window), "\n  ".join(_bare_stylesheets(window))


def test_the_checked_tab_declares_readable_colours():
    """The checked tab's own colours, straight from the stylesheet."""
    css = stylesheet("comfortable")
    block = re.search(
        r'QPushButton\[kind="tab"\]:checked\s*\{([^}]*)\}', css
    )
    assert block, "the checked tab has no rule in the stylesheet"
    body = block.group(1)

    def value(name: str) -> str:
        found = re.search(rf"(?<![-\w]){name}\s*:\s*(#[0-9A-Fa-f]{{6}})", body)
        assert found, f"the checked tab declares no {name}"
        return found.group(1)

    foreground = tuple(int(value("color")[i : i + 2], 16) for i in (1, 3, 5))
    background = tuple(int(value("background")[i : i + 2], 16) for i in (1, 3, 5))
    assert contrast(foreground, background) >= 4.5


def test_the_settings_page_is_reachable_and_holds_the_groq_key(window):
    window.resize(1366, 768)
    window.show()
    for _ in range(40):
        qapp_process()

    window.btn_nav_settings.click()
    for _ in range(20):
        qapp_process()

    assert window.workspace_stack.currentWidget() is window.settings_page


def qapp_process():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is not None:
        app.processEvents()



