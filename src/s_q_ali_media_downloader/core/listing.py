"""The shape a platform listing comes back in.

Instagram and Facebook list their videos in two different ways, but the queue
only ever wants the same thing: a list of page permalinks, and the reason
the list stopped short when it did.

The reason is the honest part. Instagram cuts a long walk off, and Facebook
shows a visitor the first screen of its list — a list that silently stops
halfway reads like a complete one.
"""

from __future__ import annotations

from collections.abc import Iterable


class Listing(list):
    """The permalinks one listing found, and why it stopped short.

    It is a plain list of URLs, so a caller that only wants the URLs ignores
    ``reason``.
    """

    def __init__(self, urls: Iterable[str] = (), reason: str = "") -> None:
        super().__init__(urls)
        self.reason = reason
