"""Theme palette and stylesheet invariants."""

from s_q_ali_media_downloader.theme import STATUS_COLORS, STYLESHEET, C

REQUIRED_KEYS = (
    "bg",
    "panel",
    "raised",
    "border",
    "text",
    "muted",
    "faint",
    "accent",
    "accent_hi",
    "amber",
    "done",
    "failed",
    "queued",
    "waiting",
)

STATES = (
    "Queued",
    "Downloading",
    "Retrying",
    "Waiting",
    "Paused",
    "Completed",
    "Failed",
    "Skipped",
)


def test_palette_has_required_keys():
    for key in REQUIRED_KEYS:
        assert key in C


def test_palette_colours_are_hex():
    for value in C.values():
        assert value.startswith("#") and len(value) == 7


def test_status_colours_cover_all_states():
    for state in STATES:
        assert state in STATUS_COLORS


def test_accent_is_cyan():
    assert C["accent"] == "#22D3EE"


def test_stylesheet_references_accent():
    assert C["accent"] in STYLESHEET


def test_stylesheet_is_a_single_stylesheet():
    assert STYLESHEET.lstrip().startswith("QWidget")
