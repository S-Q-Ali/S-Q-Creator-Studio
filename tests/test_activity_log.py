"""Tests for the visible activity log."""

from __future__ import annotations

from s_q_ali_media_downloader.ui.activity_log import MAX_LINES, ActivityLog


def test_lines_are_timestamped_and_read_only(qapp):
    log = ActivityLog()

    log.append_line("Reading @MrBeast")

    text = log.text()
    assert text.startswith("[")
    assert "Reading @MrBeast" in text
    assert log.view.isReadOnly()


def test_the_log_is_capped_and_can_be_cleared(qapp):
    log = ActivityLog()
    for index in range(MAX_LINES + 20):
        log.append_line(f"line {index}")

    assert log.view.blockCount() == MAX_LINES
    assert "line 0" not in log.text()
    assert f"line {MAX_LINES + 19}" in log.text()

    log.clear_log()

    assert log.text() == ""


def test_blank_lines_are_ignored(qapp):
    log = ActivityLog()

    log.append_line("")
    log.append_line("   ")

    assert log.text() == ""
