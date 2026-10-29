"""Legibility and theme-consistency guards for the AI Channel Finder tab."""

from pathlib import Path

from PySide6.QtWidgets import QAbstractItemView, QTableWidget, QTableWidgetItem

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


def test_populate_tiktok_table_marks_every_platform_as_a_link(qapp, isolated_appdata):
    tab = AgentTabWidget()
    profile = TikTokProfileMetadata(
        profile_id="1",
        handle="creator",
        profile_url="https://www.tiktok.com/@creator",
        facebook=SocialPresence(
            platform=SocialPlatform.FACEBOOK,
            status=SocialStatus.VERIFIED,
            verified_url="https://www.facebook.com/creator",
        ),
        instagram=SocialPresence(
            platform=SocialPlatform.INSTAGRAM, status=SocialStatus.NOT_FOUND
        ),
        youtube=SocialPresence(
            platform=SocialPlatform.YOUTUBE,
            status=SocialStatus.VERIFIED,
            verified_url="https://www.youtube.com/@creator",
        ),
    )
    tab._populate_tiktok_table([profile])
    assert tab.table.item(0, 1).data(tab._URL_ROLE) == profile.profile_url
    assert tab.table.item(0, 4).data(tab._URL_ROLE) == "https://www.facebook.com/creator"
    assert tab.table.item(0, 5).data(tab._URL_ROLE) is None
    assert tab.table.item(0, 6).data(tab._URL_ROLE) == "https://www.youtube.com/@creator"
    assert tab.table.item(0, 7).data(tab._URL_ROLE) == "https://www.youtube.com/@creator"


def test_the_tiktok_table_names_facebook_and_instagram(qapp, isolated_appdata):
    from s_q_ali_media_downloader.ui.agent_tab import MODE_TIKTOK

    tab = AgentTabWidget()
    tab._setup_table_columns(MODE_TIKTOK)

    headers = [
        tab.table.horizontalHeaderItem(col).text()
        for col in range(tab.table.columnCount())
    ]
    assert headers == [
        "Select",
        "Nickname",
        "Handle",
        "Followers",
        "Facebook",
        "Instagram",
        "YouTube Status",
        "YouTube Channel",
        "Flag",
        "Action",
    ]


def test_copy_facebook_and_instagram_links_work_in_the_tiktok_mode(
    qapp, isolated_appdata, monkeypatch
):
    from PySide6.QtWidgets import QApplication

    from s_q_ali_media_downloader.agent.schema import TikTokSearchResult

    tab = AgentTabWidget()
    profile = TikTokProfileMetadata(
        profile_id="1",
        handle="creator",
        profile_url="https://www.tiktok.com/@creator",
        facebook=SocialPresence(
            platform=SocialPlatform.FACEBOOK,
            status=SocialStatus.VERIFIED,
            verified_url="https://www.facebook.com/creator",
        ),
        instagram=SocialPresence(
            platform=SocialPlatform.INSTAGRAM,
            status=SocialStatus.VERIFIED,
            verified_url="https://www.instagram.com/creator/",
        ),
    )
    tab.search_result = TikTokSearchResult(query="x", profiles=[profile])

    tab._copy_fb_links()
    assert QApplication.clipboard().text() == "https://www.facebook.com/creator"
    assert "1 Facebook" in tab.lbl_status.text()

    tab._copy_ig_links()
    assert QApplication.clipboard().text() == "https://www.instagram.com/creator/"
    assert "1 Instagram" in tab.lbl_status.text()


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


def test_the_activity_log_stays_visible_in_every_mode(qapp, isolated_appdata):
    from s_q_ali_media_downloader.ui.agent_tab import MODE_SOCIAL

    tab = AgentTabWidget()

    assert tab.activity.isVisibleTo(tab)
    tab.mode_combo.setCurrentText(MODE_SOCIAL)
    assert tab.social_page.isVisibleTo(tab)
    assert tab.activity.isVisibleTo(tab)
    tab.deleteLater()


def test_social_discovery_lines_reach_the_shared_log(qapp, isolated_appdata):
    tab = AgentTabWidget()

    tab.social_page.log.emit("AI hand-off: Groq first, Gemini fallback")

    assert "AI hand-off" in tab.activity.text()
    tab.deleteLater()


def test_the_worker_forwards_orchestrator_log_lines(
    qapp, isolated_appdata, monkeypatch
):
    from s_q_ali_media_downloader.agent.schema import AgentSearchResult
    from s_q_ali_media_downloader.ui import agent_tab as at

    seen = {}

    class FakeOrchestrator:
        def __init__(
            self,
            api_key=None,
            progress_callback=None,
            log_callback=None,
            show_browser=True,
        ):
            self.log_callback = log_callback
            seen["show_browser"] = show_browser

        def run_discovery(self, **kwargs):
            self.log_callback("Search backend: yt-dlp scraper")
            return AgentSearchResult(query="x")

    monkeypatch.setattr(at, "AgentOrchestrator", FakeOrchestrator)
    worker = at.AgentWorkerThread(
        query="x",
        max_channels=10,
        min_subs=0,
        check_fb=True,
        check_ig=True,
        check_tiktok=False,
        only_no_socials=False,
        only_no_youtube=False,
        api_key="",
        mode=at.MODE_YOUTUBE,
        show_browser=False,
    )
    lines = []
    worker.log.connect(lines.append)

    worker.run()

    assert lines == ["Search backend: yt-dlp scraper"]
    assert seen["show_browser"] is False


def test_agent_table_is_read_only_and_clean(qapp, isolated_appdata):
    tab = AgentTabWidget()
    assert tab.table.editTriggers() == QAbstractItemView.EditTrigger.NoEditTriggers
    assert tab.table.selectionMode() == QAbstractItemView.SelectionMode.ExtendedSelection
    assert tab.table.selectionBehavior() == QTableWidget.SelectRows
    assert tab.table.showGrid() is False
    assert tab.table.verticalHeader().isVisible() is False
    assert tab.table.alternatingRowColors() is True
    assert tab.table.verticalHeader().defaultSectionSize() == 34
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