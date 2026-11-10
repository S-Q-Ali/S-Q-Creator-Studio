"""Unit tests for multi-aspect-ratio conversions in reframe module (9:16, 1:1, 4:5)."""

import pytest

from s_q_ali_media_downloader.core import reframe


def test_crop_window_aspect_ratios():
    # 1080p source (1920x1080)
    w_916, h_916 = reframe.crop_window(1920, 1080, aspect_ratio="9:16")
    assert w_916 == 594
    assert h_916 == 1056
    assert w_916 / h_916 == pytest.approx(9 / 16)

    w_11, h_11 = reframe.crop_window(1920, 1080, aspect_ratio="1:1")
    assert w_11 == 1056
    assert h_11 == 1056
    assert w_11 / h_11 == 1.0

    w_45, h_45 = reframe.crop_window(1920, 1080, aspect_ratio="4:5")
    assert w_45 == 832
    assert h_45 == 1040
    assert w_45 / h_45 == pytest.approx(4 / 5)


def test_crop_window_too_narrow_raises():
    with pytest.raises(ValueError):
        reframe.crop_window(500, 1000, aspect_ratio="1:1")


def test_output_size_aspect_ratios():
    # 1080p source
    assert reframe.output_size(1080, aspect_ratio="9:16") == (1080, 1920)
    assert reframe.output_size(1080, aspect_ratio="1:1") == (1080, 1080)
    assert reframe.output_size(1080, aspect_ratio="4:5") == (1080, 1350)


def test_vertical_output_path_suffixes(tmp_path):
    video = str(tmp_path / "clip.mp4")
    assert reframe.vertical_output_path(video, aspect_ratio="9:16").endswith("clip_9x16.mp4")
    assert reframe.vertical_output_path(video, aspect_ratio="1:1").endswith("clip_1x1.mp4")
    assert reframe.vertical_output_path(video, aspect_ratio="4:5").endswith("clip_4x5.mp4")


def test_is_landscape_aspect_ratios():
    # 16:9 1080p video
    assert reframe.is_landscape(1920, 1080, aspect_ratio="9:16") is True
    assert reframe.is_landscape(1920, 1080, aspect_ratio="1:1") is True
    assert reframe.is_landscape(1920, 1080, aspect_ratio="4:5") is True

    # 1:1 square video
    assert reframe.is_landscape(1080, 1080, aspect_ratio="9:16") is True
    assert reframe.is_landscape(1080, 1080, aspect_ratio="1:1") is False
    assert reframe.is_landscape(1080, 1080, aspect_ratio="4:5") is True

    # 9:16 vertical video
    assert reframe.is_landscape(1080, 1920, aspect_ratio="9:16") is False
    assert reframe.is_landscape(1080, 1920, aspect_ratio="1:1") is False
    assert reframe.is_landscape(1080, 1920, aspect_ratio="4:5") is False


def test_vertical_studio_page_ratio_selection(qapp, tmp_path, monkeypatch):
    from s_q_ali_media_downloader.ui.vertical_studio_page import VerticalStudioPage
    page = VerticalStudioPage()
    # Initially combo_ratio is disabled if vertical is not checked
    page.vertical.setChecked(False)
    assert page.combo_ratio.isEnabled() is False

    page.vertical.setChecked(True)
    assert page.combo_ratio.isEnabled() is True

    # Check ratio options
    items = [page.combo_ratio.itemText(i) for i in range(page.combo_ratio.count())]
    assert "9:16 (Vertical)" in items
    assert "1:1 (Square)" in items
    assert "4:5 (Portrait)" in items

    from PySide6.QtCore import QThread, Signal
    seen = {"calls": []}

    class FakeThread(QThread):
        file_started = Signal(int, str)
        progress = Signal(float, str)
        log = Signal(str)
        finished_all = Signal()

        def __init__(self, files, **kwargs):
            super().__init__()
            seen["calls"].append((files, kwargs))

        def start(self):
            pass

        def isRunning(self):
            return False

    monkeypatch.setattr("s_q_ali_media_downloader.ui.vertical_studio_page.LocalVideoThread", FakeThread)

    clip = tmp_path / "video.mp4"
    clip.write_bytes(b"dummy")
    page.paths = [str(clip)]
    page.combo_ratio.setCurrentText("1:1 (Square)")

    page.run()
    assert len(seen["calls"]) == 1
    files, kwargs = seen["calls"][0]
    assert files == [str(clip)]
    assert kwargs["vertical"] is True
    assert kwargs["aspect_ratio"] == "1:1"
    assert "reframe 1:1" in page.log.toPlainText()

