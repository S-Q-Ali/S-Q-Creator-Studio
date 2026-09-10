"""Tests for async thumbnail loading (never blocks the GUI thread)."""

import time

from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QColor, QImage

from s_q_ali_media_downloader.niche_research.ui import widgets as w

PNG_URL = "https://img.youtube.com/vi/abc123def45/maxresdefault.jpg"


def _png_bytes(color="#d33") -> bytes:
    image = QImage(8, 8, QImage.Format.Format_RGB32)
    image.fill(QColor(color))
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data())


def test_url_candidates_generates_fallback_chain():
    assert w._url_candidates(PNG_URL) == [
        PNG_URL,
        "https://img.youtube.com/vi/abc123def45/hqdefault.jpg",
        "https://img.youtube.com/vi/abc123def45/mqdefault.jpg",
    ]
    plain = "https://example.com/thumb.png"
    assert w._url_candidates(plain) == [plain]


def test_video_thumb_accepts_async_image(qapp, isolated_appdata):
    thumb = w.VideoThumb(PNG_URL, "T")
    assert thumb._pixmap is None  # still loading, nothing painted yet
    thumb._on_image(PNG_URL, _png_bytes())
    assert thumb._pixmap is not None and not thumb._pixmap.isNull()
    thumb.deleteLater()


def test_video_thumb_ignores_image_for_other_url(qapp, isolated_appdata):
    thumb = w.VideoThumb(PNG_URL, "T")
    thumb._on_image("https://other/url.jpg", _png_bytes())
    assert thumb._pixmap is None
    thumb.deleteLater()


def test_avatar_uses_cached_image_without_network(qapp, monkeypatch, isolated_appdata):
    data = _png_bytes()
    w._write_cached_image(PNG_URL, data)

    def boom(*args, **kwargs):
        raise AssertionError("network fetch must not happen when cache hit")

    monkeypatch.setattr(w, "_fetch_image_bytes", boom)
    avatar = w.AvatarThumbnail(PNG_URL, "My Channel")
    assert avatar._pixmap is not None and not avatar._pixmap.isNull()
    avatar.deleteLater()


def test_avatar_empty_url_keeps_initials_fallback(qapp, isolated_appdata):
    avatar = w.AvatarThumbnail("", "My Channel")
    assert avatar._pixmap is None
    avatar.deleteLater()


def test_loader_delivers_bytes_async(qapp, monkeypatch, isolated_appdata):
    monkeypatch.setattr(w, "_fetch_image_bytes", lambda url, timeout=8: _png_bytes())
    received = {}

    def on_image(url, data):
        received["url"] = url
        received["data"] = data

    loader = w.ThumbLoader()
    loader.finished.connect(on_image)
    loader.start(PNG_URL)

    deadline = time.time() + 3.0
    while "data" not in received and time.time() < deadline:
        qapp.processEvents()
        time.sleep(0.01)

    assert received.get("url") == PNG_URL
    assert received.get("data") is not None