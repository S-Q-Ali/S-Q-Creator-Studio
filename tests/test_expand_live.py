"""Live tests for the Instagram and Facebook expansion.

These hit the real sites, so they need the network, the instaloader package
and a browser. CI excludes them with ``pytest -m "not live"``; run them
locally with ``pytest -m live``.

Instagram rate-limits a machine that asks too often, so this file lists one
profile and one page. That is enough to prove the two legs still work.
"""

from __future__ import annotations

import pytest

from s_q_ali_media_downloader.core.facebook_client import list_page_videos
from s_q_ali_media_downloader.core.instagram_client import list_profile_media

pytestmark = pytest.mark.live


def test_a_public_instagram_profile_lists_its_videos():
    urls = list_profile_media("nasa", 3)

    assert urls, "the profile listed no videos"
    assert len(urls) <= 3
    for url in urls:
        assert url.startswith("https://www.instagram.com/p/")
        # The CDN link instaloader also exposes carries an expiry token and
        # stops working minutes later.
        assert "fbcdn.net" not in url


def test_a_public_facebook_page_lists_its_videos():
    urls = list_page_videos("nasa", 5)

    assert urls, "the page listed no videos"
    assert len(urls) <= 5
    for url in urls:
        assert url.startswith("https://www.facebook.com/nasa/videos/")
