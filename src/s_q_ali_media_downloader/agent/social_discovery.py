"""Social Discovery: from a channel to the creator's other accounts.

The pipeline is the one the specs describe, and it is Qt-free so it can be
tested without a display:

    resolve -> candidates -> (the agent, if the bio lists nothing) -> verify

The agent only ever proposes. Whether an account is the creator's is
decided by opening the account and reading what it says about itself.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from s_q_ali_media_downloader.agent.tools import social_judge as judge
from s_q_ali_media_downloader.agent.tools.social_resolve import (
    ChannelUnresolved,
    resolve_channel,
)
from s_q_ali_media_downloader.agent.tools.social_verify import (
    CreatorRef,
    Verdict,
    verify_candidates,
)

logger = logging.getLogger(__name__)

PLATFORMS = ("facebook", "instagram", "tiktok")

#: Where a candidate came from.
SOURCE_BIO = "bio"
SOURCE_MODEL = "model"


@dataclass
class PlatformOutcome:
    """What we found for one platform."""

    platform: str
    verdict: str = Verdict.UNKNOWN.value
    url: str = ""
    display_name: str = ""
    evidence: list[str] = field(default_factory=list)
    detail: str = ""
    source: str = ""

    @property
    def is_found(self) -> bool:
        return self.verdict == Verdict.FOUND.value


@dataclass
class DiscoveryResult:
    """Everything we know about one creator's other accounts."""

    query: str = ""
    title: str = ""
    handle: str = ""
    url: str = ""
    subscribers: int = 0
    platforms: list[PlatformOutcome] = field(default_factory=list)
    reason: str = ""
    warning: str = ""
    error: str = ""

    def outcome(self, platform: str) -> PlatformOutcome | None:
        for item in self.platforms:
            if item.platform == platform:
                return item
        return None

    @property
    def found_count(self) -> int:
        return sum(1 for item in self.platforms if item.is_found)


def discover(
    session,
    text: str,
    *,
    api_key: str | None = None,
    progress=None,
) -> DiscoveryResult:
    """Find one creator's Facebook, Instagram and TikTok accounts.

    ``session`` is a browser session; ``progress`` is called with a line of
    text as the work goes on.
    """

    def say(message: str) -> None:
        if progress:
            progress(message)

    say(f"Reading {text} ...")
    try:
        record = resolve_channel(text, session=session)
    except ChannelUnresolved as exc:
        return DiscoveryResult(query=text, error=str(exc))

    result = DiscoveryResult(
        query=text,
        title=record.title,
        handle=record.handle,
        url=record.url,
        subscribers=record.subscribers,
    )

    candidates = {
        platform: list(urls) for platform, urls in record.platform_candidates().items() if urls
    }
    bio_urls = {url for urls in candidates.values() for url in urls}

    # Ask the agent once per channel. The bio may list one platform and the
    # model can propose the rest; a missing key only matters when it is the
    # only source of candidates.
    if api_key or judge.groq_key() or not candidates:
        say("Asking the AI agent ...")
        try:
            proposal = judge.propose(
                record.title,
                record.handle,
                record.subscribers,
                record.description,
                api_key=api_key,
            )
        except judge.JudgeUnavailable as exc:
            if not candidates:
                result.reason = str(exc)
                result.error = str(exc)
                return result
            if "No Groq API key configured" not in str(exc):
                # The bio results are still good, but the user should know
                # why the other platforms are missing.
                result.warning = str(exc)
        else:
            result.reason = proposal.reason
            proposed = judge.candidate_urls(proposal)
            say(f"The agent proposed {sum(len(v) for v in proposed.values())} candidates.")
            for platform, urls in proposed.items():
                existing = candidates.setdefault(platform, [])
                for url in urls:
                    if url not in existing:
                        existing.append(url)

    creator = CreatorRef(title=record.title, handle=record.handle, url=record.url)
    for platform in PLATFORMS:
        urls = candidates.get(platform) or []
        if not urls:
            continue
        say(f"Checking {platform} ...")
        for check in verify_candidates(session, creator, {platform: urls}, bio_urls):
            result.platforms.append(
                PlatformOutcome(
                    platform=platform,
                    verdict=check.verdict.value,
                    url=check.url,
                    display_name=check.display_name,
                    evidence=list(check.evidence),
                    detail=check.detail,
                    source=check.source,
                )
            )
    return result
