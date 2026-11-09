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

from s_q_ali_media_downloader.agent.opslog import Ops
from s_q_ali_media_downloader.agent.tools import social_judge as judge
from s_q_ali_media_downloader.agent.tools.dual_check import (
    SearchBudget,
    ask_the_web,
    needs_the_second_check,
)
from s_q_ali_media_downloader.agent.tools.social_resolve import (
    ChannelUnresolved,
    ResolvedChannel,
    resolve_channel,
)
from s_q_ali_media_downloader.agent.tools.social_verify import (
    AI_UNKNOWN,
    AI_YES,
    RECONCILED_TO_VERDICT,
    CheckResult,
    CreatorRef,
    Verdict,
    reconcile,
    verify_candidate,
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
    tier: str = ""

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
    bio_candidates: int = 0
    ai_used: bool = False
    ai_provider: str = ""
    ai_candidates: int = 0
    browser_checks: int = 0

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
    agent_checker=None,
    progress=None,
    ops: Ops | None = None,
    budget: SearchBudget | None = None,
) -> DiscoveryResult:
    """Find one creator's Facebook, Instagram and TikTok accounts.

    ``session`` is a browser session; ``progress`` is called with a line of
    text as the work goes on.
    """

    def say(message: str) -> None:
        logger.info(message)
        if progress:
            progress(message)

    say(f"Reading {text} ...")
    try:
        record = resolve_channel(text, session=session)
    except ChannelUnresolved as exc:
        say(f"Could not resolve that channel: {exc}")
        return DiscoveryResult(query=text, error=str(exc))

    result = DiscoveryResult(
        query=text,
        title=record.title,
        handle=record.handle,
        url=record.url,
        subscribers=record.subscribers,
    )
    say(
        f"Resolved {record.title} (@{record.handle}) — "
        f"{record.subscribers:,} subscribers."
    )

    candidates = {
        platform: list(urls) for platform, urls in record.platform_candidates().items() if urls
    }
    bio_urls = {url for urls in candidates.values() for url in urls}
    result.bio_candidates = len(bio_urls)
    say(f"Bio links: {result.bio_candidates} candidate(s).")

    # Ask the agent once per channel. The bio may list one platform and the
    # model can propose the rest; a missing key only matters when it is the
    # only source of candidates.
    if api_key or judge.any_key() or not candidates:
        say("Asking the AI agent (Gemini first, Groq fallback) ...")
        logger.info(
            "AI hand-off for %s: Gemini first, Groq fallback",
            record.handle or record.title,
        )
        try:
            proposal = judge.propose(
                record.title,
                record.handle,
                record.subscribers,
                record.description,
                api_key=api_key,
                ops=ops,
            )
        except judge.JudgeUnavailable as exc:
            logger.warning("AI step unavailable for %s: %s", record.handle or record.title, exc)
            if not candidates:
                result.reason = str(exc)
                result.error = str(exc)
                return result
            if "No AI key configured" not in str(exc):
                # The bio results are still good, but the user should know
                # why the other platforms are missing.
                result.warning = str(exc)
        else:
            result.reason = proposal.reason
            result.ai_used = True
            result.ai_provider = proposal.provider
            proposed = judge.candidate_urls(proposal)
            result.ai_candidates = sum(len(urls) for urls in proposed.values())
            say(
                f"The {proposal.provider.title()} agent ({proposal.model}) "
                f"proposed {result.ai_candidates} candidates."
            )
            logger.info(
                "AI %s (%s) proposed %d candidates for %s",
                proposal.provider,
                proposal.model,
                result.ai_candidates,
                record.handle or record.title,
            )
            for platform, urls in proposed.items():
                existing = candidates.setdefault(platform, [])
                for url in urls:
                    if url not in existing:
                        existing.append(url)

    result.browser_checks = 0
    if agent_checker is not None and getattr(agent_checker, "configured", False):
        say(
            "AI browser ready for pages the rendered check cannot read "
            f"({getattr(agent_checker, 'remaining', 0)} check(s) available)."
        )
    creator = CreatorRef(
        title=record.title,
        handle=record.handle,
        url=record.url,
        channel_id=record.channel_id,
    )

    def count_check() -> None:
        result.browser_checks += 1

    checks: dict[str, list[CheckResult]] = {}
    for platform in PLATFORMS:
        urls = candidates.get(platform) or []
        if not urls:
            continue
        say(f"Checking {platform} ...")
        checks[platform] = verify_candidates(
            session,
            creator,
            {platform: urls},
            bio_urls,
            on_check=count_check,
            agent_checker=agent_checker,
            ops=ops,
        )
        for check in checks[platform]:
            say(
                f"{platform}: {check.verdict.value} — "
                f"{check.url or check.detail or 'no URL'}"
            )

    # The second check: the web is asked about the platforms the browser
    # could not confirm.
    reconciled = _second_check(
        session,
        creator,
        record,
        checks,
        candidates=candidates,
        bio_urls=bio_urls,
        budget=budget if budget is not None else SearchBudget(),
        ops=ops,
        say=say,
    )

    for platform in PLATFORMS:
        if platform in reconciled:
            result.platforms.append(reconciled[platform])
            continue
        for check in checks.get(platform, []):
            result.platforms.append(_outcome(platform, check))
    return result


def _outcome(platform: str, check: CheckResult) -> PlatformOutcome:
    """What we found for one platform."""
    return PlatformOutcome(
        platform=platform,
        verdict=check.verdict.value,
        url=check.url,
        display_name=check.display_name,
        evidence=list(check.evidence),
        detail=check.detail,
        source=check.source,
        tier=check.tier,
    )


def _second_check(
    session,
    creator: CreatorRef,
    record: ResolvedChannel,
    checks: dict[str, list[CheckResult]],
    *,
    candidates: dict[str, list[str]],
    bio_urls: set[str],
    budget: SearchBudget,
    ops: Ops | None,
    say,
) -> dict[str, PlatformOutcome]:
    """Ask the web about the platforms the browser could not confirm.

    The browser read the pages the bio — or the plain AI — named. Where it
    could not confirm the account, the web is asked as well: Gemini
    grounds its answer with Google Search, Groq with its browser search.
    The URL the web names is opened in the browser too, and the two
    answers are reconciled into one verdict.
    """
    wanted = []
    for platform in PLATFORMS:
        results = checks.get(platform) or []
        if needs_the_second_check(
            confirmed=any(r.verdict is Verdict.FOUND for r in results),
            from_bio=bool(results) and all(r.source == SOURCE_BIO for r in results),
            unreadable=any(r.verdict is Verdict.UNKNOWN for r in results),
        ):
            wanted.append(platform)
    if not wanted or not judge.any_key():
        return {}

    answer = ask_the_web(
        lambda: judge.propose_searched(
            record.title,
            record.handle,
            record.subscribers,
            record.description,
            platforms=tuple(wanted),
            ops=ops,
        ),
        budget=budget,
        platforms=wanted,
        ops=ops,
    )
    if answer is None:
        return {}

    out: dict[str, PlatformOutcome] = {}
    for platform in wanted:
        item = answer.get(platform)
        ai_exists = item.exists if item is not None else AI_UNKNOWN
        ai_url = item.url if item is not None else ""
        results = checks.get(platform) or []
        if ai_exists == AI_YES and ai_url:
            browser = verify_candidate(session, ai_url, platform, creator, ops=ops)
            if browser is not None:
                browser.source = SOURCE_MODEL
        else:
            browser = results[0] if results else _dropped_verdict(
                platform, candidates, bio_urls
            )
        result = reconcile(ai_exists, ai_url, browser)
        verdict = RECONCILED_TO_VERDICT[result.status]
        say(f"{platform}: {verdict.value} — {result.detail}")
        if ops is not None:
            ops.ok(
                "reconcile",
                "both",
                platform,
                detail=(
                    f"ai {ai_exists} + browser "
                    f"{browser.verdict.value if browser else 'no page'} -> "
                    f"{verdict.value}"
                ),
            )
        out[platform] = PlatformOutcome(
            platform=platform,
            verdict=verdict.value,
            url=(browser.url if browser and browser.url else ai_url),
            display_name=browser.display_name if browser else "",
            evidence=list(browser.evidence) if browser else [],
            detail=result.detail,
            source=(
                "both"
                if result.source == "both"
                else (browser.source if browser and browser.source else SOURCE_MODEL)
            ),
            tier=browser.tier if browser else "",
        )
    return out


def _dropped_verdict(
    platform: str,
    candidates: dict[str, list[str]],
    bio_urls: set[str],
) -> CheckResult | None:
    """The browser's verdict for a platform whose candidates were all dropped.

    ``verify_candidates`` drops a candidate whose page says the account is
    not there, so the reading is not lost — it is kept here.
    """
    urls = candidates.get(platform) or []
    if not urls:
        return None
    url = urls[0]
    return CheckResult(
        platform=platform,
        verdict=Verdict.NOT_FOUND,
        url=url,
        detail="the page says the account is not there",
        source=SOURCE_BIO if url in bio_urls else SOURCE_MODEL,
    )
