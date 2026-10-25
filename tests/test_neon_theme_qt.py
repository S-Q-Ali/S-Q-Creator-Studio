"""Regression tests for the neon theme.

The density pass used to re-apply the legacy stylesheet on top of the neon
theme, so the app always opened in the old palette. These tests pin both the
Qt-valid stylesheet and the "density must not change the theme" rule.
"""

from PySide6.QtWidgets import QWidget

from s_q_ali_media_downloader.core.theme_neon import NeonTheme
from s_q_ali_media_downloader.theme import apply_density
from s_q_ali_media_downloader.ui.themes import apply_neon_theme


def test_neon_stylesheet_is_qt_valid():
    qss = NeonTheme.get_stylesheet()
    assert "#0a0a0a" in qss
    assert "#00d4ff" in qss
    assert "qlineargradient" in qss
    for unsupported in ("box-shadow", "text-shadow", "linear-gradient", "animation:"):
        assert unsupported not in qss, f"{unsupported} is ignored by Qt"


def test_density_change_keeps_the_neon_theme(qapp):
    apply_neon_theme(qapp)
    apply_density(QWidget(), False)

    assert qapp.property("s_q_theme") == "neon"
    assert "#00d4ff" in qapp.styleSheet()


def test_neon_stylesheet_parses_without_warnings(qapp, capfd):
    widget = QWidget()
    widget.setStyleSheet(NeonTheme.get_stylesheet())
    widget.show()
    qapp.processEvents()
    widget.close()
    _, err = capfd.readouterr()
    assert not err, f"Qt reported stylesheet warnings:\n{err}"
