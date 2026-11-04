"""The download quality: the default, the container and what the card says.

A link should come down at the best resolution the source really offers, up
to 4K, and the user should be able to see what arrived. These tests cover
the three pieces that decide it - the default the settings page starts on,
the container the merge ends up in, and the label the queue card shows.
"""

import pytest
from PySide6.QtCore import QSettings

from s_q_ali_media_downloader.engine import (
    DEFAULT_QUALITY,
    QUALITY_OPTIONS,
    DownloadThread,
    codec_aware_format_selector,
    merge_container_for,
    quality_label,
)
from s_q_ali_media_downloader.ui.settings_page import SettingsPage
from s_q_ali_media_downloader.ui.widgets import Job, JobCard


# ---------------------------------------------------------------------- #
# The default
# ---------------------------------------------------------------------- #
def test_the_default_quality_is_the_best_up_to_4k():
    assert DEFAULT_QUALITY == "Best up to 4K"
    assert DEFAULT_QUALITY in QUALITY_OPTIONS


def test_the_default_caps_at_2160_and_not_below():
    spec = QUALITY_OPTIONS[DEFAULT_QUALITY]
    assert "height<=2160" in spec
    assert "height<=1440" not in spec


def test_the_ladder_still_steps_down_from_the_default():
    for label in ("2K · 1440p", "1080p", "720p", "480p", "Audio only"):
        assert label in QUALITY_OPTIONS


def test_a_capped_entry_caps_at_its_own_height():
    assert "height<=1080" in QUALITY_OPTIONS["1080p"]
    assert "height<=720" in QUALITY_OPTIONS["720p"]


# ---------------------------------------------------------------------- #
# The container
# ---------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "vcodec,expected",
    [
        ("vp9", "mkv"),
        ("vp9.2", "mkv"),
        ("vp09.00.50.08", "mkv"),
        ("vp8", "mkv"),
        ("av01.0.13M.08", "mkv"),
        ("avc1.64002A", "mp4"),
        ("hev1.1.6.L120", "mp4"),
        ("h264", "mp4"),
        ("", "mp4"),
        (None, "mp4"),
    ],
)
def test_the_container_follows_the_codec(vcodec, expected):
    assert merge_container_for(vcodec) == expected


class _FakeYdl:
    """Just enough of a YoutubeDL to run the selector twice."""

    def __init__(self, chosen):
        self.params = {"merge_output_format": "mp4"}
        self.chosen = chosen
        self.selections = 0

    def build_format_selector(self, _spec):
        def selector(_ctx):
            self.selections += 1
            return iter(self.chosen)

        return selector


def test_the_selector_sets_the_container_from_the_video_codec():
    ydl = _FakeYdl([{"vcodec": "vp9", "format_id": "315"}])

    chosen = list(codec_aware_format_selector("best", lambda: ydl)({}))

    assert ydl.params["merge_output_format"] == "mkv"
    assert chosen == [{"vcodec": "vp9", "format_id": "315"}]


def test_the_selector_selects_twice_so_the_container_is_applied():
    ydl = _FakeYdl([{"vcodec": "avc1"}])

    codec_aware_format_selector("best", lambda: ydl)({})

    assert ydl.selections == 2


def test_the_selector_leaves_the_container_alone_when_nothing_matches():
    ydl = _FakeYdl([])

    chosen = list(codec_aware_format_selector("best", lambda: ydl)({}))

    assert chosen == []
    assert ydl.params["merge_output_format"] == "mp4"


# ---------------------------------------------------------------------- #
# What the card says
# ---------------------------------------------------------------------- #
def test_the_label_names_the_resolution_and_the_codec():
    assert quality_label(2160, "vp9") == "2160p · VP9"
    assert quality_label(1080, "avc1.64002A") == "1080p · H.264"
    assert quality_label(1440, "av01.0.12M.08") == "1440p · AV1"


def test_the_label_is_empty_when_there_is_nothing_to_say():
    assert quality_label(None, "vp9") == ""
    assert quality_label(1080, "none") == ""


def test_the_download_reports_the_resolution_and_the_codec():
    thread = DownloadThread([], "out", DEFAULT_QUALITY)
    reported = []
    thread.job_quality.connect(lambda uid, label: reported.append((uid, label)))

    hook = thread._hook_factory(7, set(), "YouTube")
    hook({"status": "downloading", "info_dict": {"height": 2160, "vcodec": "vp9"}})

    assert reported == [(7, "2160p · VP9")]


def test_the_card_shows_the_resolution_the_codec_and_the_size(qapp, isolated_appdata):
    job = Job("https://youtu.be/abc")
    job.quality = "2160p · VP9"
    job.size = "412 MB"

    card = JobCard(job)

    assert "2160p · VP9" in card.meta.text()
    assert "412 MB" in card.meta.text()


# ---------------------------------------------------------------------- #
# The settings page
# ---------------------------------------------------------------------- #
@pytest.fixture
def settings_file(tmp_path, monkeypatch):
    """The app's own preferences, in a file of this test's own."""
    path = tmp_path / "settings.ini"
    monkeypatch.setenv("SQ_SETTINGS_FILE", str(path))
    return path


def _write(path, **values):
    settings = QSettings(str(path), QSettings.Format.IniFormat)
    for key, value in values.items():
        settings.setValue(key, value)
    settings.sync()
    return settings


def _read(path, key):
    return QSettings(str(path), QSettings.Format.IniFormat).value(key)


def test_a_fresh_install_starts_on_the_best_up_to_4k(qapp, isolated_appdata, settings_file):
    page = SettingsPage()
    page.load()

    assert page.quality.currentText() == DEFAULT_QUALITY


def test_a_quality_the_user_chose_survives_a_settings_bump(
    qapp, isolated_appdata, settings_file
):
    _write(settings_file, quality="720p", quality_set="true", settings_version="0.9")

    page = SettingsPage()
    page.load()

    assert page.quality.currentText() == "720p"


def test_a_quality_the_user_never_chose_follows_the_default(
    qapp, isolated_appdata, settings_file
):
    # An older build wrote "1080p" into every profile on the version bump,
    # so the stored value is not a choice - it is the old default.
    _write(settings_file, quality="1080p", settings_version="0.9")

    page = SettingsPage()
    page.load()

    assert page.quality.currentText() == DEFAULT_QUALITY


def test_picking_a_quality_marks_it_as_the_user_s_own(
    qapp, isolated_appdata, settings_file
):
    page = SettingsPage()
    page.load()
    page.quality.setCurrentText("720p")

    page.save()

    assert str(_read(settings_file, "quality_set")).lower() == "true"


def test_the_default_is_not_marked_as_a_choice(
    qapp, isolated_appdata, settings_file
):
    page = SettingsPage()
    page.load()
    page.quality.setCurrentText(DEFAULT_QUALITY)

    page.save()

    assert str(_read(settings_file, "quality_set")).lower() != "true"
