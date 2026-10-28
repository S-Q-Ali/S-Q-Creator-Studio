"""Unit tests for SocialVerifierTool using asyncio.run."""

import asyncio
import threading

from s_q_ali_media_downloader.agent.schema import (
    SocialPlatform,
    SocialPresence,
    SocialStatus,
)
from s_q_ali_media_downloader.agent.tools.browser import Page
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


def _presence(status, source="handle_guess", url="https://www.instagram.com/creator/"):
    return SocialPresence(
        platform=SocialPlatform.INSTAGRAM,
        status=status,
        verified_url=url,
        source=source,
    )


def test_a_rendered_page_confirms_an_inconclusive_probe():
    page = Page(
        url="https://www.instagram.com/creator/",
        meta={"ogTitle": "Creator (@creator) - Instagram photos and videos"},
    )
    verifier = SocialVerifierTool(rendered_checker=lambda url: page)
    presence = _presence(SocialStatus.INCONCLUSIVE)

    asyncio.run(verifier._rendered_fallback(presence, "instagram"))

    assert presence.status == SocialStatus.UNVERIFIED_HANDLE
    assert presence.confidence_score >= 0.6
    assert presence.handle == "creator"
    verifier.close()


def test_a_rendered_page_confirms_a_bio_link_as_verified():
    page = Page(
        url="https://www.instagram.com/creator/",
        meta={"ogTitle": "Creator (@creator) - Instagram photos and videos"},
    )
    verifier = SocialVerifierTool(rendered_checker=lambda url: page)
    presence = _presence(SocialStatus.UNVERIFIED_HANDLE, source="bio_link")

    asyncio.run(verifier._rendered_fallback(presence, "instagram"))

    assert presence.status == SocialStatus.VERIFIED
    verifier.close()


def test_a_rendered_missing_page_marks_a_guess_not_found():
    page = Page(url="https://www.instagram.com/creator/", title="Profile isn't available")
    verifier = SocialVerifierTool(rendered_checker=lambda url: page)
    presence = _presence(SocialStatus.INCONCLUSIVE)

    asyncio.run(verifier._rendered_fallback(presence, "instagram"))

    assert presence.status == SocialStatus.NOT_FOUND
    verifier.close()


def test_a_rendered_missing_page_never_erases_a_bio_link():
    page = Page(url="https://www.instagram.com/creator/", title="Profile isn't available")
    verifier = SocialVerifierTool(rendered_checker=lambda url: page)
    presence = _presence(SocialStatus.UNVERIFIED_HANDLE, source="bio_link")

    asyncio.run(verifier._rendered_fallback(presence, "instagram"))

    assert presence.status == SocialStatus.UNVERIFIED_HANDLE
    verifier.close()


def test_a_login_wall_is_not_evidence_of_an_account():
    page = Page(url="https://www.instagram.com/creator/", text="Log in to Instagram")
    verifier = SocialVerifierTool(rendered_checker=lambda url: page)
    presence = _presence(SocialStatus.INCONCLUSIVE)

    asyncio.run(verifier._rendered_fallback(presence, "instagram"))

    assert presence.status == SocialStatus.INCONCLUSIVE
    verifier.close()


def test_a_decisive_http_probe_never_opens_the_browser():
    calls = []
    verifier = SocialVerifierTool(rendered_checker=lambda url: calls.append(url))
    presence = _presence(SocialStatus.VERIFIED, source="bio_link")

    asyncio.run(verifier._rendered_fallback(presence, "instagram"))

    assert calls == []
    verifier.close()


def test_all_rendered_checks_use_one_thread():
    threads = []

    def checker(url):
        threads.append(threading.current_thread().name)
        return Page(url=url, title="Profile isn't available")

    verifier = SocialVerifierTool(rendered_checker=checker)

    async def _test():
        presences = [_presence(SocialStatus.INCONCLUSIVE) for _ in range(3)]
        return await asyncio.gather(
            *(verifier._rendered_fallback(item, "instagram") for item in presences)
        )

    asyncio.run(_test())

    assert len(set(threads)) == 1
    verifier.close()


def test_closing_the_verifier_closes_the_browser():
    closed = []

    class Checker:
        def __call__(self, url):
            return Page(url=url)

        def close(self):
            closed.append(True)

    verifier = SocialVerifierTool(rendered_checker=Checker())
    verifier.close()

    assert closed == [True]
