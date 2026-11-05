"""Tests for the 9:16 reframe maths - the crop window and the path it takes."""

from __future__ import annotations

import pytest

from s_q_ali_media_downloader.core import reframe


def test_the_crop_window_is_exactly_nine_by_sixteen():
    """The window has to be 9:16 to the pixel, or the scale to 1080x1920
    stretches the picture by a fraction of a percent."""
    width, height = reframe.crop_window(1920, 1080)

    assert (width, height) == (594, 1056)
    assert width * 16 == height * 9


def test_a_720p_source_gets_a_720_crop():
    assert reframe.crop_window(1280, 720) == (396, 704)


def test_a_source_too_small_to_crop_vertically_is_refused():
    with pytest.raises(ValueError):
        reframe.crop_window(100, 20)


def test_the_crop_x_is_clamped_inside_the_frame():
    assert reframe.clamp_x(-40, 1920, 594) == 0
    assert reframe.clamp_x(4000, 1920, 594) == 1920 - 594
    assert reframe.clamp_x(600, 1920, 594) == 600


def test_a_jump_in_the_detection_does_not_snap_the_camera():
    """A detector that moves the subject across the frame in one sample must
    not move the window with it in one step."""
    path = reframe.crop_path([100, 1000], 1920, 594, max_step=100)

    assert path == [100, 200]


def test_a_sample_without_a_detection_keeps_the_previous_position():
    path = reframe.crop_path([100, None, 300], 1920, 594, max_step=1000)

    assert path == [100, 100, 300]


def test_the_path_stays_inside_the_frame():
    path = reframe.crop_path([-40, 4000], 1920, 594, max_step=10_000)

    assert path == [0, 1920 - 594]
    assert all(0 <= x <= 1920 - 594 for x in path)


def test_the_crop_x_is_always_even():
    """An odd offset shifts the chroma by half a pixel."""
    path = reframe.crop_path([101, 202], 1920, 594)

    assert path == [100, 202]


def test_the_window_travels_at_most_a_quarter_of_its_width_per_sample():
    assert reframe.max_step_for(594) == 148


def test_the_command_file_holds_one_line_per_sample_in_time_order(tmp_path):
    command_file = tmp_path / "crop.cmd"

    reframe.write_command_file(
        command_file,
        [reframe.Sample(0.0, 100), reframe.Sample(1.5, 400)],
    )

    assert command_file.read_text(encoding="utf-8").splitlines() == [
        "0.000 crop@c x 100;",
        "1.500 crop@c x 400;",
    ]
