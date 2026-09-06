"""Offscreen tests for the Scorecard page."""

from PySide6.QtWidgets import QLabel, QPushButton

from s_q_ali_media_downloader.niche_research.research import scorecard_engine as se
from s_q_ali_media_downloader.niche_research.storage import db
from s_q_ali_media_downloader.niche_research.tools.youtube_client import ChannelInfo
from s_q_ali_media_downloader.niche_research.ui.scorecard_page import ScorecardPage


def _video_result():
    return se.VideoLookupResult(
        video={
            "video_id": "vid1",
            "channel_id": "UCc1",
            "channel_title": "Chan",
            "title": "Amazing Tech Video",
            "description": "desc",
            "published_at": "2026-09-01T00:00:00Z",
            "duration_seconds": 612,
            "thumbnail_url": "",
            "tags": ["tech", "ai"],
            "view_count": 50_000,
            "like_count": 900,
            "comment_count": 100,
        },
        channel={
            "channel_id": "UCc1",
            "title": "Chan",
            "thumbnail_url": "",
            "subscriber_count": 900,
        },
        seo=se.compute_seo_score(
            {
                "title": "Amazing Tech Video",
                "description": "desc",
                "tags": ["tech", "ai"],
                "view_count": 50_000,
                "like_count": 900,
                "comment_count": 100,
                "published_at": "2026-09-01T00:00:00Z",
            }
        ),
        vph=se.VphResult(vph=None, window_hours=0, error="Need at least two snapshots"),
        tracked=False,
    )


def test_scorecard_renders_video(isolated_appdata, qapp):
    db.configure(None)
    page = ScorecardPage()
    page.resize(1000, 750)
    page.show()
    page._on_done(_video_result())
    qapp.processEvents()

    labels = [l.text() for l in page._content.findChildren(QLabel)]
    assert any("Amazing Tech Video" in t for t in labels)
    assert any("VPH (24h)" in t for t in labels)
    assert any("50.0K" in t for t in labels)
    assert any("Tags (2)" in t for t in labels)

    buttons = page._content.findChildren(QPushButton)
    assert any(b.text() == "Track video" for b in buttons)
    db.close_db()


def test_scorecard_tracks_video(isolated_appdata, qapp):
    db.configure(None)
    page = ScorecardPage()
    page.show()
    page._on_done(_video_result())
    qapp.processEvents()

    track = next(b for b in page._content.findChildren(QPushButton) if b.text() == "Track video")
    track.click()
    qapp.processEvents()
    row = db.get("SELECT * FROM tracked_items WHERE kind='video' AND ref_id='vid1'")
    assert row is not None
    assert track.text() == "Tracking"
    assert track.isEnabled() is False
    db.close_db()


def test_scorecard_renders_channel(isolated_appdata, qapp):
    db.configure(None)
    result = se.ChannelLookupResult(
        channel={
            "channel_id": "UCchan",
            "title": "My Channel",
            "description": "hello",
            "thumbnail_url": "",
            "subscriber_count": 123_456,
            "video_count": 200,
            "view_count": 5_000_000,
        },
        seo=se.compute_channel_seo_score(
            ChannelInfo(
                channel_id="UCchan",
                title="My Channel",
                description="hello",
                subscriber_count=123_456,
            )
        ),
        recent_videos=[
            {
                "video_id": "u1",
                "title": "First video",
                "published_at": "2026-09-01T00:00:00Z",
                "view_count": 500,
            }
        ],
        tracked=False,
    )
    page = ScorecardPage()
    page.resize(1000, 750)
    page.show()
    page._on_done(result)
    qapp.processEvents()

    labels = [l.text() for l in page._content.findChildren(QLabel)]
    assert any("My Channel" in t for t in labels)
    assert any("123.5K" in t for t in labels)
    assert any("First video" in t for t in labels)
    buttons = page._content.findChildren(QPushButton)
    assert any(b.text() == "Track channel" for b in buttons)
    db.close_db()


def test_scorecard_placeholder_and_failure(isolated_appdata, qapp):
    db.configure(None)
    page = ScorecardPage()
    page.show()
    assert page._empty.isVisible()
    page._on_failed("bad url")
    assert "Lookup failed" in page._status.text()
    assert page._score_btn.isEnabled() is True
    db.close_db()


def test_mode_toggle(isolated_appdata, qapp):
    db.configure(None)
    page = ScorecardPage()
    page.show()
    assert page._mode == "video"
    page._set_mode("channel")
    assert page._mode == "channel"
    assert "channel" in page._url_edit.placeholderText().lower()
    assert page._video_btn.property("active") is False
    assert page._channel_btn.property("active") is True
    db.close_db()


def test_fmt_duration():
    from s_q_ali_media_downloader.niche_research.ui.scorecard_page import _fmt_duration

    assert _fmt_duration(612) == "10:12"
    assert _fmt_duration(3661) == "1:01:01"
    assert _fmt_duration(0) == "0:00"
