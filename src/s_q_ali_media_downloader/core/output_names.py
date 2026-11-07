"""The name a leg writes to: never one that is already taken.

A results folder is the user's. A file they put there, or one an earlier run
made, is not theirs to lose, so both legs pick a name that is free and keep
the family readable: ``Film_9x16 Part 2.mp4`` is the second vertical of the
same film, ``Film Part 6.mp4`` the sixth piece of it cut at the pauses.

The copy of the source a Studio run stages has its own older rule - the
``(2)`` suffix in :func:`engine.unique_basename` - and stays as it is: two
copies of a film are the same film, while two parts of it are not.
"""

from __future__ import annotations

import os
import re


def next_part_path(folder: str, base: str, ext: str = ".mp4") -> str:
    """The first of ``base``, ``base Part 2``, ``base Part 3``... free in folder.

    Nothing is created here: the caller holds the name by writing it, and the
    gap between this answer and that write is a thread's width at worst, with
    one worker per folder in practice.
    """
    candidate = os.path.join(folder, base + ext)
    n = 2
    while os.path.lexists(candidate):
        candidate = os.path.join(folder, f"{base} Part {n}{ext}")
        n += 1
    return candidate


def next_part_start(folder: str, stem: str, ext: str = ".mp4") -> int:
    """One past the highest ``<stem> Part N<ext>`` in the folder, else one.

    A new cut continues where the last stopped rather than filling its gaps:
    two runs over the same film can then never point at the same name.
    """
    pattern = re.compile(rf"^{re.escape(stem)} Part (\d+){re.escape(ext)}$")
    try:
        names = os.listdir(folder)
    except OSError:
        names = []
    return max(
        (int(match.group(1)) for name in names if (match := pattern.match(name))),
        default=0,
    ) + 1
