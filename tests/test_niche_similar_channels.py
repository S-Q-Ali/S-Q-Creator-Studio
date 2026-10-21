"""Tests for the similar-channel finder (the "Create Similar Channel" feature)."""

from __future__ import annotations

import pytest

from s_q_ali_media_downloader.niche_research.research import ai_analysis_engine as ai
from s_q_ali_media_downloader.niche_research.storage import db


@pytest.fixture(autouse=True)
def _db(isolated_appdata):
    db.configure(None)
    yield
    db.close_db()


def _add(channel_id: str, title: str, *, niche: str, subs: int, viral: int, fmt: str = "longform"):
    db.run(
        "INSERT INTO trending_channels (channel_id, title, category_name, discovered_at, "
        "viral_score, subscriber_count, niche, video_format) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (channel_id, title, "Cat", 1, viral, subs, niche, fmt),
    )


def test_find_similar_channels_excludes_the_channel_itself(isolated_appdata):
    _add("UCa", "Alpha", niche="tech_ai", subs=1000, viral=80)
    _add("UCb", "Beta", niche="tech_ai", subs=900, viral=75)

    similar = ai.find_similar_channels("UCa")

    assert [c["channel_id"] for c in similar] == ["UCb"]
    assert similar[0]["similarity"] > 0


def test_find_similar_channels_scores_the_same_niche_higher(isolated_appdata):
    _add("UCa", "Alpha", niche="tech_ai", subs=1000, viral=80)
    _add("UCb", "Same niche", niche="tech_ai", subs=1000, viral=80)
    _add("UCc", "Other niche", niche="cooking", subs=1000, viral=80)

    similar = ai.find_similar_channels("UCa")

    assert similar[0]["channel_id"] == "UCb"
    assert similar[0]["similarity"] > similar[1]["similarity"]


def test_find_similar_channels_of_an_unknown_channel(isolated_appdata):
    assert ai.find_similar_channels("UCmissing") == []


def test_find_similar_channels_respects_the_limit(isolated_appdata):
    _add("UCa", "Alpha", niche="tech_ai", subs=1000, viral=80)
    for i in range(8):
        _add(f"UC{i}", f"Other {i}", niche="tech_ai", subs=1000, viral=70)

    assert len(ai.find_similar_channels("UCa", limit=3)) == 3
