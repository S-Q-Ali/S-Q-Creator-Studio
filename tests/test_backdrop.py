"""The backdrop is the one painted surface, and the range every panel sits on.

Qt has no blur-behind, so the depth here is arithmetic a test can check: the
gradient's lit end is exactly the panel token, the light pools never outrun
it, and the sheet no longer paints a blanket background that would hide the
whole thing. Text sits on the bare backdrop wherever a container is
transparent, which is why "no brighter than a panel" is a readability rule and
not a taste rule.
"""

from __future__ import annotations

import re

from s_q_ali_media_downloader.theme import BACKDROP, C, stylesheet
from s_q_ali_media_downloader.ui.widgets import Backdrop


def _rule_body(css: str, selector: str) -> str:
    """The body of one rule, so a test can look inside a single block."""
    block = re.search(rf"(?m)^{re.escape(selector)}\s*\{{([^}}]*)\}}", css)
    assert block, f"{selector} has no rule in the stylesheet"
    return block.group(1)


def _rgb(token: str) -> tuple[int, int, int]:
    if token.startswith("rgb("):
        return tuple(int(v) for v in token[4:-1].split(",")[:3])
    return tuple(int(token[i : i + 2], 16) for i in (1, 3, 5))


def _channel(value: int) -> float:
    v = value / 255
    return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4


def _luminance(token: str) -> float:
    r, g, b = _rgb(token)
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def _mean_lightness(image, x0: int, y0: int, x1: int, y1: int) -> float:
    total = 0
    samples = 0
    for y in range(max(y0, 0), min(y1, image.height())):
        for x in range(max(x0, 0), min(x1, image.width())):
            rgb = image.pixelColor(x, y).getRgb()[:3]
            total += sum(rgb) / 3
            samples += 1
    return total / max(samples, 1)


def test_the_lit_end_of_the_backdrop_is_the_panel_token():
    """A card and the backdrop behind it must not be the same colour...

    ...but the backdrop's brightest point is allowed to be, because that is
    the surface every text token is measured against. It is the same number
    on purpose: graphite is what white at the panel alpha resolves to over
    the void, so text on the bare backdrop at the bottom of the window has
    exactly the contrast text on a card has.
    """
    assert BACKDROP["bottom"] == C["panel"]
    assert _luminance(BACKDROP["top"]) < _luminance(BACKDROP["bottom"])


def test_no_light_pool_outruns_a_panel():
    for name in ("pool_cool", "pool_signal"):
        peak = BACKDROP[name]
        assert _luminance(peak) <= _luminance(C["panel"]), (
            f"{name} {peak} is lighter than a panel {C['panel']}, so a label "
            "sitting on the bare backdrop would be dimmer than the sheet's "
            "own contrast tests assert"
        )


def test_the_bare_widget_selector_no_longer_paints_everything(qapp):
    """The old sheet set a background on the bare ``QWidget`` selector.

    It cascaded onto every container in the app, which is both why nothing
    could be glass and why a backdrop painted behind them would never be
    seen. The window and the dialogs keep their own; the containers let it
    through.
    """
    rule = _rule_body(stylesheet("comfortable"), "QWidget")
    assert "background" not in rule
    window_rule = _rule_body(stylesheet("comfortable"), "QMainWindow, QDialog")
    assert C["bg"] in window_rule


def test_a_panel_paints_the_solid_it_resolves_to(qapp):
    """Glass here is elevation and a hairline, not see-through.

    A translucent card over a gradient is a card whose colour depends on
    where it is, and every contrast number in this app is measured against
    one fixed surface. The fills are the flattened solids.
    """
    css = stylesheet("comfortable")
    assert C["panel"] in _rule_body(css, "#Rail")
    assert "rgba" not in _rule_body(css, "#Rail")


def test_the_gradient_is_darker_at_the_top_than_at_the_bottom(qapp):
    backdrop = Backdrop()
    backdrop.resize(900, 700)
    image = backdrop.grab().toImage()

    top = _mean_lightness(image, 0, 0, 900, 70)
    bottom = _mean_lightness(image, 0, 630, 900, 700)
    assert bottom - top > 3, f"top {top:.1f} bottom {bottom:.1f}: the range is invisible"


def _mean(rgb: tuple[int, int, int]) -> float:
    return sum(rgb) / 3


def _gradient_at(share: float) -> tuple[int, int, int]:
    """The plain backdrop at ``share`` of the window's height."""
    top = _rgb(BACKDROP["top"])
    bottom = _rgb(BACKDROP["bottom"])
    return tuple(round(top[i] + (bottom[i] - top[i]) * share) for i in range(3))


def test_each_pool_sits_where_the_backdrop_is_darker_than_it():
    """A pool is a colour, not extra light, so it can only lift.

    Put one where the gradient has already reached its ceiling and it paints
    a hole instead of a glow - which is what the first version of this
    widget did, and no screenshot of the top third would have shown.
    """
    for name, spec in BACKDROP["pools"].items():
        _, cy = spec["at"]
        peak = _mean(_rgb(BACKDROP[spec["colour"]]))
        base = _mean(_gradient_at(cy))
        assert peak > base + 1.5, (
            f"{name} peaks at {peak:.1f} on a backdrop already at {base:.1f} "
            f"at {cy:.0%} height: it would darken, not glow"
        )


def test_a_pool_lifts_its_own_centre(qapp):
    backdrop = Backdrop()
    backdrop.resize(900, 700)
    image = backdrop.grab().toImage()

    for name, spec in BACKDROP["pools"].items():
        cx, cy = spec["at"]
        x, y = int(cx * 900), int(cy * 700)
        here = _mean_lightness(image, x - 12, y - 12, x + 12, y + 12)
        base = _mean(_gradient_at(cy))
        assert here > base + 1.5, f"{name} at ({cx:.2f}, {cy:.2f}) paints {here:.1f}, " f"the plain gradient is {base:.1f}"
