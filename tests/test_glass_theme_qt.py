"""The glass sheet as Qt actually holds it.

``test_theme.py`` reads the tokens; this file talks to a live QApplication,
because a stylesheet can be arithmetically correct and still be one stray token
away from Qt dropping every rule after it.

This replaces ``tests/test_neon_theme_qt.py``. Two of its three assertions -
that the sheet is Qt-valid and that it parses warning-free - are now made
against the rendered sheet by ``test_theme.py`` and ``test_qss_parses.py``, so
they are not repeated here. The third was the real one: the density pass used to
re-apply the legacy stylesheet over the live theme, so the app always opened in
the old palette. The rule flipped when the two sheets became one - density must
now re-render the *same* tokens at a new size, and this is the test that says so.
"""

from PySide6.QtWidgets import QWidget

from s_q_ali_media_downloader.theme import STYLESHEET, C, apply_density


def test_the_app_holds_the_glass_sheet(qapp):
    qapp.setStyleSheet(STYLESHEET)
    sheet = qapp.styleSheet()
    assert C["accent"] in sheet
    assert C["bg"] in sheet
    assert "rgba(" in sheet, "the panels lost their glass"


def test_density_re_renders_the_same_tokens(qapp):
    """Compact changes the measurements, never the palette."""
    qapp.setStyleSheet(STYLESHEET)
    apply_density(QWidget(), True)

    sheet = qapp.styleSheet()
    assert "font-size: 12px" in sheet, "compact did not re-render the sheet"
    assert C["accent"] in sheet
    assert C["bg"] in sheet

    apply_density(QWidget(), False)
    assert "font-size: 13px" in qapp.styleSheet()
