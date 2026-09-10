"""QSS stylesheets must parse cleanly so the dark-cyan design renders correctly.

A single stray token or unmatched brace silently drops every rule that follows
it, so both stylesheets are pinned against Qt's parser on every run.
"""

import sys

import pytest
from PySide6.QtWidgets import QLabel, QWidget

from s_q_ali_media_downloader.niche_research.ui.theme import research_style
from s_q_ali_media_downloader.theme import STYLESHEET


def _parse_without_warnings(qapp, css: str) -> None:
    widget = QWidget()
    widget.setStyleSheet(css)
    widget.show()
    qapp.processEvents()
    vertex = QLabel("x")
    vertex.setStyleSheet(css)
    vertex.show()
    qapp.processEvents()
    vertex.close()
    widget.close()


def test_main_stylesheet_parses(qapp, capfd):
    _parse_without_warnings(qapp, STYLESHEET)
    _, err = capfd.readouterr()
    assert not err, f"Qt reported stylesheet warnings:\n{err}"


def test_research_stylesheet_parses(qapp, capfd):
    _parse_without_warnings(qapp, research_style())
    _, err = capfd.readouterr()
    assert not err, f"Qt reported stylesheet warnings:\n{err}"


def test_research_stylesheet_has_no_stray_tokens(qapp):
    # Regression: a stray bare "W" once sat at the end of the stylesheet.
    css = research_style()
    assert not css.rstrip().endswith("W"), "stray token at end of stylesheet"
    assert "text-transform: uppercase" in css


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-v"]))