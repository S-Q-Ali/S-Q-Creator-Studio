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


def test_scorecard_offers_channel_analysis(isolated_appdata, qapp):
    """A scored channel must be analysable without leaving the page."""
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
        seo=se.compute_channel_seo_score(ChannelInfo(channel_id="UCchan", title="My Channel")),
        recent_videos=[],
        tracked=False,
    )
    page = ScorecardPage()
    page.show()
    got: list = []
    page.analyze_requested.connect(got.append)
    page._on_done(result)
    qapp.processEvents()

    buttons = {b.text(): b for b in page._content.findChildren(QPushButton)}
    assert "Analyze channel" in buttons
    buttons["Analyze channel"].click()
    assert got == ["UCchan"]
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


def test_scorecard_survives_repeated_failures(isolated_appdata, qapp):
    """The shared empty-state widget used to be deleted and then re-added,
    so the second failure raised "Internal C++ object already deleted"."""
    from PySide6.QtCore import QCoreApplication, QEvent

    db.configure(None)
    page = ScorecardPage()
    page.show()
    for _ in range(4):
        page._on_failed("bad url")
        # Process the deferred widget deletions, like the running event loop does.
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        qapp.processEvents()
    assert page._score_btn.isEnabled() is True
    assert "Lookup failed" in page._status.text()
    db.close_db()


def test_scorecard_survives_repeated_mode_switches(isolated_appdata, qapp):
    from PySide6.QtCore import QCoreApplication, QEvent

    db.configure(None)
    page = ScorecardPage()
    page.show()
    for _ in range(3):
        page._set_mode("channel")
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        qapp.processEvents()
        page._set_mode("video")
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        qapp.processEvents()
    assert page._mode == "video"
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


def test_focus_keyword_reaches_the_lookup(isolated_appdata, qapp, monkeypatch):
    """The focus keyword must be forwarded to the engine, otherwise the
    keyword-placement checks can never run."""
    db.configure(None)
    seen = {}

    def fake_lookup_video(url, *, cookiefile=None, focus_keyword=""):
        seen["url"] = url
        seen["keyword"] = focus_keyword
        return _video_result()

    monkeypatch.setattr(se, "lookup_video", fake_lookup_video)

    page = ScorecardPage()
    page.show()
    page._url_edit.setText("https://youtube.com/watch?v=vid1")
    page._keyword_edit.setText("tech")
    page._run_lookup()
    page._worker.wait(5000)
    qapp.processEvents()

    assert seen["url"] == "https://youtube.com/watch?v=vid1"
    assert seen["keyword"] == "tech"
    db.close_db()


# --------------------------------------------------------------------------- #
# Handoffs (SPEC-handoffs.md) + the canonical tracked-items helper
# --------------------------------------------------------------------------- #
def test_scorecard_queue_button_emits_the_video_url(isolated_appdata, qapp):
    """Scorecard -> Download queue."""
    db.configure(None)
    page = ScorecardPage()
    page.show()
    got: list = []
    page.queue_urls_requested.connect(got.append)
    page._on_done(_video_result())
    qapp.processEvents()

    button = next(b for b in page._content.findChildren(QPushButton) if b.text() == "Queue")
    button.click()

    assert got == [["https://www.youtube.com/watch?v=vid1"]]
    db.close_db()


def test_scorecard_open_on_youtube_button_emits_the_url(isolated_appdata, qapp):
    """Scorecard -> YouTube."""
    db.configure(None)
    page = ScorecardPage()
    page.show()
    got: list = []
    page.open_browser_requested.connect(got.append)
    page._on_done(_video_result())
    qapp.processEvents()

    button = next(
        b for b in page._content.findChildren(QPushButton) if b.text() == "Open on YouTube"
    )
    button.click()

    assert got == ["https://www.youtube.com/watch?v=vid1"]
    db.close_db()


def test_scorecard_buttons_are_disabled_with_a_reason(isolated_appdata, qapp):
    """A button that cannot run is disabled and says why."""
    db.configure(None)
    result = _video_result()
    result.video.pop("video_id")
    page = ScorecardPage()
    page.show()
    page._on_done(result)
    qapp.processEvents()

    buttons = {
        b.text(): b
        for b in page._content.findChildren(QPushButton)
        if b.text() in ("Queue", "Open on YouTube", "Track video")
    }
    assert set(buttons) == {"Queue", "Open on YouTube", "Track video"}
    for button in buttons.values():
        assert button.isEnabled() is False
        assert button.toolTip(), "a disabled button must explain why"
    db.close_db()


def test_scorecard_track_button_uses_the_canonical_helper(isolated_appdata, qapp, monkeypatch):
    """The UI layer must not insert into tracked_items with its own SQL."""
    from s_q_ali_media_downloader.niche_research.research import competitor_engine as ce

    db.configure(None)
    calls: list = []
    monkeypatch.setattr(
        ce, "track_item", lambda kind, ref, label="": calls.append((kind, ref, label))
    )

    page = ScorecardPage()
    page.show()
    page._on_done(_video_result())
    qapp.processEvents()

    track = next(b for b in page._content.findChildren(QPushButton) if b.text() == "Track video")
    track.click()

    assert calls == [("video", "vid1", "Amazing Tech Video")]
    db.close_db()

