"""An optional AI-agent browser for the pages a script cannot read.

The deterministic verifier is the source of truth. It reads the rendered
page with fixed rules, and those rules are what decide whether an account
exists and whose it is. Some pages still defeat it: a consent wall, a blank
shell, a login gate, or a page that renders differently on every visit.

For those pages only, this module drives `browser-use` — a real browser
controlled by the same Groq/Gemini models the rest of the agent uses. It
opens the same persistent profile, looks at the page, and answers with
facts it copied from the page. The answer is then fed back through the
deterministic matching rules; the model never gets to invent a finding.

Design rules:

* ``browser-use`` is optional. Without it, the feature says what to
  install instead of crashing.
* Gemini is tried first, Groq second — the same order as the judge. Every
  model in Gemini's chain gets a turn before the next provider does, so a
  free key whose daily allowance is spent on one model still has two left.
* The agent is capped per run (``MAX_AGENT_CHECKS``), so a run cannot
  spend minutes on a page that will never answer.
* Telemetry is turned off before the package is imported. The cloud sync
  is off too: everything stays on this machine.
* The model must quote the page. A "no" without an explicit not-found
  quote is downgraded to "unknown", and a login wall is never a "no".
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from s_q_ali_media_downloader.agent.opslog import Ops
from s_q_ali_media_downloader.agent.tools import social_judge as judge
from s_q_ali_media_downloader.agent.tools.social_verify import NOT_FOUND_SIGNATURES

logger = logging.getLogger(__name__)

#: How many pages one run may hand to the AI browser.
MAX_AGENT_CHECKS = 3

#: How many agent steps one page may take. Reading a profile is short; a
#: higher limit only gives the model more chances to wander.
DEFAULT_MAX_STEPS = 8

#: Per-attempt limits. The whole check can run twice (Groq, then Gemini).
DEFAULT_ATTEMPT_TIMEOUT = 90.0
DEFAULT_STEP_TIMEOUT = 45
DEFAULT_LLM_TIMEOUT = 30

#: Words that mean the page was gated, not that the account is missing.
_WALL_WORDS = (
    "log in",
    "login",
    "sign in",
    "captcha",
    "consent",
    "rate limit",
    "too many requests",
    "try again",
    "access denied",
)

#: A "no" is only accepted when the quote looks like a missing-page message.
_MISSING_WORDS = (
    "not available",
    "not found",
    "doesn't exist",
    "does not exist",
    "couldn't find",
    "could not find",
    "no longer available",
    "page isn't available",
    "page is not available",
)


class AgentProfile(BaseModel):
    """What the AI browser saw. Every field is a copy from the page."""

    exists: str = Field(
        default="unknown",
        description='One of "yes", "no", or "unknown". A gated or blank page is "unknown".',
    )
    display_name: str = Field(default="", description="The account's display name, exactly as shown.")
    handle: str = Field(default="", description="The account's @handle or username, exactly as shown.")
    followers: str = Field(default="", description="The follower count, exactly as shown.")
    quote: str = Field(
        default="",
        description=(
            "For a no, the exact sentence that says the page is missing. "
            "For a yes, the text the name/handle/followers were copied from."
        ),
    )
    reason: str = Field(default="", description="One short sentence explaining the answer.")


def _clean(value: Any, limit: int) -> str:
    text = str(value or "").strip()
    return text[:limit]


def _exists(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"yes", "y", "true"}:
        return "yes"
    if text in {"no", "n", "false"}:
        return "no"
    return "unknown"


def _looks_missing(quote: str) -> bool:
    text = (quote or "").lower()
    if any(sig in text for sig in NOT_FOUND_SIGNATURES):
        return True
    return any(word in text for word in _MISSING_WORDS)


def _looks_gated(quote: str) -> bool:
    text = (quote or "").lower()
    return any(word in text for word in _WALL_WORDS)


def _loads(raw: Any) -> dict[str, Any]:
    """Read a structured answer or the model's JSON text."""
    if isinstance(raw, BaseModel):
        return raw.model_dump()
    if isinstance(raw, dict):
        return raw
    text = str(raw or "").strip()
    if not text:
        return {}
    if text.startswith("```"):
        lines = [line for line in text.splitlines() if not line.strip().startswith("```")]
        text = "\n".join(lines).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def parse_answer(raw: Any) -> AgentProfile:
    """Validate the model's answer. Anything doubtful becomes "unknown".

    The model is allowed to say "no" only with an explicit missing-page
    quote. A login wall, a blank page, or a quote that is not about a
    missing account is "unknown" — never "not found".
    """
    data = _loads(raw)
    if not data:
        return AgentProfile(reason="the AI browser did not answer with JSON")

    exists = _exists(data.get("exists"))
    quote = _clean(data.get("quote"), 300)
    name = _clean(data.get("display_name"), 120)
    handle = _clean(data.get("handle"), 60).lstrip("@")
    followers = _clean(data.get("followers"), 40)
    reason = _clean(data.get("reason"), 240)

    if exists == "no":
        if not quote:
            return AgentProfile(
                exists="unknown",
                reason="the AI browser said no without quoting the page",
            )
        if _looks_gated(quote) or not _looks_missing(quote):
            return AgentProfile(
                exists="unknown",
                quote=quote,
                reason="the quoted page text is not a missing-account message",
            )
        return AgentProfile(
            exists="no",
            quote=quote,
            reason=reason or "the page says the account is missing",
        )

    if exists == "yes":
        if not (name or handle or followers):
            return AgentProfile(
                exists="unknown",
                quote=quote,
                reason="the AI browser said yes without a name, handle, or follower count",
            )
        return AgentProfile(
            exists="yes",
            display_name=name,
            handle=handle,
            followers=followers,
            quote=quote,
            reason=reason or "the AI browser read the profile",
        )

    return AgentProfile(quote=quote, reason=reason or "the AI browser could not decide")


def provider_choices(
    groq_api_key: str | None = None,
    gemini_api_key: str | None = None,
) -> list[tuple[str, str, str]]:
    """The providers to try, Gemini first. Empty when no key is configured."""
    choices: list[tuple[str, str, str]] = []
    gemini = (gemini_api_key or judge.gemini_key() or "").strip()
    if gemini:
        choices.append(("gemini", gemini, judge.GEMINI_MODEL))
    groq = (groq_api_key or judge.groq_key() or "").strip()
    if groq:
        choices.append(("groq", groq, judge.DEFAULT_MODEL))
    return choices


def provider_choice(
    groq_api_key: str | None = None,
    gemini_api_key: str | None = None,
) -> tuple[str, str, str] | None:
    """The first provider that would be tried, or None."""
    choices = provider_choices(groq_api_key, gemini_api_key)
    return choices[0] if choices else None


def build_task(url: str, platform: str) -> str:
    """The task for the agent. It reads one page and copies what it sees."""
    return f"""Open this {platform} page and read what it shows:

{url}

Do this:
1. Open the URL (it may already be open).
2. If a cookie or consent dialog covers the page, accept only what is
   needed to see the page.
3. Read only what the rendered page shows. Do not search, do not follow
   recommendations, and do not click Follow, Like, or Message.

Answer with these fields:
- exists: "yes" if the page shows a profile, account, or page; "no" only
  if the page explicitly says it is missing; otherwise "unknown".
- display_name: the account's display name exactly as shown, or "".
- handle: the account's @handle or username exactly as shown, or "".
- followers: the follower count exactly as shown, or "".
- quote: for "no", the exact sentence that says the page is missing. For
  "yes", the text the name, handle, or follower count was copied from.
- reason: one short sentence.

Rules:
- A login wall, consent wall, blank page, CAPTCHA, rate limit, or network
  error is "unknown". Never "no".
- Never infer anything from the URL, the handle, search results, or what
  you already know about this creator.
- "yes" requires a display name, a handle, or a follower count copied from
  the page.
- Do not change anything on the page.
"""


def _prepare_environment() -> None:
    """Keep browser-use local: no telemetry, no cloud sync, quiet logs."""
    os.environ["ANONYMIZED_TELEMETRY"] = "false"
    os.environ["BROWSER_USE_CLOUD_SYNC"] = "false"
    os.environ.setdefault("BROWSER_USE_LOGGING_LEVEL", "warning")


def available() -> bool:
    """True when the optional browser-use package is installed."""
    try:
        return importlib.util.find_spec("browser_use") is not None
    except (ImportError, ValueError):
        return False


@dataclass
class AgentBrowserChecker:
    """A sync callable that asks the AI browser about one page.

    The caller owns the thread: browser-use starts its own browser and its
    own event loop, so this must not run on the GUI thread.
    """

    headless: bool = True
    profile_dir: str | os.PathLike | None = None
    executable_path: str | os.PathLike | None = None
    max_checks: int = MAX_AGENT_CHECKS
    max_steps: int = DEFAULT_MAX_STEPS
    attempt_timeout: float = DEFAULT_ATTEMPT_TIMEOUT
    step_timeout: int = DEFAULT_STEP_TIMEOUT
    llm_timeout: int = DEFAULT_LLM_TIMEOUT
    groq_api_key: str | None = None
    gemini_api_key: str | None = None
    log_callback: Callable[[str], None] | None = None
    ops: Ops | None = None
    _checks: int = 0

    def __post_init__(self) -> None:
        if self.ops is None:
            self.ops = Ops(self.log_callback)

    def _log(self, message: str) -> None:
        logger.info(message)
        if self.log_callback:
            try:
                self.log_callback(message)
            except Exception as exc:
                logger.warning("AI browser log callback error: %s", exc)

    @property
    def remaining(self) -> int:
        return max(0, self.max_checks - self._checks)

    @property
    def configured(self) -> bool:
        return bool(provider_choices(self.groq_api_key, self.gemini_api_key))

    def close(self) -> None:
        """Nothing is kept open between checks."""

    def __call__(self, url: str, platform: str) -> AgentProfile:
        if not (url or "").strip():
            return AgentProfile(reason="there is no URL to check")
        if not available():
            return AgentProfile(
                reason=(
                    "the AI browser is not installed; install the 'agent' "
                    "extra or browser-use"
                )
            )
        if not self.configured:
            return AgentProfile(reason="no AI key is configured")
        if self._checks >= self.max_checks:
            return AgentProfile(reason="the AI browser check limit for this run is spent")

        self._checks += 1
        try:
            return asyncio.run(self._check(url, platform))
        except Exception as exc:
            logger.warning("AI browser check failed for %s: %s", url, exc)
            self._log(f"AI browser check failed for {url}: {exc}")
            return AgentProfile(reason=f"the AI browser failed: {exc}")

    async def _check(self, url: str, platform: str) -> AgentProfile:
        _prepare_environment()
        choices = provider_choices(self.groq_api_key, self.gemini_api_key)
        errors: list[str] = []
        for provider, key, model in choices:
            # A free Gemini key has a daily allowance per model, so every
            # model in the chain gets a turn before the next provider does.
            models = judge.gemini_models(model) if provider == "gemini" else (model,)
            for name in models:
                self.ops.start(
                    "ai.browser.ask",
                    "ai-browser",
                    url,
                    detail=f"{provider} {name} reading {platform}",
                )
                self._log(
                    f"AI browser: {provider} ({name}) is reading {platform} {url} ..."
                )
                try:
                    answer = await self._run(provider, key, name, url, platform)
                except Exception as exc:
                    message = str(exc)
                    if "413" in message or "tokens per minute" in message.lower():
                        message += (
                            " (Groq's free tier cannot carry a browser page; "
                            "raise the Groq limit or wait for the rate limit to clear)"
                        )
                    elif "RESOURCE_EXHAUSTED" in message or "quota" in message.lower():
                        message += (
                            " (this Gemini model's daily allowance is spent; "
                            "the next model in the chain gets a turn)"
                        )
                    errors.append(f"{provider} ({name}): {message}")
                    self.ops.fail(
                        "ai.browser.ask",
                        "ai-browser",
                        url,
                        message,
                        detail=f"{provider} {name}",
                    )
                    self._log(f"AI browser: {provider} failed for {url}: {message}")
                    continue
                self.ops.ok(
                    "ai.browser.ask",
                    "ai-browser",
                    url,
                    detail=f"{provider} {name} -> {answer.exists}",
                )
                return answer
        return AgentProfile(reason="no AI provider answered: " + " | ".join(errors))

    async def _run(
        self,
        provider: str,
        key: str,
        model: str,
        url: str,
        platform: str,
    ) -> AgentProfile:
        from browser_use import Agent, BrowserProfile, BrowserSession, ChatGoogle, ChatGroq

        # Gemini 3 rejects a temperature, so only Groq gets one. One retry
        # each: a token-limit error is not going to fix itself, and the next
        # provider should get its turn.
        llm = (
            ChatGroq(model=model, api_key=key, temperature=0.0, max_retries=1)
            if provider == "groq"
            else ChatGoogle(model=model, api_key=key, max_retries=1)
        )
        profile_kwargs: dict[str, Any] = {
            "headless": self.headless,
            "keep_alive": False,
            "args": ["--no-first-run", "--no-default-browser-check"],
            "highlight_elements": False,
            # The default extensions are downloaded on first launch. The
            # deterministic browser already handles consent, and the agent
            # only reads one page, so the download is not worth it.
            "enable_default_extensions": False,
        }
        if self.executable_path:
            profile_kwargs["executable_path"] = str(self.executable_path)
        if self.profile_dir:
            profile_kwargs["user_data_dir"] = str(self.profile_dir)
        browser_profile = BrowserProfile(**profile_kwargs)
        session = BrowserSession(browser_profile=browser_profile)
        agent = None
        try:
            agent = Agent(
                task=build_task(url, platform),
                llm=llm,
                browser_session=session,
                output_model_schema=AgentProfile,
                use_vision=False,
                use_thinking=False,
                max_actions_per_step=2,
                max_failures=2,
                max_history_items=6,
                step_timeout=self.step_timeout,
                llm_timeout=self.llm_timeout,
                enable_planning=False,
                enable_signal_handler=False,
                register_new_step_callback=self._on_step,
            )
            history = await asyncio.wait_for(
                agent.run(max_steps=self.max_steps), timeout=self.attempt_timeout
            )
            answer = getattr(history, "structured_output", None)
            if answer is None:
                final = getattr(history, "final_result", lambda: "")()
                answer = final
            if not answer:
                # browser-use swallows a provider error into the history.
                # Raise it so the next provider gets a turn instead of
                # reporting a page as unreadable.
                errors = [
                    str(error)
                    for error in (getattr(history, "errors", list)() or [])
                    if error
                ]
                detail = "; ".join(errors[-2:]) or "the agent stopped without an answer"
                raise RuntimeError(detail)
            parsed = parse_answer(answer)
            self._log(
                f"AI browser: {platform} {url} -> {parsed.exists} "
                f"({parsed.reason or 'no reason given'})"
            )
            return parsed
        finally:
            if agent is not None:
                try:
                    await agent.close()
                except Exception as exc:
                    logger.debug("closing the AI browser failed: %s", exc)
            self._remove_profile_copy(browser_profile)

    def _remove_profile_copy(self, browser_profile: Any) -> None:
        """browser-use copies a Chrome profile; do not leave cookies behind."""
        copied = str(getattr(browser_profile, "user_data_dir", "") or "")
        original = str(self.profile_dir or "")
        if (
            copied
            and copied != original
            and "browser-use-user-data-dir-" in copied.lower()
        ):
            shutil.rmtree(copied, ignore_errors=True)

    def _on_step(self, state: Any, output: Any, step: int) -> None:
        goal = getattr(output, "next_goal", "") or ""
        if not goal:
            current = getattr(output, "current_state", None)
            goal = getattr(current, "next_goal", "") or ""
        page_url = getattr(state, "url", "") or ""
        self._log(f"AI browser step {step}: {goal or 'reading the page'} ({page_url})")
