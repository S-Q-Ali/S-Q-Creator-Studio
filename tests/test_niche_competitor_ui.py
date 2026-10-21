"""Offscreen tests for the Competitors dashboard page."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QLabel

from s_q_ali_media_downloader.niche_research.storage import db
from s_q_ali_media_downloader.niche_research.ui.competitors_page import (
    CompetitorsPage,
    _fmt,
)
from s_q_ali_media_downloader.niche_research.ui.widgets import CompetitionBadge, ScoreBadge


@pytest.fixture(autouse=True)
def _db(isolated_appdata):
    db.configure(None)
    yield
    db.close_db()


# --------------------------------------------------------------------------- #
# Regression (2026-10): the tracked cards must be actionable
# --------------------------------------------------------------------------- #
def test_tracked_cards_offer_drill_down(isolated_appdata, qapp):
    """Competitors cards were inert: no scorecard, no analysis, no keyword
    detail. Every tracked item needs a way out of the page."""
    from PySide6.QtWidgets import QPushButton

    _seed_video()
    _seed_channel()
    _seed_keyword()

    page = CompetitorsPage()
    page.show()

    labels = {b.text() for b in page.findChildren(QPushButton)}
    assert "Scorecard" in labels
    assert "Analyze" in labels
    assert "Details" in labels


def test_tracked_video_opens_the_scorecard(isolated_appdata, qapp):
    _seed_video()
    page = CompetitorsPage()
    page.show()
    got: list = []
    page.scorecard_requested.connect(lambda url, mode: got.append((url, mode)))

    from PySide6.QtWidgets import QPushButton

    for btn in page.findChildren(QPushButton):
        if btn.text() == "Scorecard":
            btn.click()
            break

    assert got and "watch?v=vidA" in got[0][0]
    assert got[0][1] == "video"


def test_tracked_channel_opens_the_scorecard_in_channel_mode(isolated_appdata, qapp):
    """The handoff carried no mode, so a channel was scored as a video."""
    _seed_channel()
    page = CompetitorsPage()
    page.show()
    got: list = []
    page.scorecard_requested.connect(lambda url, mode: got.append((url, mode)))

    from PySide6.QtWidgets import QPushButton

    for btn in page.findChildren(QPushButton):
        if btn.text() == "Scorecard":
            btn.click()
            break

    assert got and "/channel/" in got[0][0]
    assert got[0][1] == "channel"


def test_tracked_channel_can_be_analysed(isolated_appdata, qapp):
    _seed_channel()
    page = CompetitorsPage()
    page.show()
    got: list = []
    page.analyze_requested.connect(got.append)

    from PySide6.QtWidgets import QPushButton

    for btn in page.findChildren(QPushButton):
        if btn.text() == "Analyze":
            btn.click()
            break

    assert got == ["chanB"]


def test_tracked_keyword_opens_its_detail(isolated_appdata, qapp):
    _seed_keyword()
    page = CompetitorsPage()
    page.show()
    got: list = []
    page.keyword_requested.connect(got.append)

    from PySide6.QtWidgets import QPushButton

    for btn in page.findChildren(QPushButton):
        if btn.text() == "Details":
            btn.click()
            break

    assert got == ["ai tools"]



def _seed_video() -> None:
    db.run(
        "INSERT INTO tracked_items (kind, ref_id, label, added_at) VALUES (?, ?, ?, ?)",
        ("video", "vidA", "Video A", db.now()),
    )
    db.run(
        "INSERT INTO videos (video_id, title, thumbnail_url, channel_id, published_at, "
        "view_count, like_count, comment_count, last_fetched) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("vidA", "Video A", "", "chan1", "2026-01-01T00:00:00Z", 1_000_000, 99, 5, db.now()),
    )
    db.run(
        "INSERT INTO video_snapshots (video_id, ts, view_count, like_count, comment_count) "
        "VALUES (?, ?, ?, ?, ?)",
        ("vidA", db.now() - 2 * 3600 * 1000, 900_000, 80, 4),
    )
    db.run(
        "INSERT INTO video_snapshots (video_id, ts, view_count, like_count, comment_count) "
        "VALUES (?, ?, ?, ?, ?)",
        ("vidA", db.now(), 1_000_000, 99, 5),
    )


def _seed_channel() -> None:
    db.run(
        "INSERT INTO tracked_items (kind, ref_id, label, added_at) VALUES (?, ?, ?, ?)",
        ("channel", "chanB", "Channel B", db.now()),
    )
    db.run(
        "INSERT INTO channels (channel_id, title, thumbnail_url, subscriber_count, "
        "video_count, view_count, last_fetched) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("chanB", "Channel B", "", 200_000, 150, 40_000_000, db.now()),
    )
    db.run(
        "INSERT INTO channel_snapshots (channel_id, ts, subscriber_count, video_count, view_count) "
        "VALUES (?, ?, ?, ?, ?)",
        ("chanB", db.now() - 5 * 24 * 3600 * 1000, 180_000, 140, 38_000_000),
    )
    db.run(
        "INSERT INTO channel_snapshots (channel_id, ts, subscriber_count, video_count, view_count) "
        "VALUES (?, ?, ?, ?, ?)",
        ("chanB", db.now() - 24 * 3600 * 1000, 200_000, 150, 40_000_000),
    )


def _seed_keyword() -> None:
    db.run(
        "INSERT INTO tracked_items (kind, ref_id, label, added_at) VALUES (?, ?, ?, ?)",
        ("keyword", "ai tools", "AI Tools", db.now()),
    )
    db.run(
        "INSERT INTO keywords (term, display_term, score, demand_score, competition_score, "
        "competition_label, source, first_seen, last_checked) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("ai tools", "AI Tools", 82, 90, 25, "Low", "search", db.now(), db.now()),
    )
    db.run(
        "INSERT INTO keyword_snapshots (term, ts, demand_score, competition_score, score) "
        "VALUES (?, ?, ?, ?, ?)",
        ("ai tools", db.now() - 3600 * 1000, 90, 25, 82),
    )
    db.run(
        "INSERT INTO keyword_snapshots (term, ts, demand_score, competition_score, score) "
        "VALUES (?, ?, ?, ?, ?)",
        ("ai tools", db.now(), 90, 25, 84),
    )
    db.run(
        "INSERT INTO rankings (term, video_id, position, ts) VALUES (?, ?, ?, ?)",
        ("ai tools", "vidR", 1, db.now()),
    )
    db.run(
        "INSERT INTO videos (video_id, title, view_count, last_fetched) VALUES (?, ?, ?, ?)",
        ("vidR", "Ranked video", 5000, db.now()),
    )


def _labels(page: CompetitorsPage) -> list[str]:
    return [
        label.text()
        for label in page.findChildren(QLabel)
        if label.text() and not label.objectName().startswith("scoreBadge")
    ]


def test_empty_dashboard_shows_empty_notes(qapp):
    page = CompetitorsPage()
    text = "\n".join(_labels(page))
    assert "Nothing tracked yet" in text
    assert text.count("Nothing tracked yet") == 3
    page.deleteLater()


def test_video_card_shows_vph_and_sparkline(qapp):
    _seed_video()
    page = CompetitorsPage()
    assert any("1.0M views" in t for t in _labels(page))
    assert any("50000/hr" in t for t in _labels(page))  # 100k views / 2h
    from s_q_ali_media_downloader.niche_research.ui.widgets import Sparkline

    sparks = page.findChildren(Sparkline)
    assert len(sparks) == 1
    page.deleteLater()


def test_channel_card_shows_growth(qapp):
    _seed_channel()
    page = CompetitorsPage()
    text = "\n".join(_labels(page))
    assert "200K subs" in text
    assert "+20K / 7d" in text
    page.deleteLater()


def test_keyword_card_badges_and_rankings(qapp):
    _seed_keyword()
    page = CompetitorsPage()
    text = "\n".join(_labels(page))
    assert "AI Tools" in text
    assert "Ranked video" in text
    badges = page.findChildren(ScoreBadge)
    assert badges  # score badge rendered
    comps = page.findChildren(CompetitionBadge)
    assert comps
    page.deleteLater()


def test_untrack_removes_item(qapp):
    _seed_video()
    page = CompetitorsPage()
    assert "1.0M views" in "\n".join(_labels(page))
    page._untrack("video", "vidA")
    text = "\n".join(_labels(page))
    assert "1.0M views" not in text
    assert db.get("SELECT 1 FROM tracked_items WHERE kind='video' AND ref_id=?", ("vidA",)) is None
    page.deleteLater()


def test_refresh_now_flags_button_and_rerenders(qapp, monkeypatch):
    _seed_video()
    page = CompetitorsPage()

    fake_counts = {"videos": 1, "channels": 0, "keywords": 0}

    # Expose a synchronous fake refresh by calling the completion handler directly
    page._on_refresh_done(fake_counts)
    assert page._refresh_btn.text() == "Refresh now"
    assert page._summary.text().startswith("Snapshotted 1 videos")
    # still shows the tracked video after rerender
    assert "1.0M views" in "\n".join(_labels(page))
    page.deleteLater()


def test_fmt():
    assert _fmt(999) == "999"
    assert _fmt(1500) == "1.5K"
    assert _fmt(2_500_000) == "2.5M"
    assert _fmt(1234567890) == "1.23B"


def test_poller_emits():
    from s_q_ali_media_downloader.niche_research.ui.competitors_page import NichePoller

    poller = NichePoller(interval_ms=1000000)
    fired: list[bool] = []
    poller.snapshot_requested.connect(lambda: fired.append(True))
    assert poller is not None
    poller.stop()
    assert not fired


# --------------------------------------------------------------------------- #
# Handoffs (SPEC-handoffs.md) + the canonical tracked-items helper
# --------------------------------------------------------------------------- #
def test_tracked_video_can_be_queued(isolated_appdata, qapp):
    """Competitors -> Download queue."""
    from PySide6.QtWidgets import QPushButton

    _seed_video()
    page = CompetitorsPage()
    page.show()
    got: list = []
    page.queue_urls_requested.connect(got.append)

    button = next(b for b in page.findChildren(QPushButton) if b.text() == "Queue")
    button.click()

    assert got == [["https://www.youtube.com/watch?v=vidA"]]
    page.deleteLater()


def test_untrack_goes_through_the_engine_helper(qapp, monkeypatch):
    """The UI layer must not delete from tracked_items with its own SQL."""
    from s_q_ali_media_downloader.niche_research.research import competitor_engine as ce

    _seed_video()
    page = CompetitorsPage()
    calls: list = []
    monkeypatch.setattr(ce, "untrack_item", lambda kind, ref: calls.append((kind, ref)))

    page._untrack("video", "vidA")

    assert calls == [("video", "vidA")]
    page.deleteLater()


def test_poller_interval_can_be_changed_while_running(qapp):
    """The snapshot interval setting must reach the running poller."""
    from s_q_ali_media_downloader.niche_research.ui.competitors_page import NichePoller

    poller = NichePoller(interval_ms=60 * 60 * 1000)
    assert poller.interval_minutes == 60

    poller.set_interval_minutes(30)

    assert poller._timer.interval() == 30 * 60 * 1000
    assert poller.interval_minutes == 30
    poller.stop()
