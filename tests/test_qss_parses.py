"""QSS stylesheets must parse cleanly so the glass design renders correctly.

A single stray token or unmatched brace silently drops every rule that follows
it, so the stylesheet is pinned against Qt's parser on every run - in both
densities, because density is a second render of the same sheet, not a second
sheet.
"""

import sys

import pytest
from PySide6.QtWidgets import QLabel, QWidget

from s_q_ali_media_downloader.theme import STYLESHEET, stylesheet

DENSITIES = ("comfortable", "compact")


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


@pytest.mark.parametrize("density", DENSITIES)
def test_main_stylesheet_parses(qapp, capfd, density):
    _parse_without_warnings(qapp, stylesheet(density))
    _, err = capfd.readouterr()
    assert not err, f"Qt reported stylesheet warnings:\n{err}"


@pytest.mark.parametrize("density", DENSITIES)
def test_main_stylesheet_has_no_stray_tokens(density):
    # Regression: a stray bare "W" once sat at the end of the stylesheet.
    css = stylesheet(density)
    assert not css.rstrip().endswith("W"), "stray token at end of stylesheet"


def test_the_default_sheet_is_the_comfortable_render():
    assert STYLESHEET == stylesheet("comfortable")


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-v"]))
