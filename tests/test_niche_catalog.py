"""Tests for the niche catalog (ported from the companion research web tool's lib/niches.ts)."""

from s_q_ali_media_downloader.niche_research.data.niches import (
    LONGFORM,
    LONGFORM_NICHES,
    NICHES,
    SHORTFORM,
    SHORTFORM_NICHES,
    format_name,
    get_niche,
    get_niches,
)


def test_longform_count_matches_source():
    assert len(LONGFORM_NICHES) == 25


def test_shortform_count_matches_source():
    assert len(SHORTFORM_NICHES) == 26


def test_every_niche_has_queries_and_rpm():
    for fmt in (LONGFORM, SHORTFORM):
        for niche in NICHES[fmt.id].values():
            assert niche.queries
            assert len(niche.queries) >= 3
            assert niche.rpm.min > 0
            assert niche.rpm.max > 0
            assert niche.rpm.min <= niche.rpm.avg <= niche.rpm.max
            assert niche.competition in {"low", "medium", "high"}
            assert niche.difficulty in {"easy", "medium", "hard"}


def test_no_duplicate_niche_ids_within_format():
    for fmt in (LONGFORM, SHORTFORM):
        ids = list(NICHES[fmt.id].keys())
        assert len(ids) == len(set(ids))


def test_format_shared_ids_are_reused_like_source():
    # S-Q-Ali Media Downloader reuses the same id across formats (e.g. faceless, tech_ai).
    assert NICHES["longform"]["faceless"].name == "Faceless YouTube"
    assert NICHES["shortform"]["faceless"].name == "Faceless Shorts"


def test_known_niche_properties():
    finance = LONGFORM_NICHES["finance"]
    assert finance.name == "Finance"
    assert finance.competition == "medium"
    assert finance.difficulty == "hard"
    assert finance.rpm.min == 6.0
    assert finance.rpm.max == 18.0
    assert finance.rpm.avg == 12.0

    faceless_short = SHORTFORM_NICHES["faceless"]
    assert faceless_short.rpm.avg < finance.rpm.avg


def test_getters():
    assert format_name("longform") == "Longform"
    assert format_name("shortform") == "Shortform"
    assert format_name("nope") == "nope"
    assert len(get_niches("longform")) == 25
    assert len(get_niches("shortform")) == 26
    assert len(get_niches()) == len(set(list(LONGFORM_NICHES) + list(SHORTFORM_NICHES)))
    assert get_niche("longform", "tech_ai").id == "tech_ai"
    assert get_niche("shortform", "missing") is None
