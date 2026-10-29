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
from s_q_ali_media_downloader.agent.tools.social_verify import CreatorRef


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


def test_a_model_guess_that_404s_is_not_found(monkeypatch):
    """A URL the model guessed is not a creator-declared link, so a missing
    page stays missing instead of being kept as unverified."""
    verifier = SocialVerifierTool(timeout=0.1)
    import httpx

    monkeypatch.setattr(
        httpx, "AsyncClient", _client_for(_FakeResponse(404, "Not Found"))
    )

    async def _test():
        return await verifier.verify_instagram_presence(
            candidate_url="https://www.instagram.com/guessed_by_the_model/",
            source="model",
        )

    presence = asyncio.run(_test())
    assert presence.status == SocialStatus.NOT_FOUND
    assert presence.source == "model"


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


# --------------------------------------------------------------------------- #
# The AI browser fallback
# --------------------------------------------------------------------------- #
class _Agent:
    def __init__(self, answer, remaining=3):
        self.answer = answer
        self.remaining = remaining
        self.configured = True
        self.calls = []

    def __call__(self, url, platform):
        self.calls.append((url, platform))
        return self.answer


def test_an_agent_answer_confirms_an_inconclusive_probe():
    agent = _Agent(
        {
            "exists": "yes",
            "display_name": "Creator",
            "handle": "creator",
            "followers": "1M followers",
            "reason": "the profile is visible",
        }
    )
    verifier = SocialVerifierTool(agent_checker=agent)
    presence = _presence(SocialStatus.INCONCLUSIVE)

    asyncio.run(verifier._agent_fallback(presence, "instagram"))

    assert presence.status == SocialStatus.UNVERIFIED_HANDLE
    assert presence.confidence_score >= 0.6
    assert presence.handle == "creator"
    assert agent.calls == [("https://www.instagram.com/creator/", "instagram")]
    verifier.close()


def test_an_agent_answer_confirms_a_bio_link_as_verified():
    agent = _Agent({"exists": "yes", "display_name": "Creator", "handle": "creator"})
    verifier = SocialVerifierTool(agent_checker=agent)
    presence = _presence(SocialStatus.UNVERIFIED_HANDLE, source="bio_link")

    asyncio.run(verifier._agent_fallback(presence, "instagram"))

    assert presence.status == SocialStatus.VERIFIED
    verifier.close()


def test_an_agent_no_marks_a_guessed_page_not_found():
    agent = _Agent({"exists": "no", "quote": "Profile isn't available"})
    verifier = SocialVerifierTool(agent_checker=agent)
    presence = _presence(SocialStatus.INCONCLUSIVE)

    asyncio.run(verifier._agent_fallback(presence, "instagram"))

    assert presence.status == SocialStatus.NOT_FOUND
    verifier.close()


def test_an_agent_no_never_erases_a_bio_link():
    agent = _Agent({"exists": "no", "quote": "Profile isn't available"})
    verifier = SocialVerifierTool(agent_checker=agent)
    presence = _presence(SocialStatus.UNVERIFIED_HANDLE, source="bio_link")

    asyncio.run(verifier._agent_fallback(presence, "instagram"))

    assert presence.status == SocialStatus.UNVERIFIED_HANDLE
    verifier.close()


def test_an_unknown_agent_answer_changes_nothing():
    agent = _Agent({"exists": "unknown", "reason": "the page is blank"})
    verifier = SocialVerifierTool(agent_checker=agent)
    presence = _presence(SocialStatus.INCONCLUSIVE)

    asyncio.run(verifier._agent_fallback(presence, "instagram"))

    assert presence.status == SocialStatus.INCONCLUSIVE
    verifier.close()


def test_the_agent_is_not_called_when_its_budget_is_spent():
    agent = _Agent({"exists": "yes", "display_name": "Creator"}, remaining=0)
    verifier = SocialVerifierTool(agent_checker=agent)
    presence = _presence(SocialStatus.INCONCLUSIVE)

    asyncio.run(verifier._agent_fallback(presence, "instagram"))

    assert presence.status == SocialStatus.INCONCLUSIVE
    assert agent.calls == []
    verifier.close()


def test_the_agent_closes_the_rendered_browser_first():
    events = []

    class Rendered:
        def __call__(self, url):
            return Page(url=url)

        def close(self):
            events.append("rendered")

    class Agent(_Agent):
        def __call__(self, url, platform):
            events.append("agent")
            return super().__call__(url, platform)

    verifier = SocialVerifierTool(
        rendered_checker=Rendered(),
        agent_checker=Agent({"exists": "yes", "display_name": "Creator"}),
    )

    asyncio.run(verifier._agent_fallback(_presence(SocialStatus.INCONCLUSIVE), "instagram"))

    assert events == ["rendered", "agent"]
    verifier.close()


def test_closing_the_verifier_closes_the_agent():
    closed = []

    class Agent(_Agent):
        def close(self):
            closed.append(True)

    verifier = SocialVerifierTool(agent_checker=Agent({"exists": "unknown"}))
    verifier.close()

    assert closed == [True]


# --------------------------------------------------------------------------- #
# The page is judged against the creator, whoever read it
# --------------------------------------------------------------------------- #
CREATOR = CreatorRef(title="Creator", handle="creator")


def test_a_bio_link_is_verified_when_the_page_matches_the_creator():
    page = Page(
        url="https://www.instagram.com/creator/",
        meta={"ogTitle": "Creator (@creator) - Instagram photos and videos"},
    )
    verifier = SocialVerifierTool(rendered_checker=lambda url: page)
    presence = _presence(SocialStatus.UNVERIFIED_HANDLE, source="bio_link")

    asyncio.run(verifier._rendered_fallback(presence, "instagram", CREATOR))

    assert presence.status == SocialStatus.VERIFIED
    assert presence.confidence_score == 0.95
    verifier.close()


def test_a_fan_page_is_not_verified_for_a_bio_link():
    """The creator linked it, but the page says it is a fan account."""
    page = Page(
        url="https://www.instagram.com/creatorfans/",
        meta={"ogTitle": "Creator Fans (@creatorfans) - Instagram photos and videos"},
    )
    verifier = SocialVerifierTool(rendered_checker=lambda url: page)
    presence = _presence(SocialStatus.UNVERIFIED_HANDLE, source="bio_link")

    asyncio.run(verifier._rendered_fallback(presence, "instagram", CREATOR))

    assert presence.status == SocialStatus.UNVERIFIED_HANDLE
    assert presence.confidence_score == 0.55
    verifier.close()


def test_the_agent_cannot_verify_a_page_that_names_somebody_else():
    agent = _Agent(
        {
            "exists": "yes",
            "display_name": "Creator Fans",
            "handle": "creatorfans",
            "reason": "the profile is visible",
        }
    )
    verifier = SocialVerifierTool(agent_checker=agent)
    presence = _presence(SocialStatus.UNVERIFIED_HANDLE, source="bio_link")

    asyncio.run(verifier._agent_fallback(presence, "instagram", CREATOR))

    assert presence.status == SocialStatus.UNVERIFIED_HANDLE
    assert presence.confidence_score == 0.55
    verifier.close()


def test_the_agent_verifies_a_bio_link_the_page_confirms():
    agent = _Agent(
        {
            "exists": "yes",
            "display_name": "Creator",
            "handle": "creator",
            "reason": "the profile is visible",
        }
    )
    verifier = SocialVerifierTool(agent_checker=agent)
    presence = _presence(SocialStatus.UNVERIFIED_HANDLE, source="bio_link")

    asyncio.run(verifier._agent_fallback(presence, "instagram", CREATOR))

    assert presence.status == SocialStatus.VERIFIED
    verifier.close()


def test_a_model_guess_is_never_verified():
    """Even a page that matches the creator is only an unverified handle:
    the creator never said this is their account."""
    agent = _Agent({"exists": "yes", "display_name": "Creator", "handle": "creator"})
    verifier = SocialVerifierTool(agent_checker=agent)
    presence = _presence(SocialStatus.INCONCLUSIVE, source="model")

    asyncio.run(verifier._agent_fallback(presence, "instagram", CREATOR))

    assert presence.status == SocialStatus.UNVERIFIED_HANDLE
    assert presence.confidence_score == 0.60
    verifier.close()


def test_a_page_is_judged_the_same_way_by_the_browser_and_the_agent():
    """Both readers go through the same rule, so a fan page reads the same
    no matter who looked at it."""
    page = Page(
        url="https://www.instagram.com/creatorfans/",
        meta={"ogTitle": "Creator Fans (@creatorfans) - Instagram photos and videos"},
    )
    agent = _Agent({"exists": "yes", "display_name": "Creator Fans", "handle": "creatorfans"})

    rendered = SocialVerifierTool(rendered_checker=lambda url: page)
    read = _presence(SocialStatus.UNVERIFIED_HANDLE, source="bio_link")
    asyncio.run(rendered._rendered_fallback(read, "instagram", CREATOR))
    rendered.close()

    asked = SocialVerifierTool(agent_checker=agent)
    told = _presence(SocialStatus.UNVERIFIED_HANDLE, source="bio_link")
    asyncio.run(asked._agent_fallback(told, "instagram", CREATOR))
    asked.close()

    assert read.status == told.status
    assert read.confidence_score == told.confidence_score
