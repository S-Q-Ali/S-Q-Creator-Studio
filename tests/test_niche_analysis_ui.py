"""Offscreen tests for the Settings page + Analysis modal."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QLabel, QPushButton

from s_q_ali_media_downloader.niche_research.research import ai_analysis_engine as ai
from s_q_ali_media_downloader.niche_research.storage import db
from s_q_ali_media_downloader.niche_research.tools import youtube_client as yc
from s_q_ali_media_downloader.niche_research.ui.analysis_modal import AnalysisModal
from s_q_ali_media_downloader.niche_research.ui.settings_page import SettingsPage


@pytest.fixture(autouse=True)
def _db(isolated_appdata):
    db.configure(None)
    yield
    db.close_db()


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """The modal starts a channel-data worker on construction; stub the
    network call so no test reaches YouTube and leaves a live thread
    behind."""
    monkeypatch.setattr(
        ai, "load_channel_analysis_data", lambda cid, **kw: _sample_data(False)
    )


# --------------------------------------------------------------------------- #
# Regression (2026-10): the modal must never abort the process on close
# --------------------------------------------------------------------------- #
class _SlowWorker(QThread):
    """A worker that keeps running until it is asked to stop.

    It polls isInterruptionRequested() like the real workers do, so stopping
    it never has to fall back to terminate() — killing a live thread can
    corrupt the interpreter.
    """

    def run(self) -> None:  # pragma: no cover - timing dependent
        while not self.isInterruptionRequested():
            self.msleep(50)


def test_closing_the_modal_joins_its_workers(qapp, monkeypatch):
    """QDialog.reject() hides the dialog without emitting closeEvent, so the
    workers have to be joined there too — otherwise PySide6 aborts with
    "QThread: Destroyed while thread is still running"."""
    monkeypatch.setattr(ai, "load_channel_analysis_data", lambda cid, **kw: _sample_data(False))
    modal = AnalysisModal("UCabc")
    worker = _SlowWorker(modal)
    modal._track_worker(worker)
    worker.start()
    assert worker.isRunning() is True

    modal.reject()

    assert worker.isRunning() is False


def test_is_analyzed_is_true_without_scripts(isolated_appdata):
    """An analysis whose model returned no scripts is still an analysis —
    the modal used to fall back to "Ready to Analyze" and charge twice."""
    db.run(
        "INSERT OR REPLACE INTO similar_channel_analysis "
        "(source_channel_id, target_channel_id, similarity_score, analysis_json, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        ("UCabc", "UCabc", 100, '{"contentType": ["educational"]}', db.now()),
    )

    assert ai.is_analyzed("UCabc") is True


# --------------------------------------------------------------------------- #
# Regression (2026-10): one click, one paid analysis
# --------------------------------------------------------------------------- #
def test_the_analyze_button_is_disabled_while_the_analysis_runs(qapp, monkeypatch):
    """The "Analyze this channel" button was a local variable, so it was never
    disabled: every click started another provider call, and the button that
    got disabled was the unrelated "Create Similar Channel" one."""
    from s_q_ali_media_downloader.niche_research.ui import analysis_modal as am

    monkeypatch.setattr(ai, "load_channel_analysis_data", lambda cid, **kw: _sample_data(False))

    starts: list[str] = []

    class _FakeWorker(QThread):
        progress = Signal(str)
        done = Signal(object)
        failed = Signal(str)

        def __init__(self, channel_id, parent=None):
            super().__init__(parent)
            starts.append(channel_id)

        def run(self):
            pass

    monkeypatch.setattr(am, "AnalyzeWorker", _FakeWorker)

    modal = AnalysisModal("UCabc")
    analyze_btn = modal._run_analysis_btn
    similar_btn = modal._similar_btn

    assert analyze_btn.isEnabled() is True
    assert "Analyze" in analyze_btn.text()

    modal._start_analyze()

    assert analyze_btn.isEnabled() is False
    assert "Analyzing" in analyze_btn.text()
    # the similar-channel button keeps its own label and stays clickable
    assert similar_btn.text() == "Create Similar Channel"
    assert similar_btn.isEnabled() is True

    modal._start_analyze()  # a second click must not buy a second analysis

    assert len(starts) == 1


def test_the_modal_can_cancel_a_running_analysis(qapp, monkeypatch):
    """An analysis that is already running has to be stoppable — the only
    way out used to be closing the dialog, which discarded a paid call."""
    from s_q_ali_media_downloader.niche_research.ui import analysis_modal as am

    monkeypatch.setattr(ai, "load_channel_analysis_data", lambda cid, **kw: _sample_data(False))

    class _FakeWorker(QThread):
        progress = Signal(str)
        done = Signal(object)
        failed = Signal(str)

        def __init__(self, channel_id, parent=None):
            super().__init__(parent)

        def run(self):
            pass

    monkeypatch.setattr(am, "AnalyzeWorker", _FakeWorker)

    modal = AnalysisModal("UCabc")

    assert modal._cancel_analysis_btn.isEnabled() is False

    modal._start_analyze()

    assert modal._cancel_analysis_btn.isEnabled() is True

    modal._cancel_analysis()

    assert modal._analysis_worker.isInterruptionRequested() is True


def test_the_modal_can_queue_the_channel_uploads(qapp):
    """AI Analysis -> download queue: the newest uploads of the analysed
    channel can be queued without leaving the modal."""
    modal = AnalysisModal("UCabc")
    queued: list[list[str]] = []
    modal.queue_urls_requested.connect(queued.append)

    modal._on_channel_data(_sample_data(True))

    button = next(
        (
            b
            for b in modal._channel_row.findChildren(QPushButton)
            if "Queue" in b.text()
        ),
        None,
    )
    assert button is not None, "the analysis modal has no Queue button"
    assert button.isEnabled() is True

    button.click()

    assert queued and "watch?v=v1" in queued[0][0]


def test_the_modal_can_track_the_analysed_channel(qapp):
    """AI Analysis -> Competitors: the analysed channel can be tracked."""
    modal = AnalysisModal("UCabc")
    tracked: list[str] = []
    modal.track_channel_requested.connect(tracked.append)

    modal._on_channel_data(_sample_data(True))

    button = next(
        (
            b
            for b in modal._channel_row.findChildren(QPushButton)
            if "Track" in b.text()
        ),
        None,
    )
    assert button is not None, "the analysis modal has no Track button"
    assert button.isEnabled() is True

    button.click()

    assert tracked == ["UCabc"]


def test_the_modal_can_open_the_analysed_channel_on_the_scorecard(qapp):
    """AI Analysis -> Scorecard: the analysed channel itself must be
    scoreable — the button used to exist only for similar channels."""
    modal = AnalysisModal("UCabc")
    opened: list[str] = []
    modal.open_scorecard_requested.connect(opened.append)

    modal._on_channel_data(_sample_data(True))

    button = next(
        (
            b
            for b in modal._channel_row.findChildren(QPushButton)
            if "Scorecard" in b.text()
        ),
        None,
    )
    assert button is not None, "the analysis modal has no Scorecard button"
    assert button.isEnabled() is True

    button.click()

    assert opened == ["UCabc"]


def test_is_analyzed_is_false_for_a_fresh_channel(isolated_appdata):
    assert ai.is_analyzed("UCnothing") is False



def _sample_data(analyzed: bool = False) -> dict:
    analysis = {
        "strategy": {
            "contentType": ["educational"],
            "postingSchedule": "2-3 per week",
            "thumbnailStyle": "Bold",
            "titleFormula": "How to",
            "tagStrategy": ["tech"],
            "uniqueSellingPoints": ["Deep dives"],
        },
        "contentIdeas": [
            {
                "title": "Idea one",
                "description": "desc",
                "contentType": "video",
                "estimatedViews": "high",
                "difficulty": "easy",
            },
        ],
        "scripts": [
            {
                "title": "Script one",
                "hook": "Hook",
                "intro": "Intro",
                "bodySections": ["Body"],
                "outro": "Outro",
                "estimatedDuration": 601,
            },
        ],
        "growthBlueprint": {
            "30day": {"goals": ["10 videos"], "actions": ["Post weekly"], "metrics": ["views"]},
            "60day": {"goals": [], "actions": [], "metrics": []},
            "90day": {"goals": [], "actions": [], "metrics": []},
        },
    }
    return {
        "channel": {
            "channelId": "UCabc",
            "title": "Test Channel",
            "description": "About",
            "thumbnailUrl": "",
            "subscriberCount": 200_000,
            "viewCount": 50_000_000,
            "videoCount": 120,
            "publishedAt": "",
            "country": "US",
            "topicCategories": [],
            "channelTags": [],
        },
        "trending": {
            "viralScore": 85,
            "growthRate": 12.5,
            "viewSubRatio": 3.4,
            "isNewlyCreated": True,
            "categoryName": "Tech",
        },
        "analyzed": analyzed,
        "analysis": analysis if analyzed else None,
        "recentVideos": [
            {
                "videoId": "v1",
                "title": "Recent one",
                "thumbnailUrl": "",
                "viewCount": 10_000,
                "publishedAt": "2026-01-01",
            },
        ],
    }


def test_modal_renders_recent_video_tiles(qapp, monkeypatch):
    from s_q_ali_media_downloader.niche_research.ui.widgets import VideoThumb

    monkeypatch.setattr(
        ai, "load_channel_analysis_data", lambda cid, **kw: _sample_data(False)
    )
    data = _sample_data(False)
    data["recentVideos"] = [
        {
            "videoId": f"v{i}",
            "title": f"Recent {i}",
            "thumbnailUrl": "",
            "viewCount": 1000 * i,
            "publishedAt": f"2026-01-0{i + 1}",
        }
        for i in range(8)
    ]
    modal = AnalysisModal("UCabc")
    modal._on_channel_data(data)
    assert modal._recent_cap.text() == "Recent Videos (8)"
    assert modal._recent_grid.count() == 8
    assert len(modal.findChildren(VideoThumb)) == 8
    modal.reject()
    modal.deleteLater()


def test_modal_content_is_scrollable(qapp, monkeypatch):
    from PySide6.QtWidgets import QScrollArea

    monkeypatch.setattr(
        ai, "load_channel_analysis_data", lambda cid, **kw: _sample_data(True)
    )
    modal = AnalysisModal("UCabc")
    modal._on_channel_data(_sample_data(True))
    scrolls = modal.findChildren(QScrollArea)
    assert any(scroll.widget() is modal._stack for scroll in scrolls)
    modal.reject()
    modal.deleteLater()


def test_modal_minimum_size_and_resize(qapp, monkeypatch):
    monkeypatch.setattr(
        ai, "load_channel_analysis_data", lambda cid, **kw: _sample_data(True)
    )
    modal = AnalysisModal("UCabc")
    modal._on_channel_data(_sample_data(True))
    assert modal.minimumSize().width() >= 600
    assert modal.minimumSize().height() >= 500
    modal.resize(720, 540)
    qapp.processEvents()
    assert modal.width() == 720
    modal.reject()
    modal.deleteLater()


def test_settings_page_saves_keys(qapp):
    page = SettingsPage()
    page._keys["aihubmix_api_key"].setText("sk-abc")
    page._save()
    assert db.get_setting("aihubmix_api_key") == "sk-abc"
    assert ai.get_providers()[0]["name"] == "aihubmix"
    page.deleteLater()


def test_settings_page_primary_provider_order(qapp):
    page = SettingsPage()
    page._keys["groq_api_key"].setText("k")
    page._keys["aihubmix_api_key"].setText("k")
    idx = page._default_provider.findData("groq")
    page._default_provider.setCurrentIndex(idx)
    page._save()
    assert db.get_setting("ai_primary_provider") == "groq"
    assert ai.get_providers()[0]["name"] == "groq"
    page.deleteLater()


def test_settings_page_saves_youtube_api_key(qapp):
    page = SettingsPage()
    page._keys["youtube_api_key"].setText("AIzaSyYouTubeTest")
    page._save()
    assert db.get_setting("youtube_api_key") == "AIzaSyYouTubeTest"
    assert yc.get_api_key() == "AIzaSyYouTubeTest"
    page.deleteLater()


def test_settings_page_stores_the_cookie_file(qapp, tmp_path):
    """The cookies.txt escape hatch has to be configurable in the UI."""
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
    page = SettingsPage()
    page._cookies_edit.setText(str(cookies))
    page._save()
    assert db.get_setting("youtube_cookies_file") == str(cookies)
    page.deleteLater()


def test_settings_page_shows_the_stored_cookie_file(qapp, tmp_path):
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("x", encoding="utf-8")
    db.set_setting("youtube_cookies_file", str(cookies))
    page = SettingsPage()
    assert page._cookies_edit.text() == str(cookies)
    page.deleteLater()


def test_settings_page_clears_the_cookie_file(qapp):
    db.set_setting("youtube_cookies_file", "C:/tmp/cookies.txt")
    page = SettingsPage()
    page._clear_cookies()
    assert db.get_setting("youtube_cookies_file") == ""
    assert page._cookies_edit.text() == ""
    page.deleteLater()


def test_settings_provider_combo_is_visible_in_layout(qapp):
    page = SettingsPage()
    page.show()
    qapp.processEvents()
    assert page._default_provider.width() > 0
    assert page._default_provider.isVisible()
    assert page._keys["youtube_api_key"].isVisible()
    page.deleteLater()


def _stats_map(modal) -> dict:
    result = {}
    for i in range(modal._stats_row.count()):
        tile = modal._stats_row.itemAt(i).widget()
        val = next(
            l for l in tile.findChildren(QLabel) if l.objectName() == "statTileValue"
        )
        cap = next(
            l for l in tile.findChildren(QLabel) if l.objectName() == "statTileLabel"
        )
        result[cap.text()] = val.text()
    return result


def test_modal_stats_show_dash_for_unknown(qapp, monkeypatch):
    monkeypatch.setattr(
        ai, "load_channel_analysis_data", lambda cid, **kw: _sample_data(False)
    )
    data = _sample_data(False)
    # keyless discovery leaves exact stats unknown -> honest "—", never 0
    data["channel"]["subscriberCount"] = None
    data["channel"]["viewCount"] = None
    data["channel"]["videoCount"] = None
    data["trending"] = {"growthRate": None, "viewSubRatio": None, "categoryName": "Tech"}
    modal = AnalysisModal("UCabc")
    modal._on_channel_data(data)
    tiles = _stats_map(modal)
    assert tiles["Videos"] == "—"
    assert tiles["Subscribers"] == "—"
    assert tiles["Total Views"] == "—"
    assert "— growth (30d)" in " ".join(t.text() for t in modal.findChildren(QLabel))
    modal.reject()
    modal.deleteLater()


def test_modal_renders_not_analyzed(qapp, monkeypatch):
    monkeypatch.setattr(ai, "load_channel_analysis_data", lambda cid, **kw: _sample_data(False))
    modal = AnalysisModal("UCabc")
    modal._on_channel_data(_sample_data(False))
    assert modal._channel_row is not None
    assert modal._data["channel"]["title"] == "Test Channel"
    # not analyzed -> empty-state + analyze button visible
    assert modal._analysis_stack.currentIndex() == 0
    assert modal._similar_btn.text() == "Create Similar Channel"
    # recent video tile title present
    assert len(modal._data["recentVideos"]) == 1
    modal.reject()
    modal.deleteLater()


def test_modal_renders_analyzed_tabs(qapp, monkeypatch):
    monkeypatch.setattr(ai, "load_channel_analysis_data", lambda cid, **kw: _sample_data(True))
    modal = AnalysisModal("UCabc")
    modal._on_channel_data(_sample_data(True))
    assert modal._analysis_stack.currentIndex() == 1
    # Ideas tab button carries a count
    assert modal._tab_buttons["ideas"].text() == "Content Ideas (1)"
    modal.reject()
    modal.deleteLater()


def test_modal_set_tab_switches(qapp, monkeypatch):
    monkeypatch.setattr(ai, "load_channel_analysis_data", lambda cid, **kw: _sample_data(True))
    modal = AnalysisModal("UCabc")
    modal._on_channel_data(_sample_data(True))
    modal._set_tab("scripts")
    assert modal._tab_stack.currentIndex() == 2
    assert modal._analysis_stack.currentIndex() == 1
    assert modal._style_buttons["bold"].property("active") is True
    modal.reject()
    modal.deleteLater()


def test_thumbnail_tab_is_reachable_without_an_analysis(qapp, monkeypatch):
    """The thumbnail generator used to live behind the AI analysis, so a
    fresh channel could not generate a thumbnail without paying for (and
    waiting on) a full chat analysis first."""
    monkeypatch.setattr(ai, "load_channel_analysis_data", lambda cid, **kw: _sample_data(False))
    modal = AnalysisModal("UCabc")
    modal._on_channel_data(_sample_data(False))
    assert modal._analysis_stack.currentIndex() == 0

    # The not-analyzed card offers the thumbnail generator directly.
    buttons = [
        b
        for b in modal._analysis_stack.widget(0).findChildren(QPushButton)
        if "Thumbnail" in b.text()
    ]
    assert buttons
    buttons[0].click()
    assert modal._analysis_stack.currentIndex() == 2
    # the thumbnail page is the one on screen, with its own controls
    thumb_page = modal._analysis_stack.widget(2)
    assert thumb_page is not None
    assert thumb_page.findChildren(QPushButton)
    modal.reject()
    modal.deleteLater()


def test_modal_show_thumbnail_preview(qapp, monkeypatch):
    monkeypatch.setattr(ai, "load_channel_analysis_data", lambda cid, **kw: _sample_data(True))
    modal = AnalysisModal("UCabc")
    modal._on_channel_data(_sample_data(True))
    modal._thumb_title.setText("My title")
    result = {"success": True, "imageData": _tiny_png_data_uri()}
    modal._on_thumbnail_done(result)
    assert not modal._download_btn.isHidden()
    assert modal._preview.pixmap() is not None
    modal.reject()
    modal.deleteLater()


def test_modal_thumbnail_error(qapp, monkeypatch):
    monkeypatch.setattr(ai, "load_channel_analysis_data", lambda cid, **kw: _sample_data(True))
    modal = AnalysisModal("UCabc")
    modal._on_channel_data(_sample_data(True))
    modal._on_thumbnail_done({"success": False, "error": "no key"})
    assert "no key" in modal._thumb_error.text()
    modal.reject()
    modal.deleteLater()


def test_modal_text_is_selectable(qapp, monkeypatch):
    from PySide6.QtCore import Qt

    monkeypatch.setattr(
        ai, "load_channel_analysis_data", lambda cid, **kw: _sample_data(True)
    )
    modal = AnalysisModal("UCabc")
    modal._on_channel_data(_sample_data(True))
    sel = Qt.TextInteractionFlag.TextSelectableByMouse
    labels = modal.findChildren(QLabel)
    for needle in (
        "How to",
        "2-3 per week",
        "Idea one",
        "Script one",
        "10 videos",
        "Recent one",
        "Test Channel",
    ):
        matches = [label for label in labels if needle in label.text()]
        assert matches, needle
        assert all(bool(label.textInteractionFlags() & sel) for label in matches), needle
    modal.reject()
    modal.deleteLater()


def test_modal_re_render_after_analyze_rebuilds_layouts(qapp, monkeypatch):
    monkeypatch.setattr(
        ai, "load_channel_analysis_data", lambda cid, **kw: _sample_data(True)
    )
    modal = AnalysisModal("UCabc")
    modal._on_channel_data(_sample_data(True))
    # The Analyze -> reload path renders the same modal a second time. The
    # trending row carries a trailing stretch spacer that used to make
    # _clear_layout crash mid-rebuild.
    modal._on_channel_data(_sample_data(True))
    texts = [label.text() for label in modal.findChildren(QLabel)]
    assert any("2-3 per week" in text for text in texts)
    assert any("Script one" in text for text in texts)
    modal.reject()
    modal.deleteLater()


def test_modal_fmt_duration():
    assert AnalysisModal._fmt_duration(0) == "0:00"
    assert AnalysisModal._fmt_duration(601) == "10:01"
    assert AnalysisModal._fmt_duration(3599) == "59:59"


def _tiny_png_data_uri() -> str:
    import base64
    import struct
    import zlib

    def chunk(tag: bytes, data: bytes) -> bytes:
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    width = height = 1
    raw = b"".join(b"\x00" + b"\x00\x00\x00\x00\x00\x00\x00" for _ in range(height))
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )
    return "data:image/png;base64," + base64.b64encode(png).decode()
