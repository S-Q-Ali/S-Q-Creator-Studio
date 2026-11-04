"""The glass token set and the stylesheet it renders into.

The palette is black, white, grey and one blue. Glass is specified in alphas,
but readability has to be judged on the solid colour each alpha actually
flattens to, so both numbers live in ``theme.py`` and this file proves they
agree.
"""

import re
from pathlib import Path

import pytest

from s_q_ali_media_downloader.theme import (
    DENSITY,
    GLASS,
    STATUS_COLORS,
    STYLESHEET,
    TEXT_SURFACES,
    UI_FAMILIES,
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


def test_no_colour_literal_outside_the_token_table():
    """A hex in a page is a hue no contrast test can see.

    The palette is one file: everything else asks ``theme.py`` for a colour,
    so the brief's four hues and their measured contrasts stay checkable.
    """
    package = Path(__file__).resolve().parents[1] / "src" / "s_q_ali_media_downloader"
    quoted_hex = re.compile(r"[\"']#[0-9A-Fa-f]{3,6}[\"']")
    offenders = [
        f"{path.name}:{number}: {line.strip()}"
        for path in sorted(package.rglob("*.py"))
        if path.name != "theme.py"
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if quoted_hex.search(line)
    ]
    assert not offenders, "colour literals outside theme.py:\n" + "\n".join(offenders)


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


def test_glass_is_three_elevations_and_one_edge():
    assert GLASS["low"] < GLASS["mid"] < GLASS["high"]
    assert GLASS["high"] <= 0.10, "above this a panel stops reading as glass"
    assert GLASS["hairline"] > GLASS["high"], "the lit top edge must beat the fill"


def test_every_glass_alpha_is_painted():
    """An elevation nothing draws with is a number no test can defend.

    ``glow`` was one: it described a focus halo Qt cannot paint, survived
    three refactors unnoticed, and went out the day the ring turned out to
    be a colour rather than a shadow.
    """
    source = Path(__file__).resolve().parents[1] / "src" / "s_q_ali_media_downloader" / "theme.py"
    after_the_table = source.read_text(encoding="utf-8").split("GLASS = {", 1)[1]
    unused = [key for key in GLASS if f'GLASS["{key}"]' not in after_the_table]
    assert not unused, f"nothing is drawn with: {unused}"


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


def test_the_sheet_paints_the_flattened_solid_not_the_alpha():
    """Glass is the elevation and the hairline, not the see-through.

    The alphas in GLASS still derive the tokens, but a painted panel is the
    solid its alpha resolves to over the backdrop. The backdrop is a
    gradient, so a translucent card would be a different colour at the top of
    the window than at the bottom, and no contrast number in this file would
    describe the surface the text is actually on.
    """
    for selector in ("#Rail", "#Card", "#Chip", "#StatusBar", "QPushButton"):
        body = _rule(STYLESHEET, selector)
        assert C["panel"] in body or C["raised"] in body, f"{selector} lost its solid fill"
        assert rgba("#FFFFFF", GLASS["mid"]) not in body
        assert rgba("#FFFFFF", GLASS["high"]) not in body


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
    assert DENSITY["comfortable"]["title"] == 19
    assert "font-size: 10px" in _rule(css, 'QLabel[role="section"]')
    assert "padding: 8px 14px" in _rule(css, "QPushButton")
    assert "padding: 8px 10px" in _rule(css, "QLineEdit, QPlainTextEdit, QTextEdit, QComboBox")


def test_compact_measures_the_same_sheet_down():
    css = stylesheet("compact")
    assert "font-size: 12px" in _rule(css, "QWidget")
    assert DENSITY["compact"]["title"] == 17
    assert "font-size: 9px" in _rule(css, 'QLabel[role="section"]')
    assert "padding: 5px 11px" in _rule(css, "QPushButton")
    assert "padding: 5px 8px" in _rule(css, "QLineEdit, QPlainTextEdit, QTextEdit, QComboBox")


@pytest.mark.parametrize("density", ("comfortable", "compact"))
def test_the_wordmark_is_drawn_not_styled(density):
    """The rail's name is painted into a pixmap, so the sheet has no hand in it.

    A ``#Wordmark`` rule here would be a second copy of the title size - one
    the painter never reads, and one that silently disagrees with the first.
    """
    assert not any(sel == "#Wordmark" for sel, _, _ in _rules(stylesheet(density)))


# The faces each platform ships its interface in, in the order the stack asks
# for them. Qt has no alias for "the system face", so the list is the only way
# to name one.
OS_UI_FACES = {
    "windows": ("Segoe UI Variable Display", "Segoe UI"),
    "macos": (".AppleSystemUIFont", "Helvetica Neue"),
    "linux": ("Noto Sans", "Cantarell", "Ubuntu", "Inter"),
}


def test_the_font_stack_names_each_platforms_own_face():
    """Windows first, then macOS, then Linux, each as a block."""
    expected = [family for faces in OS_UI_FACES.values() for family in faces]
    assert list(UI_FAMILIES) == expected


def test_the_sheet_ends_the_font_stack_with_a_generic():
    """A machine holding none of the named faces still renders readable text."""
    stack = _rule(STYLESHEET, "QWidget").split("font-family:")[1].split(";")[0]
    assert stack.strip().endswith("sans-serif")


PSEUDO_STATES = (":checked", ":hover", ":pressed", ":focus", ":selected", ":disabled")


@pytest.mark.parametrize("density", ("comfortable", "compact"))
def test_no_pseudo_state_rule_repaints_the_font(density):
    """Type size and weight belong where sizeHint() can see them.

    Qt measures a button with its base font, then paints it with whatever the
    state rule asks for. A tab that bolds only while it is active writes
    wider text into a box sized for the calm one and loses its last letter -
    while every layout test stays green, because they measure the calm font
    too. The active tab already has a fill, a border and chalk text.
    """
    css = stylesheet(density)
    offenders = [
        " ".join(selector.split())
        for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css)
        if any(state in selector for state in PSEUDO_STATES)
        and re.search(r"font-(weight|size)", body)
    ]
    assert not offenders, f"sized with the calm font, painted with the state's: {offenders}"


# Every control a keyboard can reach, named by the rule that has to say it is
# focused. A kind-qualified button needs its *own* focus rule: Qt resolves
# ``QPushButton[kind="tab"]`` and ``QPushButton:focus`` at the same
# specificity, so the later one - the tab's calm state - wins and the ring
# never paints.
FOCUS_RING = {
    "the plain button": "QPushButton:focus",
    "the primary button": 'QPushButton[kind="primary"]:focus',
    "the danger button": 'QPushButton[kind="danger"]:focus',
    "the ghost button": 'QPushButton[kind="ghost"]:focus',
    "the workspace tab": 'QPushButton[kind="tab"]:focus',
    "the link field": "QLineEdit:focus",
    "the log": "QPlainTextEdit:focus",
    "the rich text": "QTextEdit:focus",
    "the dropdown": "QComboBox:focus",
    "the checkbox": "QCheckBox::indicator:focus",
    "the embedded tab": "QTabBar::tab:focus",
}


def _rules(css: str) -> list[tuple[str, str, int]]:
    """``(selector, body, offset)`` for every selector in the sheet.

    Comments go first: Qt ignores them, and a comment that names a selector is
    not a rule that paints one.
    """
    sheet = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    found = []
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", sheet):
        for selector in match.group(1).split(","):
            found.append((selector.strip(), match.group(2), match.start()))
    return found


def _head(selector: str) -> str:
    """The selector without its pseudo-state - what two rules compete over.

    ``::indicator`` stays: it is a sub-control, not a state, and a rule for
    the box and a rule for its label are not rivals.
    """
    return re.sub(r"(?<!:):[a-z-]+", "", selector)


def _focus_rules(css: str) -> dict[str, str]:
    """Every selector in the sheet that fires on focus, mapped to its body."""
    return {selector: body for selector, body, _ in _rules(css) if ":focus" in selector}


def test_every_focusable_control_has_a_focus_rule():
    missing = [name for name, sel in FOCUS_RING.items() if sel not in _focus_rules(STYLESHEET)]
    assert not missing, "no ring for: " + ", ".join(
        f"{name} ({FOCUS_RING[name]})" for name in missing
    )


def test_the_ring_is_declared_after_the_states_it_competes_with():
    """Qt gives a tie to the rule that comes last, not the one that fits.

    ``QCheckBox::indicator:checked`` and ``QCheckBox::indicator:focus`` are the
    same specificity. With the ring declared above it, a checked box that the
    keyboard lands on paints exactly what it painted a moment ago, and every
    line of the stylesheet still looks correct.
    """
    rules = _rules(STYLESHEET)
    offenders = []
    for name, focus in FOCUS_RING.items():
        ring_at = min(offset for selector, _, offset in rules if selector == focus)
        for selector, body, offset in rules:
            if ":focus" in selector or ":disabled" in selector:
                continue  # a disabled control can never hold focus
            if _head(selector) == _head(focus) and "border" in body and offset > ring_at:
                offenders.append(f"{name}: {selector} outlives its own ring")
    assert not offenders, "\n".join(offenders)


def test_a_focus_rule_paints_the_ring_colour():
    wrong = {
        selector: body
        for selector, body in _focus_rules(STYLESHEET).items()
        if C["accent_hi"] not in body
    }
    assert not wrong, f"focus rules with no ring colour: {sorted(wrong)}"


def test_a_focus_rule_changes_colour_never_geometry():
    """The ring is a border colour, not a wider border.

    Same trap as the bolded tab: a 2px ring on focus pushes the content one
    pixel in on every side, and a control that grows on focus moves the row
    around it. Qt gives no box-shadow, so the colour is the whole ring.
    """
    offenders = {}
    for selector, body in _focus_rules(STYLESHEET).items():
        if re.search(r"padding|margin|font-(size|weight)|min-|max-|width", body):
            offenders[selector] = body
        for border in re.findall(r"border(?:-(?:top|bottom|left|right))?\s*:\s*([^;]+)", body):
            if re.search(r"\b([2-9]|[1-9]\d)px", border):
                offenders.setdefault(selector, body)
    assert not offenders, f"focus shifts geometry: {sorted(offenders)}"


@pytest.mark.parametrize("surface", ("panel", "raised", "raised_hi", "bg"))
def test_the_ring_is_visible_on_the_surface_around_it(surface):
    """WCAG 1.4.11: 3:1 for an indicator, not the 4.5:1 for text.

    The ring is judged against what the control sits on - the panel or the
    backdrop. The fill inside it is the control, not its background.
    """
    assert contrast(C["accent_hi"], C[surface]) >= 3.0


def test_stylesheet_references_accent():
    assert C["accent"] in STYLESHEET


def test_stylesheet_is_a_single_stylesheet():
    assert STYLESHEET.lstrip().startswith("QWidget")


def test_unknown_density_is_refused():
    with pytest.raises(KeyError):
        stylesheet("roomy")
