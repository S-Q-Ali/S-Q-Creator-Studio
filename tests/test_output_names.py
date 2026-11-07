"""Tests for the name a leg writes its output to.

The rule these hold: a name that is already in the folder is never written
over, and a fresh cut of parts continues where the last one stopped.
"""

from __future__ import annotations

from s_q_ali_media_downloader.core import output_names


def test_a_free_folder_takes_the_plain_name(tmp_path):
    got = output_names.next_part_path(str(tmp_path), "Film_9x16")
    assert got == str(tmp_path / "Film_9x16.mp4")


def test_a_name_already_in_the_folder_gets_the_next_part(tmp_path):
    (tmp_path / "Film_9x16.mp4").write_bytes(b"kept by the user")
    got = output_names.next_part_path(str(tmp_path), "Film_9x16")
    assert got == str(tmp_path / "Film_9x16 Part 2.mp4")


def test_parts_already_in_the_folder_are_stepped_over_too(tmp_path):
    for name in ("Film_9x16.mp4", "Film_9x16 Part 2.mp4"):
        (tmp_path / name).write_bytes(b"kept by the user")
    got = output_names.next_part_path(str(tmp_path), "Film_9x16")
    assert got == str(tmp_path / "Film_9x16 Part 3.mp4")


def test_only_the_requested_extension_counts_as_taken(tmp_path):
    (tmp_path / "Film_9x16.txt").write_bytes(b"not a video")
    got = output_names.next_part_path(str(tmp_path), "Film_9x16")
    assert got == str(tmp_path / "Film_9x16.mp4")


def test_no_other_name_is_created_by_choosing_one(tmp_path):
    output_names.next_part_path(str(tmp_path), "Film_9x16")
    assert list(tmp_path.iterdir()) == []


def test_a_folder_that_is_not_there_yet_starts_at_the_plain_name(tmp_path):
    missing = str(tmp_path / "results")
    got = output_names.next_part_path(missing, "Film_9x16")
    assert got == str(tmp_path / "results" / "Film_9x16.mp4")


def test_the_part_numbering_reuses_the_extension_it_was_given(tmp_path):
    (tmp_path / "Film_9x16.mkv").write_bytes(b"x")
    got = output_names.next_part_path(str(tmp_path), "Film_9x16", ext=".mkv")
    assert got == str(tmp_path / "Film_9x16 Part 2.mkv")


def test_a_film_with_no_parts_in_it_starts_at_one(tmp_path):
    (tmp_path / "Film.mp4").write_bytes(b"the film itself")
    assert output_names.next_part_start(str(tmp_path), "Film") == 1


def test_the_first_free_part_is_one_past_the_highest_written(tmp_path):
    for name in ("Film Part 1.mp4", "Film Part 2.mp4"):
        (tmp_path / name).write_bytes(b"x")
    assert output_names.next_part_start(str(tmp_path), "Film") == 3


def test_a_gap_in_the_parts_is_not_filled_in(tmp_path):
    for name in ("Film Part 1.mp4", "Film Part 3.mp4"):
        (tmp_path / name).write_bytes(b"x")
    assert output_names.next_part_start(str(tmp_path), "Film") == 4


def test_ten_parts_outranks_two_when_the_parts_are_counted(tmp_path):
    for name in ("Film Part 2.mp4", "Film Part 10.mp4"):
        (tmp_path / name).write_bytes(b"x")
    assert output_names.next_part_start(str(tmp_path), "Film") == 11


def test_the_parts_of_another_film_are_not_counted(tmp_path):
    for name in ("Other Part 4.mp4", "Film_extra Part 4.mp4"):
        (tmp_path / name).write_bytes(b"x")
    assert output_names.next_part_start(str(tmp_path), "Film") == 1


def test_a_stem_with_regex_characters_in_it_is_read_as_a_name(tmp_path):
    (tmp_path / "Film (2) Part 3.mp4").write_bytes(b"x")
    assert output_names.next_part_start(str(tmp_path), "Film (2)") == 4


def test_a_folder_that_is_not_there_yet_starts_at_one(tmp_path):
    assert output_names.next_part_start(str(tmp_path / "results"), "Film") == 1
