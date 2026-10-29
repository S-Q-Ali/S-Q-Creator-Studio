"""One line per operation, so a run can be read after the fact.

The activity log already shows the progress of a discovery run, but the
progress lines are for the user: they say what is happening now. An
*operation* line says what was *attempted* — which link was opened, which
engine answered, how long it took, what failed. The two are different
readers: the first wants to know where the run is, the second wants to know
why a verdict came out the way it did.

An ``Op`` is one such attempt. ``Ops`` writes it to a sink — the activity log
panel, a logger, or nothing at all in a test.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)

#: How an operation ended.
OK = "ok"
FAIL = "fail"
SKIP = "skip"
START = "start"

_MARKERS = {OK: "+", FAIL: "!", SKIP: "?", START: ">"}


@dataclass(frozen=True)
class Op:
    """One attempt: what was tried, on what, and what came back."""

    stage: str
    engine: str
    target: str
    outcome: str
    detail: str = ""
    error: str = ""
    duration_ms: int | None = None


def format_op(op: Op) -> str:
    """The line the activity log shows.

    ``+ browser.open | browser | https://instagram.com/x/ | 1.2s``
    """
    marker = _MARKERS.get(op.outcome, "-")
    parts = [f"{marker} {op.stage}", op.engine, op.target]
    if op.detail:
        parts.append(op.detail)
    if op.error:
        parts.append(f"error: {op.error}")
    if op.duration_ms is not None:
        parts.append(f"{op.duration_ms / 1000:.1f}s")
    return " | ".join(parts)


class Ops:
    """Writes operation lines to a sink.

    The sink is any callable taking one string. ``None`` writes nothing, which
    is what the tests use.
    """

    def __init__(self, sink: Callable[[str], None] | None = None):
        self._sink = sink

    def event(
        self,
        stage: str,
        engine: str,
        target: str,
        outcome: str,
        *,
        detail: str = "",
        error: str = "",
        duration_ms: int | None = None,
    ) -> Op:
        """Record one operation and return it."""
        op = Op(
            stage=stage,
            engine=engine,
            target=target,
            outcome=outcome,
            detail=detail,
            error=error,
            duration_ms=duration_ms,
        )
        line = format_op(op)
        logger.info("%s", line)
        if self._sink is not None:
            try:
                self._sink(line)
            except Exception as exc:  # pragma: no cover - the sink is the UI
                logger.warning("Operation log sink failed: %s", exc)
        return op

    def start(self, stage: str, engine: str, target: str, **detail) -> Op:
        """Record that an operation has begun."""
        return self.event(stage, engine, target, START, **detail)

    def ok(self, stage: str, engine: str, target: str, **detail) -> Op:
        """Record that an operation succeeded."""
        return self.event(stage, engine, target, OK, **detail)

    def fail(self, stage: str, engine: str, target: str, error: str, **detail) -> Op:
        """Record that an operation failed."""
        return self.event(stage, engine, target, FAIL, error=error, **detail)

    def skip(self, stage: str, engine: str, target: str, **detail) -> Op:
        """Record that an operation did not run."""
        return self.event(stage, engine, target, SKIP, **detail)
