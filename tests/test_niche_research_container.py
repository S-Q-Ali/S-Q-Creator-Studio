"""Offscreen tests for the ResearchContainer + main-window research tab."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QLabel, QPushButton

from s_q_ali_media_downloader.niche_research.storage import db
from s_q_ali_media_downloader.niche_research.ui.competitors_page import NichePoller
from s_q_ali_media_downloader.niche_research.ui.research_container import SIDEBAR, ResearchContainer


@pytest.fixture(autouse=True)
def _db(isolated_appdata):
    db.configure(None)
    yield
    db.close_db()


def test_container_builds_all_pages(qapp):
    container = ResearchContainer()
    assert container.stack.count() == len(SIDEBAR) == 6
    assert container.current_page() == "dashboard"
    container.deleteLater()


def test_competitors_channel_handoff_opens_the_scorecard_in_channel_mode(qapp):
    """The handoff carried no mode, so a channel URL was scored as a video
    and the lookup always failed with "Could not parse a YouTube video ID"."""
    container = ResearchContainer()

    container.competitors_page.scorecard_requested.emit(
        "https://www.youtube.com/channel/UCx", "channel"
    )

    assert container.scorecard_page._mode == "channel"
    container.deleteLater()


def test_container_sidebar_navigation(qapp):
    container = ResearchContainer()
    container.show_page("trending")
    assert container.current_page() == "trending"
    assert container._sidebar_buttons["trending"].isChecked()
    container.show_page("competitors")
    assert container.current_page() == "competitors"
    container.deleteLater()


def test_container_has_poller(qapp):
    container = ResearchContainer()
    assert isinstance(container._poller, NichePoller)
    container.stop_poller()
    container.deleteLater()


def test_container_forwards_queue_urls(qapp):
    """The research tab must be able to hand video URLs to the download
    queue through one shared signal."""
    container = ResearchContainer()
    got: list = []
    container.send_to_queue_requested.connect(got.append)

    container.trending_page.queue_urls_requested.emit(
        ["https://www.youtube.com/watch?v=abc"]
    )

    assert got == [["https://www.youtube.com/watch?v=abc"]]
    container.stop_poller()
    container.deleteLater()


def test_container_opens_the_scorecard_for_a_channel(qapp):
    """Discovery -> Scorecard handoff: the scorecard page must open with the
    channel prefilled in channel mode."""
    container = ResearchContainer()
    container.trending_page.scorecard_requested.emit("UCchan")

    assert container.current_page() == "scorecard"
    assert container.scorecard_page._mode == "channel"
    assert "UCchan" in container.scorecard_page._url_edit.text()
    container.stop_poller()
    container.deleteLater()


def test_dashboard_shows_live_metrics(qapp):
    """The dashboard was a static intro card — it must show real numbers."""
    from s_q_ali_media_downloader.niche_research.storage import db

    db.run(
        "INSERT INTO trending_channels (channel_id, title, category_name, discovered_at, "
        "viral_score, subscriber_count, niche, video_format) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("UCa", "Alpha", "Tech", 1, 90, 1000, "tech_ai", "longform"),
    )
    container = ResearchContainer()
    container.refresh_dashboard()

    assert container._dash_metrics["channelsDiscovered"].text() == "1"
    labels = [label.text() for label in container.dashboard_page.findChildren(QLabel)]
    assert any("Alpha" in text for text in labels)
    container.stop_poller()
    container.deleteLater()


def test_dashboard_quick_actions_navigate(qapp):
    """The guide cards are buttons now, not static labels."""
    container = ResearchContainer()
    buttons = [
        b
        for b in container.dashboard_page.findChildren(QPushButton)
        if "Niche Discovery" in b.text()
    ]
    assert buttons
    buttons[0].click()
    assert container.current_page() == "trending"
    container.stop_poller()
    container.deleteLater()


def test_poller_refreshes_regardless_of_the_visible_page(qapp):
    """The poller only ran while the Competitors tab was open, so VPH and
    growth never accumulated for most users."""
    container = ResearchContainer()
    calls: list = []
    container.competitors_page.refresh_now = lambda: calls.append(1)

    container.show_page("dashboard")
    container._on_poll_tick()

    assert calls == [1]
    container.stop_poller()
    container.deleteLater()


def test_poller_interval_follows_the_setting(qapp):
    from s_q_ali_media_downloader.niche_research.storage import db

    db.set_setting("snapshot_interval_minutes", "30")
    container = ResearchContainer()
    assert container._poller._timer.interval() == 30 * 60 * 1000
    container.stop_poller()
    container.deleteLater()


def test_update_button_disabled_on_static_pages(qapp):
    container = ResearchContainer()
    assert container.btn_update.isEnabled() is False  # dashboard
    container.show_page("settings")
    assert container.btn_update.isEnabled() is False
    container.show_page("scorecard")
    assert container.btn_update.isEnabled() is False
    container.show_page("trending")
    assert container.btn_update.isEnabled() is True
    container.stop_poller()
    container.deleteLater()


def test_update_button_refreshes_trending(qapp, monkeypatch):
    calls = []

    def fake_discovery():
        calls.append(1)

    container = ResearchContainer()
    monkeypatch.setattr(container.trending_page, "start_discovery", fake_discovery)
    container.show_page("trending")
    assert container.btn_update.isEnabled() is True
    container.btn_update.click()
    assert calls == [1]
    container.stop_poller()
    container.deleteLater()


def test_update_button_takes_fresh_competitor_snapshot(qapp, monkeypatch):
    calls = []

    def fake_refresh_now():
        calls.append(1)

    container = ResearchContainer()
    monkeypatch.setattr(container.competitors_page, "refresh_now", fake_refresh_now)
    container.show_page("competitors")
    container.btn_update.click()
    assert calls == [1]
    container.stop_poller()
    container.deleteLater()


def test_update_button_reruns_keywords(qapp, monkeypatch):
    calls = []

    def fake_re_run():
        calls.append(1)

    container = ResearchContainer()
    monkeypatch.setattr(container.keyword_page, "re_run", fake_re_run)
    container.show_page("keywords")
    assert container.btn_update.isEnabled() is True
    container.btn_update.click()
    assert calls == [1]
    container.stop_poller()
    container.deleteLater()


def test_container_analysis_signal(qapp, monkeypatch):
    opened = {}

    def fake_open(self, cid):
        opened["cid"] = cid

    monkeypatch.setattr(ResearchContainer, "_open_analysis", fake_open)
    container = ResearchContainer()
    container.stop_poller()
    container._open_analysis("UC123")
    assert opened.get("cid") == "UC123"
    container.deleteLater()


def test_container_analysis_modal_not_stacked(qapp, monkeypatch):
    import s_q_ali_media_downloader.niche_research.ui.research_container as rc

    calls = []

    class _FakeSignal:
        def __init__(self):
            self.slots = []

        def connect(self, slot):
            self.slots.append(slot)

        def emit(self, *args):
            for slot in self.slots:
                slot(*args)

    class _FakeModal:
        def __init__(self, channel_id, parent=None):
            self.channel_id = channel_id
            self.finished = _FakeSignal()
            self.open_scorecard_requested = _FakeSignal()

        def exec(self):
            calls.append(self.channel_id)

    monkeypatch.setattr(rc, "AnalysisModal", _FakeModal)
    container = ResearchContainer()
    container._open_analysis("UC1")
    container._open_analysis("UC2")  # already open -> should be ignored
    assert calls == ["UC1"]
    container._analysis_modal.finished.emit(0)  # user closes the modal
    container._open_analysis("UC3")
    assert calls == ["UC1", "UC3"]
    container.stop_poller()
    container.deleteLater()


def test_main_window_research_nav(qapp):
    from s_q_ali_media_downloader.ui.main_window import MainWindow

    window = MainWindow()
    assert hasattr(window, "btn_nav_research")
    assert window.workspace_stack.count() == 3
    window.btn_nav_research.click()
    assert window.workspace_stack.currentIndex() == 2
    assert window.research_tab.current_page() == "dashboard"
    window.research_tab.stop_poller()
    window.close()


def test_main_window_research_tab_shows_pages(qapp):
    from s_q_ali_media_downloader.ui.main_window import MainWindow

    window = MainWindow()
    window.btn_nav_research.click()
    container = window.research_tab
    container.show_page("keywords")
    assert container.current_page() == "keywords"
    container.show_page("scorecard")
    assert container.current_page() == "scorecard"
    container.show_page("settings")
    assert container.current_page() == "settings"
    container.stop_poller()
    window.close()


def container_module_analysis():
    import s_q_ali_media_downloader.niche_research.ui.research_container as rc

    return rc
