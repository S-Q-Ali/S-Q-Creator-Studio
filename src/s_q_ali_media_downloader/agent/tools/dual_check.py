"""The second check: ask the web, then let the browser confirm.

One question, two methods. The search-grounded AI reads the web and can
only *propose* a URL; the browser opens the page and reads what the
account says about itself, so the browser is the one that decides. This
module holds what the three discovery modes share: when the second check
is worth the call, how many calls one run may make, and how the ask is
made.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence

from s_q_ali_media_downloader.agent.opslog import Ops
from s_q_ali_media_downloader.agent.schema import SocialStatus
from s_q_ali_media_downloader.agent.tools.social_judge import AiAnswer, JudgeUnavailable
from s_q_ali_media_downloader.agent.tools.social_verify import Reconciled

logger = logging.getLogger(__name__)

#: How many search-grounded calls one run may make. A free Gemini key gets
#: a daily allowance per model and every call is one request: without a
#: cap a run with fifty channels spends the whole day on the first one.
MAX_SEARCHES_PER_RUN = 5


class SearchBudget:
    """How many search-grounded calls this run may still make."""

    def __init__(self, limit: int = MAX_SEARCHES_PER_RUN):
        self.limit = limit
        self.spent = 0

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.spent)

    def take(self) -> bool:
        """Take one call from the budget. False when it is spent."""
        if self.spent >= self.limit:
            return False
        self.spent += 1
        return True


def needs_the_second_check(
    *, confirmed: bool, from_bio: bool, unreadable: bool
) -> bool:
    """True when this platform is worth asking the web about.

    The web is asked when the creator's own bio says nothing about the
    platform — the account then rests on the plain AI's guess — and when
    the browser could not read the page at all. A link the browser read
    and confirmed needs nothing more, and neither does a creator's own
    link that the browser read and rejected: the page is the judge.
    """
    if confirmed:
        return False
    if from_bio:
        return unreadable
    return True


def ask_the_web(
    ask: Callable[[], AiAnswer],
    *,
    budget: SearchBudget,
    platforms: Sequence[str],
    ops: Ops | None = None,
) -> AiAnswer | None:
    """Ask the web about the platforms, if the budget allows one more call.

    None when the budget is spent or no provider answered: the browser's
    answer then stands on its own, which is the way it should be.
    """
    if not platforms:
        return None
    if not budget.take():
        message = (
            f"the search budget for this run is spent ({budget.limit} calls); "
            f"{len(platforms)} platform(s) keep the browser's answer"
        )
        logger.info("%s", message)
        if ops is not None:
            ops.skip("budget", "ai", "search", detail=message)
        return None
    try:
        answer = ask()
    except JudgeUnavailable as exc:
        logger.info("the search-grounded ask did not answer: %s", exc)
        if ops is not None:
            ops.fail(
                "budget",
                "ai",
                "search",
                str(exc),
                detail=f"{budget.spent}/{budget.limit} spent",
            )
        return None
    if ops is not None:
        ops.ok(
            "budget",
            "ai",
            "search",
            detail=f"{budget.spent}/{budget.limit} spent, {budget.remaining} left",
        )
    return answer


#: Mode 2 asks "does this creator have a YouTube channel", not "does this
#: account exist". A channel the browser opened and found to belong to
#: somebody else is not this creator's channel, and a lead the browser
#: could not confirm is not a channel either — the app asks the user to
#: look instead of guessing either way.
YOUTUBE_RECONCILED_TO_STATUS = {
    Reconciled.VERIFIED: (SocialStatus.VERIFIED, 0.95),
    Reconciled.WEAK: (SocialStatus.NOT_FOUND, 0.0),
    Reconciled.UNCONFIRMED: (SocialStatus.INCONCLUSIVE, 0.0),
    Reconciled.MISSING: (SocialStatus.NOT_FOUND, 0.0),
    Reconciled.UNKNOWN: (SocialStatus.INCONCLUSIVE, 0.0),
}
