"""The glass token set and the stylesheet it renders into.

The palette is black, white, grey and one blue. Glass is specified in alphas,
but readability has to be judged on the solid colour each alpha actually
flattens to, so both numbers live in ``theme.py`` and this file proves they
agree.
"""

import re

import pytest

from s_q_ali_media_downloader.theme import (
    GLASS,
    STATUS_COLORS,
    STYLESHEET,
    TEXT_SURFACES,
    C,
    flatten,
    rgba,
    stylesheet,
)

REQUIRED_KEYS = (
    "bg",
    "panel",
    "raised",
    "raised_hi",
    "border",
    "text",
    "muted",
    "faint",
    "accent",
    "accent_hi",
    "accent_deep",
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
)

WEB_ONLY = ("box-shadow", "text-shadow", "transition", "backdrop-filter", "opacity:")


def _rgb(value: str) -> tuple[int, int, int]:
    return tuple(int(value[i : i + 2], 16) for i in (1, 3, 5))


def _channel(value: float) -> float:
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def _luminance(hex_value: str) -> float:
    r, g, b = (c / 255.0 for c in _rgb(hex_value))
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast(a: str, b: str) -> float:
    la, lb = _luminance(a), _luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _rule(css: str, selector: str) -> str:
    """The body of one rule, so a test can look inside a single block."""
    block = re.search(rf"(?m)^{re.escape(selector)}\s*\{{([^}}]*)\}}", css)
    assert block, f"{selector} has no rule in the stylesheet"
    return block.group(1)


def test_palette_has_required_keys():
    for key in REQUIRED_KEYS:
        assert key in C


def test_palette_colours_are_hex():
    for value in C.values():
        assert value.startswith("#") and len(value) == 7


def test_palette_stays_in_black_white_grey_and_blue():
    """No hue the brief does not allow: every token is neutral, or blue."""
    for key, value in C.items():
        red, green, blue = _rgb(value)
        if key in {"bg", "panel", "raised", "raised_hi", "border", "text", "muted", "faint", "done"}:
            assert blue >= red, f"{key} is warm, and the palette has no warm neutrals"
        else:
            assert blue > green > red or abs(blue - green) < 8, f"{key} is not a blue"


def test_the_rendered_sheet_holds_no_warm_colour():
    """Red above blue is the tell of a warm hue, and the sheet is what paints.

    The token table can be clean while a literal left over in the CSS is not,
    so both renders are read rather than the dictionary alone.
    """
    for density in ("comfortable", "compact"):
        for colour in re.findall(r"#[0-9A-Fa-f]{6}", stylesheet(density)):
            red, _, blue = _rgb(colour)
            assert blue >= red, f"{colour} is warm in the {density} render"


def test_status_colours_cover_all_states():
    for state in STATES:
        assert state in STATUS_COLORS


def test_accent_is_the_signal_blue():
    assert C["accent"] == "#2F81F7"


def test_glass_is_three_elevations_and_two_edges():
    assert GLASS["low"] < GLASS["mid"] < GLASS["high"]
    assert GLASS["high"] <= 0.10, "above this a panel stops reading as glass"
    assert GLASS["hairline"] > GLASS["high"], "the lit top edge must beat the fill"
    assert GLASS["glow"] > GLASS["hairline"]


def test_rgba_emits_what_qss_paints():
    assert rgba("#FFFFFF", 0.07) == "rgba(255, 255, 255, 0.07)"


def test_the_panel_solid_is_the_glass_flattened():
    """The solid token and the alpha it replaces can never drift apart."""
    assert C["panel"] == flatten(C["bg"], "#FFFFFF", GLASS["mid"])
    assert C["raised"] == flatten(C["bg"], "#FFFFFF", GLASS["high"])


def test_text_clears_aa_on_the_surface_it_sits_on():
    for role, (foreground, surface) in TEXT_SURFACES.items():
        assert contrast(C[foreground], C[surface]) >= 4.5, f"{role} fails AA"


def test_the_action_fill_holds_chalk_text():
    """The darkest blue that can still carry body-size text at 4.5:1."""
    assert contrast(C["text"], C["accent_deep"]) >= 4.5


def test_every_spine_is_visible_against_a_panel():
    """A 3px bar is a non-text control: WCAG asks 3:1, not 4.5:1."""
    for state, colour in STATUS_COLORS.items():
        assert contrast(colour, C["panel"]) >= 3.0, f"{state}'s spine is invisible"


def test_every_status_label_is_readable_on_a_panel():
    """The same colour is also written as the status word, and that is text.

    A spine can be dim; a label cannot. This is the gate that decides the
    palette, because the strict brief has no red left to lean on.
    """
    for state, colour in STATUS_COLORS.items():
        assert contrast(colour, C["panel"]) >= 4.5, f"{state} as a label fails AA"


def test_the_failed_chip_is_chalk_under_void_text():
    """Failed inverts: the one chip in the app that flips foreground and fill."""
    assert contrast(C["bg"], C["failed"]) >= 4.5


def test_the_state_language_reads_in_three_groups():
    """Grey is not moving, blue is moving, chalk is finished.

    The ramp is the only thing that tells seven states apart once the hue is
    gone, so the groups are asserted rather than left to the token names.
    """
    assert contrast(STATUS_COLORS["Queued"], C["panel"]) < contrast(
        STATUS_COLORS["Paused"], C["panel"]
    ), "a queued job must not outshine one the user stopped"
    for state in ("Downloading", "Waiting", "Retrying"):
        colour = STATUS_COLORS[state]
        red, green, blue = _rgb(colour)
        assert blue > green > red, f"{state} left the blue family"
    assert contrast(STATUS_COLORS["Failed"], C["panel"]) > contrast(
        STATUS_COLORS["Completed"], C["panel"]
    ), "the terminal failure is the brightest thing in the list"


def test_spines_are_seven_distinct_values():
    assert len(set(STATUS_COLORS.values())) == len(STATUS_COLORS)


def test_sheet_painted_glass_where_glass_belongs():
    assert rgba("#FFFFFF", GLASS["mid"]) in STYLESHEET


def test_sheet_keeps_the_reading_surfaces_opaque():
    """Rows, popups and tooltips sit over an arbitrary desktop, not over glass."""
    for selector in ("QToolTip", "QTableWidget", "QComboBox QAbstractItemView"):
        assert "rgba" not in _rule(STYLESHEET, selector), f"{selector} went translucent"


def test_sheet_carries_no_property_qt_cannot_do():
    for needle in WEB_ONLY:
        assert needle not in STYLESHEET, f"{needle} is web CSS; Qt drops the rule after it"


def test_sheet_covers_every_widget_the_app_paints():
    """The merged sheet must not lose a selector the live theme had."""
    for selector in (
        "QMenuBar",
        "QMenu",
        "QTextEdit",
        "QTabWidget::pane",
        "QTabBar::tab:selected",
        "QScrollBar:horizontal",
        "#MusicPage",
        "#divider",
    ):
        assert selector in STYLESHEET, f"{selector} has no rule"


def test_focus_gets_a_visible_ring():
    """Neither old sheet had a :focus rule, and grey glass swallows one."""
    assert "QPushButton:focus" in STYLESHEET


def test_compact_renders_smaller_from_the_same_tokens():
    comfortable = stylesheet("comfortable")
    compact = stylesheet("compact")
    assert "font-size: 13px" in comfortable
    assert "font-size: 12px" in compact
    assert comfortable != compact


def test_comfortable_keeps_the_measurements_the_app_shipped_with():
    """The glass switch is meant to be visually flat: new paint, same sizes.

    These are the numbers the pre-glass app rendered. If one of them moves,
    that belongs in its own commit with its own reason, not in a restyle.
    """
    css = stylesheet("comfortable")
    assert "font-size: 13px" in _rule(css, "QWidget")
    assert "font-size: 19px" in _rule(css, "#Wordmark")
    assert "font-size: 10px" in _rule(css, 'QLabel[role="section"]')
    assert "padding: 8px 14px" in _rule(css, "QPushButton")
    assert "padding: 8px 10px" in _rule(css, "QLineEdit, QPlainTextEdit, QTextEdit, QComboBox")


def test_compact_measures_the_same_sheet_down():
    css = stylesheet("compact")
    assert "font-size: 12px" in _rule(css, "QWidget")
    assert "font-size: 17px" in _rule(css, "#Wordmark")
    assert "font-size: 9px" in _rule(css, 'QLabel[role="section"]')
    assert "padding: 5px 11px" in _rule(css, "QPushButton")
    assert "padding: 5px 8px" in _rule(css, "QLineEdit, QPlainTextEdit, QTextEdit, QComboBox")


def test_stylesheet_references_accent():
    assert C["accent"] in STYLESHEET


def test_stylesheet_is_a_single_stylesheet():
    assert STYLESHEET.lstrip().startswith("QWidget")


def test_unknown_density_is_refused():
    with pytest.raises(KeyError):
        stylesheet("roomy")
