"""Formatting helpers that more than one place needs.

The subscriber count was written twice - once for YouTube, once for TikTok -
and the two copies drifted apart in the past. One function, one answer.
"""

from __future__ import annotations


def format_count(value: int) -> str:
    """A count as short text: 1820000 -> ``1.8M``, 1500 -> ``1.5K``."""
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return str(value)
