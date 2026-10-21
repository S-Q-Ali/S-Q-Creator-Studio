"""Offscreen tests for the ResearchContainer + main-window research tab."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QLabel, QPushButton

from s_q_ali_media_downloader.niche_research.storage import db
from s_q_ali_media_downloader.niche_research.ui.competitors_page import NichePoller
from s_q_ali_media_downloader.niche_research.ui.research_container import SIDEBAR, ResearchContainer


def _find_button(page, text: str) -> QPushButton | None:
    """The first button with this exact label (None when there is none)."""
    for button in page.findChildren(QPushButton):
        if button.text() == text:
            return button
    return None


def _video_result(video_id: str = "vidQ"):
    """A minimal scored-video result (no network involved)."""
    from s_q_ali_media_downloader.niche_research.research import scorecard_engine as se

    return se.VideoLookupResult(
        video={
            "video_id": video_id,
            "channel_id": "UCc1",
            "channel_title": "Chan",
            "title": "A Video",
            "description": "",
            "published_at": "2026-09-01T00:00:00Z",
            "duration_seconds": 60,
            "thumbnail_url": "",
            "tags": [],
            "view_count": 100,
            "like_count": 1,
            "comment_count": 1,
        },
        channel={
            "channel_id": "UCc1",
            "title": "Chan",
            "thumbnail_url": "",
            "subscriber_count": 5,
        },
        seo=se.compute_seo_score({"title": "A Video", "description": "", "tags": []}),
        vph=se.VphResult(vph=None, window_hours=0, error="Need two snapshots"),
        tracked=False,
    )


def _seed_tracked_video(video_id: str = "vidQ") -> None:
    db.run(
        "INSERT INTO tracked_items (kind, ref_id, label, added_at) VALUES (?, ?, ?, ?)",
        ("video", video_id, "A Video", db.now()),
    )
    db.run(
        "INSERT INTO videos (video_id, title, thumbnail_url, channel_id, published_at, "
        "view_count, like_count, comment_count, last_fetched) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (video_id, "A Video", "", "UCc1", "2026-01-01T00:00:00Z", 1000, 1, 1, db.now()),
    )


def _seed_keyword_with_ranking() -> None:
    db.run(
        "INSERT INTO keywords (term, display_term, score, demand_score, competition_score, "
        "competition_label, source, first_seen, last_checked) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("ai tools", "AI Tools", 82, 90, 25, "Low", "search", db.now(), db.now()),
    )
    db.run(
        "INSERT INTO rankings (term, video_id, position, ts) VALUES (?, ?, ?, ?)",
        ("ai tools", "vidR", 1, db.now()),
    )
    db.run(
        "INSERT INTO videos (video_id, title, view_count, last_fetched) VALUES (?, ?, ?, ?)",
        ("vidR", "Ranked video", 5000, db.now()),
    )


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
            self.queue_urls_requested = _FakeSignal()
            self.track_channel_requested = _FakeSignal()

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


# --------------------------------------------------------------------------- #
# Handoffs (SPEC-handoffs.md): the missing half of the matrix
# --------------------------------------------------------------------------- #
def test_scorecard_queue_hands_the_video_to_the_download_queue(qapp):
    """Scorecard -> Download queue: the scored video must reach the queue
    through the one shared bridge, never through a second path."""
    container = ResearchContainer()
    got: list = []
    container.send_to_queue_requested.connect(got.append)

    container.scorecard_page._on_done(_video_result("vidQ"))
    qapp.processEvents()

    button = _find_button(container.scorecard_page, "Queue")
    assert button is not None, "the scorecard has no Queue button"
    assert button.isEnabled() is True
    button.click()

    assert got == [["https://www.youtube.com/watch?v=vidQ"]]
    container.stop_poller()
    container.deleteLater()


def test_scorecard_open_on_youtube_opens_the_browser(qapp, monkeypatch):
    """Scorecard -> YouTube: the scored video opens in the default browser."""
    import s_q_ali_media_downloader.niche_research.ui.research_container as rc

    opened: list[str] = []

    class _FakeDesktopServices:
        @staticmethod
        def openUrl(url):
            opened.append(url.toString())
            return True

    monkeypatch.setattr(rc, "QDesktopServices", _FakeDesktopServices)

    container = ResearchContainer()
    container.scorecard_page._on_done(_video_result("vidO"))
    qapp.processEvents()

    button = _find_button(container.scorecard_page, "Open on YouTube")
    assert button is not None, "the scorecard has no Open on YouTube button"
    button.click()

    assert opened == ["https://www.youtube.com/watch?v=vidO"]
    container.stop_poller()
    container.deleteLater()


def test_competitors_queue_hands_the_video_to_the_download_queue(qapp):
    """Competitors -> Download queue: a tracked video can be queued."""
    _seed_tracked_video("vidQ")
    container = ResearchContainer()
    got: list = []
    container.send_to_queue_requested.connect(got.append)
    container.competitors_page.refresh_dashboard()
    qapp.processEvents()

    button = _find_button(container.competitors_page, "Queue")
    assert button is not None, "the competitors page has no Queue button"
    button.click()

    assert got == [["https://www.youtube.com/watch?v=vidQ"]]
    container.stop_poller()
    container.deleteLater()


def test_keyword_detail_analyze_opens_the_scorecard(qapp):
    """Keyword Research -> Scorecard: a ranked video is scored on the
    Scorecard page, with the keyword as the focus keyword."""
    _seed_keyword_with_ranking()
    container = ResearchContainer()
    container.keyword_page.show_detail("ai tools")
    qapp.processEvents()

    button = _find_button(container.keyword_page, "Analyze")
    assert button is not None, "the keyword detail has no Analyze button"
    button.click()

    assert container.current_page() == "scorecard"
    assert "vidR" in container.scorecard_page._url_edit.text()
    assert container.scorecard_page._keyword_edit.text() == "ai tools"
    container.stop_poller()
    container.deleteLater()


def test_keyword_detail_analyze_keyword_button_scores_the_top_video(qapp):
    """The keyword-level button scores the top-ranked video."""
    _seed_keyword_with_ranking()
    container = ResearchContainer()
    container.keyword_page.show_detail("ai tools")
    qapp.processEvents()

    button = _find_button(container.keyword_page, "Analyze keyword")
    assert button is not None, "the keyword detail has no Analyze keyword button"
    button.click()

    assert container.current_page() == "scorecard"
    assert "vidR" in container.scorecard_page._url_edit.text()
    container.stop_poller()
    container.deleteLater()


def test_keyword_track_button_uses_the_canonical_helper(qapp, monkeypatch):
    """The UI layer must not write tracked_items with its own SQL."""
    from s_q_ali_media_downloader.niche_research.research import competitor_engine as ce

    calls: list = []
    monkeypatch.setattr(
        ce, "track_item", lambda kind, ref, label="": calls.append((kind, ref, label))
    )
    monkeypatch.setattr(ce, "is_tracked", lambda kind, ref: False)

    _seed_keyword_with_ranking()
    container = ResearchContainer()
    container.keyword_page.show_detail("ai tools")
    qapp.processEvents()
    container.keyword_page._on_track()

    assert calls == [("keyword", "ai tools", "ai tools")]
    container.stop_poller()
    container.deleteLater()


def test_snapshot_interval_change_takes_effect_without_a_restart(qapp):
    """The poller read the interval once, so a new setting only took effect
    after a restart."""
    container = ResearchContainer()
    assert container._poller._timer.interval() == 60 * 60 * 1000

    combo = container.settings_page._interval_combo
    combo.setCurrentIndex(combo.findData(30))
    container.settings_page._save()

    assert container._poller._timer.interval() == 30 * 60 * 1000
    container.stop_poller()
    container.deleteLater()


# --------------------------------------------------------------------------- #
# AI Analysis handoffs: the modal is owned elsewhere, the wiring is here
# --------------------------------------------------------------------------- #
def _fake_modal(monkeypatch) -> None:
    """Replace the analysis modal with a signal-only stand-in."""
    from PySide6.QtCore import QObject, Signal

    import s_q_ali_media_downloader.niche_research.ui.research_container as rc

    class _FakeModal(QObject):
        finished = Signal()
        open_scorecard_requested = Signal(str)
        queue_urls_requested = Signal(list)
        track_channel_requested = Signal(str)

        def __init__(self, channel_id, parent=None):
            super().__init__(parent)
            self.channel_id = channel_id

        def exec(self):
            return None

    monkeypatch.setattr(rc, "AnalysisModal", _FakeModal)


def test_analysis_modal_queue_handoff_uses_the_shared_bridge(qapp, monkeypatch):
    """AI Analysis -> Download queue: the modal's queue signal must reach the
    one shared queue bridge."""
    _fake_modal(monkeypatch)
    container = ResearchContainer()
    got: list = []
    container.send_to_queue_requested.connect(got.append)

    container._open_analysis("UC1")
    container._analysis_modal.queue_urls_requested.emit(
        ["https://www.youtube.com/watch?v=v1"]
    )

    assert got == [["https://www.youtube.com/watch?v=v1"]]
    container.stop_poller()
    container.deleteLater()


def test_analysis_modal_track_handoff_tracks_the_channel(qapp, monkeypatch):
    """AI Analysis -> Competitors: the analysed channel is tracked."""
    _fake_modal(monkeypatch)
    container = ResearchContainer()

    container._open_analysis("UC1")
    container._analysis_modal.track_channel_requested.emit("UC9")

    row = db.get("SELECT * FROM tracked_items WHERE kind='channel' AND ref_id='UC9'")
    assert row is not None
    container.stop_poller()
    container.deleteLater()
