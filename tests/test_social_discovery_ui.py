"""Tests for the Social Discovery page."""

from __future__ import annotations

from PySide6.QtCore import Qt

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


def _found(platform: str) -> PlatformOutcome:
    return PlatformOutcome(
        platform=platform,
        verdict="found",
        url=f"https://www.{platform}.com/mrbeast",
        display_name="MrBeast",
        evidence=["name_match", "handle_match"],
        detail="the page describes the account",
        source="bio",
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


def test_a_channel_that_could_not_be_resolved_still_gets_a_row(qapp):
    page = SocialDiscoveryPage()
    result = _result(query="@nobody", title="", error="that is not a channel")

    page._on_result(result)

    assert page.table.rowCount() == 1
    assert page.table.item(0, 1).text() == "—"
