"""Legibility and theme-consistency guards for the AI Channel Finder tab."""

from pathlib import Path

AGENT_TAB = (
    Path(__file__).parent.parent
    / "src"
    / "s_q_ali_media_downloader"
    / "ui"
    / "agent_tab.py"
)


def test_agent_tab_imports_theme_constants():
    text = AGENT_TAB.read_text(encoding="utf-8")
    assert "from s_q_ali_media_downloader.theme import C" in text


def test_agent_tab_avoids_off_palette_and_low_contrast_colors():
    text = AGENT_TAB.read_text(encoding="utf-8")
    assert "#FACC15" not in text  # low-contrast yellow on the dark panel
    assert "#6E667E" not in text  # darker than muted, fails contrast on panel