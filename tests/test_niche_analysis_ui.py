"""Offscreen tests for the Settings page + Analysis modal."""

from __future__ import annotations

import pytest

from s_q_ali_media_downloader.niche_research.research import ai_analysis_engine as ai
from s_q_ali_media_downloader.niche_research.storage import db
from s_q_ali_media_downloader.niche_research.ui.analysis_modal import AnalysisModal
from s_q_ali_media_downloader.niche_research.ui.settings_page import SettingsPage


@pytest.fixture(autouse=True)
def _db(isolated_appdata):
    db.configure(None)
    yield
    db.close_db()


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


def test_modal_renders_not_analyzed(qapp, monkeypatch):
    monkeypatch.setattr(ai, "load_channel_analysis_data", lambda cid, **kw: _sample_data(False))
    modal = AnalysisModal("UCabc")
    modal._on_channel_data(_sample_data(False))
    assert modal._channel_row is not None
    assert modal._data["channel"]["title"] == "Test Channel"
    # not analyzed -> empty-state + analyze button visible
    assert modal._analysis_stack.currentIndex() == 0
    assert modal._analyze_btn.text() == "Create Similar Channel"
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
    modal._set_tab("thumbnail")
    assert modal._tab_stack.currentIndex() == 4
    assert modal._style_buttons["bold"].property("active") is True
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
