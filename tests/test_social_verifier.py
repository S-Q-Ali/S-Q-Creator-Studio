"""Unit tests for SocialVerifierTool using asyncio.run."""

import asyncio

from s_q_ali_media_downloader.agent.schema import SocialStatus
from s_q_ali_media_downloader.agent.tools.social_verifier import SocialVerifierTool


def test_social_verifier_none_input():
    verifier = SocialVerifierTool()

    async def _test():
        return await verifier.verify_channel_socials(candidate_fb=None, candidate_ig=None)

    fb, ig, tk = asyncio.run(_test())
    assert fb.status == SocialStatus.NOT_FOUND
    assert ig.status == SocialStatus.NOT_FOUND
    assert tk.status == SocialStatus.NOT_FOUND


def test_social_verifier_valid_format():
    verifier = SocialVerifierTool()

    async def _test():
        return await verifier.verify_facebook_presence(
            candidate_url="https://www.facebook.com/nonexistent_dummy_page_99999"
        )

    presence = asyncio.run(_test())
    assert presence.verified_url == "https://www.facebook.com/nonexistent_dummy_page_99999"


def test_bio_link_never_downgrades_to_not_found(monkeypatch):
    """A bio-sourced URL that hits a network failure must stay UNVERIFIED_HANDLE."""
    verifier = SocialVerifierTool(timeout=0.1)
    import httpx

    class FakeClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, *a, **kw):
            raise httpx.ConnectError("blocked")

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    async def _test():
        return await verifier.verify_instagram_presence(
            candidate_url="https://www.instagram.com/real_creator/"
        )

    presence = asyncio.run(_test())
    assert presence.status == SocialStatus.UNVERIFIED_HANDLE
    assert presence.confidence_score >= 0.5
    assert presence.source == "bio_link"


class _FakeResponse:
    def __init__(self, status_code, text):
        self.status_code = status_code
        self.text = text


def _client_for(response):
    class FakeClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, *a, **kw):
            return response

    return FakeClient


def test_a_200_login_wall_is_not_verified(monkeypatch):
    """Instagram answers a login wall with 200. That is not a profile."""
    verifier = SocialVerifierTool(timeout=0.1)
    import httpx

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        _client_for(_FakeResponse(200, "<html>Log in to Instagram</html>")),
    )

    async def _test():
        return await verifier.verify_instagram_presence(
            candidate_url="https://www.instagram.com/real_creator/"
        )

    presence = asyncio.run(_test())
    assert presence.status == SocialStatus.UNVERIFIED_HANDLE


def test_a_200_profile_with_a_profile_key_is_verified(monkeypatch):
    verifier = SocialVerifierTool(timeout=0.1)
    import httpx

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        _client_for(_FakeResponse(200, '<html>{"edge_followed_by": {"count": 91}}</html>')),
    )

    async def _test():
        return await verifier.verify_instagram_presence(
            candidate_url="https://www.instagram.com/real_creator/"
        )

    presence = asyncio.run(_test())
    assert presence.status == SocialStatus.VERIFIED


def test_a_200_page_with_only_followers_is_not_a_profile(monkeypatch):
    """The JavaScript shell also contains the word 'followers'."""
    verifier = SocialVerifierTool(timeout=0.1)
    import httpx

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        _client_for(_FakeResponse(200, "<html>91M followers</html>")),
    )

    async def _test():
        return await verifier.verify_instagram_presence(
            candidate_url="https://www.instagram.com/real_creator/"
        )

    presence = asyncio.run(_test())
    assert presence.status == SocialStatus.UNVERIFIED_HANDLE


def test_a_404_on_a_bio_link_is_not_not_found(monkeypatch):
    """A creator-declared link is never erased by a failed probe."""
    verifier = SocialVerifierTool(timeout=0.1)
    import httpx

    monkeypatch.setattr(
        httpx, "AsyncClient", _client_for(_FakeResponse(404, "Not Found"))
    )

    async def _test():
        return await verifier.verify_instagram_presence(
            candidate_url="https://www.instagram.com/real_creator/"
        )

    presence = asyncio.run(_test())
    assert presence.status == SocialStatus.UNVERIFIED_HANDLE


def test_handle_guess_network_failure_is_inconclusive(monkeypatch):
    """A guessed handle that hits a network failure must NOT be NOT_FOUND."""
    verifier = SocialVerifierTool(timeout=0.1)
    import httpx

    class FakeClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, *a, **kw):
            raise httpx.ConnectError("blocked")

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    async def _test():
        return await verifier.verify_facebook_presence(
            candidate_url=None, channel_handle="@somebody"
        )

    presence = asyncio.run(_test())
    assert presence.status == SocialStatus.INCONCLUSIVE
    assert presence.source == "handle_guess"
