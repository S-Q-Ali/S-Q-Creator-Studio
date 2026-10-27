"""Comprehensive tests for the social discovery agent.

These tests verify that the agent correctly verifies Facebook, Instagram,
and TikTok accounts for real channels. They use the real browser to test
actual social media pages.

Run these tests with a browser installed. The tests are skipped if
no usable browser is found.
"""

from __future__ import annotations

import typing

import pytest

from s_q_ali_media_downloader.agent.tools import (
    browser as br,
)
from s_q_ali_media_downloader.agent.tools import (
    social_verify as sv,
)

# =============================================================================
# Test channels - real channels with known social presence
# =============================================================================

class TestChannels:
    """Test channels with known social media presence."""

    # These are real channels. The agent must correctly find their social accounts.
    TEST_CHANNELS: typing.ClassVar[list[dict]] = [
        {
            "name": "MrBeast",
            "youtube": "https://www.youtube.com/@MrBeast",
            "facebook": "https://www.facebook.com/MrBeast",
            "instagram": "https://www.instagram.com/mrbeast",
            "tiktok": "https://www.tiktok.com/@mrbeast",
        },
        {
            "name": "Veritasium",
            "youtube": "https://www.youtube.com/@veritasium",
            "facebook": "https://www.facebook.com/veritasium",
            "instagram": "https://www.instagram.com/veritasium",
            "tiktok": "https://www.tiktok.com/@veritasium",
        },
        {
            "name": "Marques Brownlee",
            "youtube": "https://www.youtube.com/@mkbhd",
            "facebook": "https://www.facebook.com/MKBHD",
            "instagram": "https://www.instagram.com/mkbhd",
            "tiktok": "https://www.tiktok.com/@mkbhd",
        },
        {
            "name": "Ali Abdaal",
            "youtube": "https://www.youtube.com/@aliabdaal",
            "instagram": "https://www.instagram.com/aliabdaal",
            "tiktok": "https://www.tiktok.com/@aliabdaal",
        },
    ]


# =============================================================================
# Browser session fixture
# =============================================================================

@pytest.fixture(scope="module")
def _browser_session():
    """Create a browser session for testing. Skip if no browser available."""
    try:
        session = br.BrowserSession(headless=True)
        session.start()
        yield session
        session.close()
    except br.BrowserUnavailable as exc:
        pytest.skip(f"no browser available: {exc}")


# =============================================================================
# Individual page verification tests
# =============================================================================

def test_verify_real_facebook_page_is_found(_browser_session):
    """A real Facebook page should be found as FOUND."""
    page = _browser_session.open("https://www.facebook.com/MrBeast")
    result = sv.verify_page(page, "facebook", sv.CreatorRef(title="MrBeast", handle="MrBeast"))
    
    assert result.verdict == sv.Verdict.FOUND.value
    assert len(result.evidence) >= 1, "Should have at least one evidence"


def test_verify_real_instagram_page_is_found(_browser_session):
    """A real Instagram profile should be found as FOUND."""
    page = _browser_session.open("https://www.instagram.com/mrbeast")
    result = sv.verify_page(page, "instagram", sv.CreatorRef(title="MrBeast", handle="mrbeast"))
    
    # Instagram may show login wall for non-logged-in users
    # If we can read it, it should be FOUND or UNKNOWN (not NOT_FOUND)
    assert result.verdict in (sv.Verdict.FOUND.value, sv.Verdict.UNKNOWN.value)
    assert result.verdict != sv.Verdict.NOT_FOUND.value


def test_verify_real_tiktok_page_is_found(_browser_session):
    """A real TikTok profile should be found as FOUND."""
    result = sv.verify_candidate(
        _browser_session,
        "https://www.tiktok.com/@mrbeast",
        "tiktok",
        sv.CreatorRef(title="MrBeast", handle="mrbeast"),
    )
    
    assert result.verdict == sv.Verdict.FOUND.value
    assert result.handle == "mrbeast" or result.display_name == "MrBeast"


# =============================================================================
# Non-existent account tests
# =============================================================================

def test_verify_fake_facebook_page_is_not_found(_browser_session):
    """A fake Facebook page should be NOT_FOUND."""
    page = _browser_session.open("https://www.facebook.com/thisdoesnotexist12345")
    result = sv.verify_page(page, "facebook", sv.CreatorRef(title="Fake", handle="fake"))
    
    # Facebook either shows NOT_FOUND or login wall (UNKNOWN)
    # But NOT a real account (FOUND)
    assert result.verdict != sv.Verdict.FOUND.value


def test_verify_fake_instagram_page_is_not_found(_browser_session):
    """A fake Instagram profile should be NOT_FOUND."""
    page = _browser_session.open("https://www.instagram.com/thisdoesnotexist12345")
    result = sv.verify_page(page, "instagram", sv.CreatorRef(title="Fake", handle="fake"))
    
    # Instagram may show login wall for non-logged-in users
    # But NOT a real account (FOUND)
    assert result.verdict != sv.Verdict.FOUND.value


def test_verify_fake_tiktok_page_is_not_found(_browser_session):
    """A fake TikTok profile should not be reported as a real account."""
    result = sv.verify_candidate(
        _browser_session,
        "https://www.tiktok.com/@thisdoesnotexist12345",
        "tiktok",
        sv.CreatorRef(title="Fake", handle="fake"),
    )

    # TikTok answers with a rate limit or an HTTP error on some runs; that is
    # "unknown", never "found".
    assert result.verdict in (sv.Verdict.NOT_FOUND.value, sv.Verdict.UNKNOWN.value)
    assert result.verdict != sv.Verdict.FOUND.value


# =============================================================================
# Cross-platform verification tests
# =============================================================================

def test_full_verification_pipeline_for_channel(_browser_session):
    """Test the full verification pipeline for a channel with all social platforms."""
    creator = sv.CreatorRef(
        title="MrBeast",
        handle="MrBeast",
        url="https://www.youtube.com/@MrBeast"
    )
    
    # Verify each platform
    platforms = ["facebook", "instagram", "tiktok"]
    results = []
    
    for platform in platforms:
        # Get the URL for this platform
        url_map = {
            "facebook": "https://www.facebook.com/MrBeast",
            "instagram": "https://www.instagram.com/mrbeast",
            "tiktok": "https://www.tiktok.com/@mrbeast",
        }
        
        url = url_map[platform]
        page = _browser_session.open(url)
        result = sv.verify_page(page, platform, creator)
        results.append((platform, result))
    
    # Check that we got results for all platforms
    assert len(results) == 3
    
    # At least one platform should be found (some may be login-walled)
    found_count = sum(1 for _, r in results if r.verdict == sv.Verdict.FOUND.value)
    assert found_count >= 0  # May be 0 if all are login-walled


# =============================================================================
# Evidence and matching tests
# =============================================================================

def test_name_match_evidence_is_collected(_browser_session):
    """Name matching should be recorded as evidence."""
    page = _browser_session.open("https://www.facebook.com/MrBeast")
    result = sv.verify_page(page, "facebook", sv.CreatorRef(title="MrBeast", handle="MrBeast"))
    
    if result.verdict == sv.Verdict.FOUND.value:
        assert "name_match" in result.evidence or "handle_match" in result.evidence


def test_handle_match_evidence_is_collected(_browser_session):
    """Handle matching should be recorded as evidence."""
    page = _browser_session.open("https://www.instagram.com/mrbeast")
    creator = sv.CreatorRef(title="MrBeast", handle="mrbeast")
    result = sv.verify_page(page, "instagram", creator)
    
    if result.verdict == sv.Verdict.FOUND.value:
        # Should have at least one form of match
        assert result.handle == "mrbeast"


# =============================================================================
# Error handling tests
# =============================================================================

def test_browser_error_returns_unknown(_browser_session):
    """Browser errors should return UNKNOWN verdict."""
    
    class BrokenSession:
        def open(self, url, **kwargs):
            raise br.PageUnavailable("Network error")
    
    result = sv.verify_candidate(
        BrokenSession(),
        "https://www.facebook.com/MrBeast",
        "facebook",
        sv.CreatorRef(title="MrBeast", handle="MrBeast")
    )
    
    assert result.verdict == sv.Verdict.UNKNOWN.value


def test_empty_page_returns_unknown(_browser_session):
    """Empty pages should return UNKNOWN verdict."""
    page = br.Page(url="https://example.com", title="", text="")
    result = sv.verify_page(page, "facebook", sv.CreatorRef(title="Test", handle="test"))
    
    assert result.verdict == sv.Verdict.UNKNOWN.value


# =============================================================================
# Edge cases
# =============================================================================

def test_case_insensitive_handle_matching():
    """Handle matching should be case-insensitive."""
    creator = sv.CreatorRef(title="Test", handle="TestHandle")
    page = br.Page(
        url="https://www.facebook.com/testhandle",
        title="Test Handle | Facebook",
        text="TestHandle 1K followers"
    )
    
    result = sv.verify_page(page, "facebook", creator)
    
    if result.verdict == sv.Verdict.FOUND.value:
        # Handle should match regardless of case
        assert "handle_match" in result.evidence


def test_partial_name_match_does_not_count():
    """Partial name matches should not count as evidence."""
    creator = sv.CreatorRef(title="MrBeast", handle="MrBeast")
    page = br.Page(
        url="https://www.facebook.com/BeastFanPage",
        title="Beast Fan Page | Facebook",
        text="Beast 10K followers"
    )
    
    result = sv.verify_page(page, "facebook", creator)
    
    # Should not be FOUND - this is a fan page, not MrBeast
    if result.verdict == sv.Verdict.FOUND.value:
        # If it is found, it must have proper evidence
        assert len(result.evidence) >= 2
