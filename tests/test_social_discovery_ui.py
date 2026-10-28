"""Tests for the Social Discovery page."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from s_q_ali_media_downloader.agent.social_discovery import (
    DiscoveryResult,
    PlatformOutcome,
)
from s_q_ali_media_downloader.ui.social_discovery_page import SocialDiscoveryPage


def _result(**kwargs) -> DiscoveryResult:
    base = {
        "query": "@MrBeast",
        "title": "MrBeast",
        "handle": "MrBeast",
        "url": "https://www.youtube.com/@MrBeast",
        "subscribers": 522_000_000,
    }
    base.update(kwargs)
    return DiscoveryResult(**base)


def _found(platform: str, tier: str = "confirmed", source: str = "bio") -> PlatformOutcome:
    return PlatformOutcome(
        platform=platform,
        verdict="found",
        url=f"https://www.{platform}.com/mrbeast",
        display_name="MrBeast",
        evidence=["name_match", "handle_match"],
        detail="the page describes the account",
        source=source,
        tier=tier,
    )


def test_the_page_has_a_column_per_platform(qapp):
    page = SocialDiscoveryPage()

    assert page.table.columnCount() == 4
    assert page.table.horizontalHeaderItem(1).text() == "Facebook"
    assert page.table.horizontalHeaderItem(3).text() == "TikTok"


def test_a_result_becomes_a_row(qapp):
    page = SocialDiscoveryPage()
    result = _result()
    result.platforms = [_found("facebook"), _found("instagram")]

    page._on_result(result)

    assert page.table.rowCount() == 1
    assert page.table.item(0, 0).text().startswith("MrBeast")
    assert "Found" in page.table.item(0, 1).text()
    assert "Found" in page.table.item(0, 2).text()
    assert page.table.item(0, 3).text() == "—"


def test_a_found_cell_carries_the_link(qapp):
    page = SocialDiscoveryPage()
    result = _result()
    result.platforms = [_found("facebook")]

    page._on_result(result)

    item = page.table.item(0, 1)
    assert "mrbeast" in item.toolTip()
    assert item.data(Qt.ItemDataRole.UserRole) == "https://www.facebook.com/mrbeast"


def test_clicking_a_cell_shows_the_evidence(qapp):
    page = SocialDiscoveryPage()
    result = _result()
    result.platforms = [_found("facebook")]
    page._on_result(result)

    page._on_cell_clicked(0, 1)

    text = page.detail_label.text()
    assert "name_match" in text
    assert "mrbeast" in text


def test_a_found_cell_shows_the_confidence_tier(qapp):
    page = SocialDiscoveryPage()
    result = _result()
    result.platforms = [_found("facebook", tier="likely")]

    page._on_result(result)

    item = page.table.item(0, 1)
    assert "Found" in item.text()
    assert "likely" in item.text()
    assert "likely" in item.toolTip()


def test_the_detail_line_shows_the_source_and_tier(qapp):
    page = SocialDiscoveryPage()
    result = _result()
    result.platforms = [_found("facebook", tier="likely", source="model")]
    page._on_result(result)

    page._on_cell_clicked(0, 1)

    text = page.detail_label.text()
    assert "likely" in text
    assert "model" in text


def test_the_status_splits_confirmed_from_likely(qapp):
    page = SocialDiscoveryPage()
    result = _result()
    result.platforms = [
        _found("facebook", tier="confirmed"),
        _found("instagram", tier="likely"),
    ]

    page._on_result(result)

    text = page.status_label.text()
    assert "2 found" in text
    assert "1 confirmed" in text
    assert "1 likely" in text


def test_the_export_rows_carry_the_tier_and_source(qapp):
    page = SocialDiscoveryPage()
    result = _result()
    result.platforms = [_found("facebook", tier="likely", source="model")]
    page._on_result(result)

    rows = page._rows()

    assert rows[0]["facebook_tier"] == "likely"
    assert rows[0]["facebook_source"] == "model"


def test_the_export_rows_carry_every_platform(qapp):
    page = SocialDiscoveryPage()
    result = _result()
    result.platforms = [_found("facebook")]
    page._on_result(result)

    rows = page._rows()

    assert rows[0]["channel"] == "MrBeast"
    assert rows[0]["facebook"] == "https://www.facebook.com/mrbeast"
    assert rows[0]["instagram"] == ""
    assert rows[0]["tiktok_status"] == ""


def test_shutdown_stops_and_waits_for_the_worker(qapp):
    class FakeWorker:
        cancelled = False
        waited = False

        def isRunning(self):
            return True

        def cancel(self):
            self.cancelled = True

        def wait(self, ms):
            self.waited = True
            return True

    page = SocialDiscoveryPage()
    page.worker = FakeWorker()

    assert page.shutdown() is True
    assert page.worker.cancelled
    assert page.worker.waited


def test_shutdown_reports_a_worker_that_will_not_stop(qapp):
    class FakeWorker:
        def isRunning(self):
            return True

        def cancel(self):
            pass

        def wait(self, ms):
            return False

    page = SocialDiscoveryPage()
    page.worker = FakeWorker()

    assert page.shutdown() is False


def test_a_failure_reaches_the_activity_log(qapp):
    page = SocialDiscoveryPage()
    lines = []
    page.log.connect(lines.append)

    page._on_failed("no browser available")

    assert lines == ["Failed: no browser available"]


def test_a_finished_result_reaches_the_activity_log(qapp):
    page = SocialDiscoveryPage()
    lines = []
    page.log.connect(lines.append)
    result = _result()
    result.platforms = [_found("facebook")]

    page._on_result(result)

    assert any("1 found" in line for line in lines)


def test_a_warning_is_shown_with_the_row(qapp):
    page = SocialDiscoveryPage()
    result = _result(warning="Groq answered 401: invalid_api_key")
    result.platforms = [_found("facebook")]

    page._on_result(result)

    assert "401" in page.status_label.text()
    assert "401" in page.table.item(0, 0).toolTip()


def test_the_status_line_says_which_backends_were_used(qapp):
    page = SocialDiscoveryPage()
    result = _result(
        bio_candidates=2,
        ai_used=True,
        ai_candidates=3,
        browser_checks=5,
    )
    result.platforms = [_found("facebook")]

    page._on_result(result)

    text = page.status_label.text()
    assert "bio links 2" in text
    assert "AI 3" in text
    assert "browser checks 5" in text


def test_the_channel_tooltip_says_which_backends_were_used(qapp):
    page = SocialDiscoveryPage()
    result = _result(
        bio_candidates=2,
        ai_used=True,
        ai_candidates=3,
        browser_checks=5,
    )
    result.platforms = [_found("facebook")]

    page._on_result(result)

    tip = page.table.item(0, 0).toolTip()
    assert "bio links 2" in tip
    assert "AI 3" in tip
    assert "browser checks 5" in tip


def test_the_page_explains_the_backend_order(qapp):
    page = SocialDiscoveryPage()

    hints = [label.text() for label in page.findChildren(QLabel)]
    hint = next(text for text in hints if "bio links" in text)

    assert "yt-dlp" in hint
    assert "Groq" in hint
    assert "browser" in hint


def test_a_channel_that_could_not_be_resolved_still_gets_a_row(qapp):
    page = SocialDiscoveryPage()
    result = _result(query="@nobody", title="", error="that is not a channel")

    page._on_result(result)

    assert page.table.rowCount() == 1
    assert page.table.item(0, 1).text() == "—"
