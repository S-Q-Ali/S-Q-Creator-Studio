"""Legibility and theme-consistency guards for the AI Channel Finder tab."""

from pathlib import Path

from PySide6.QtWidgets import QTableWidgetItem

from s_q_ali_media_downloader.agent.schema import (
    ChannelMetadata,
    SocialPlatform,
    SocialPresence,
    SocialStatus,
    TikTokProfileMetadata,
)
from s_q_ali_media_downloader.ui.agent_tab import AgentTabWidget

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


def test_populate_table_marks_verified_socials_and_channel_as_links(qapp, isolated_appdata):
    tab = AgentTabWidget()
    channel = ChannelMetadata(
        channel_id="ucx",
        title="Test Channel",
        youtube_url="https://www.youtube.com/channel/ucx",
        facebook=SocialPresence(
            platform=SocialPlatform.FACEBOOK,
            status=SocialStatus.VERIFIED,
            verified_url="https://www.facebook.com/testpage",
        ),
        instagram=SocialPresence(platform=SocialPlatform.INSTAGRAM, status=SocialStatus.NOT_FOUND),
        tiktok=SocialPresence(platform=SocialPlatform.TIKTOK, status=SocialStatus.INCONCLUSIVE),
    )
    tab._populate_table([channel])
    assert tab.table.item(0, 1).data(tab._URL_ROLE) == channel.youtube_url
    assert tab.table.item(0, 4).data(tab._URL_ROLE) == "https://www.facebook.com/testpage"
    assert tab.table.item(0, 5).data(tab._URL_ROLE) is None
    assert tab.table.item(0, 6).data(tab._URL_ROLE) is None


def test_populate_tiktok_table_marks_youtube_channel_and_profile_as_links(qapp, isolated_appdata):
    tab = AgentTabWidget()
    profile = TikTokProfileMetadata(
        profile_id="1",
        handle="creator",
        profile_url="https://www.tiktok.com/@creator",
        youtube=SocialPresence(
            platform=SocialPlatform.YOUTUBE,
            status=SocialStatus.VERIFIED,
            verified_url="https://www.youtube.com/@creator",
        ),
    )
    tab._populate_tiktok_table([profile])
    assert tab.table.item(0, 1).data(tab._URL_ROLE) == profile.profile_url
    assert tab.table.item(0, 4).data(tab._URL_ROLE) == "https://www.youtube.com/@creator"
    assert tab.table.item(0, 5).data(tab._URL_ROLE) == "https://www.youtube.com/@creator"


def test_open_cell_url_opens_only_link_cells(qapp, isolated_appdata, monkeypatch):
    from s_q_ali_media_downloader.ui import agent_tab as at

    tab = AgentTabWidget()
    opened = []
    monkeypatch.setattr(at.QDesktopServices, "openUrl", lambda url: opened.append(url.toString()))
    tab.table.setRowCount(1)
    tab.table.setItem(0, 0, QTableWidgetItem("plain"))
    tab.table.setItem(0, 1, QTableWidgetItem("link"))
    tab.table.item(0, 1).setData(tab._URL_ROLE, "https://example.com/x")
    tab._open_cell_url(0, 0)
    tab._open_cell_url(0, 1)
    assert opened == ["https://example.com/x"]


def test_send_selected_to_queue_uses_inline_status(qapp, isolated_appdata, monkeypatch):
    from s_q_ali_media_downloader.ui import agent_tab as at

    popups = []
    monkeypatch.setattr(at.QMessageBox, "information", lambda *a, **k: popups.append(a))
    tab = AgentTabWidget()
    channel = ChannelMetadata(
        channel_id="ucx",
        title="Test Channel",
        youtube_url="https://www.youtube.com/channel/ucx",
        latest_video_url="https://www.youtube.com/watch?v=abc",
    )
    tab._populate_table([channel])
    tab._send_selected_to_queue()
    assert popups == []
    assert tab.lbl_status.text().startswith("Sent")
    tab.deleteLater()


def test_copy_links_uses_inline_status(qapp, isolated_appdata, monkeypatch):
    from s_q_ali_media_downloader.ui import agent_tab as at

    popups = []
    monkeypatch.setattr(at.QMessageBox, "information", lambda *a, **k: popups.append(a))
    tab = AgentTabWidget()
    tab._copy_fb_links()
    assert popups == []
    assert "Facebook" in tab.lbl_status.text()
    tab.deleteLater()