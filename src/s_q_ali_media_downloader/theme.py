"""Visual identity for S-Q Creator Studio.

Palette: black, white, grey and one blue. Depth is glass - a translucent
white fill over a known dark backdrop - and status is carried on a vertical
spine at the left edge of every queue card, which is the one signature
element of the interface.

Qt has no blur-behind, so glass here is honest about what it is: the fills are
alphas, and every alpha has a sibling solid token equal to what it resolves to
over the backdrop. Readability is asserted against those solids, never against
the alpha, and the surfaces that sit over an arbitrary desktop - tables,
popups, tooltips - are painted opaque.

The app has two densities. ``comfortable`` is the roomy default;
``compact`` fits the whole interface on a 1280x720 laptop without a single
control being clipped. The same rules are written once and rendered from a
token set, so the two densities cannot drift apart.
"""

from PySide6.QtWidgets import QApplication, QLayout, QWidget

# --------------------------------------------------------------------------- #
# Glass
# --------------------------------------------------------------------------- #
# Three elevations and one lit edge. Everything above 0.10 stops reading as a
# panel and starts reading as a sheet of frosted plastic.
GLASS = {
    "low": 0.04,  # recessed wells: scrollbars, tracks
    "mid": 0.07,  # the panel - cards, chips, the rail
    "high": 0.10,  # the raised layer - buttons, inputs
    "hairline": 0.14,  # the lit top edge, and the hover step above raised
}


def rgba(color: str, alpha: float) -> str:
    """A QSS ``rgba()`` from a hex colour and an alpha - what Qt paints."""
    red = int(color[1:3], 16)
    green = int(color[3:5], 16)
    blue = int(color[5:7], 16)
    return f"rgba({red}, {green}, {blue}, {alpha})"


def flatten(base: str, over: str, alpha: float) -> str:
    """The solid ``over`` at ``alpha`` resolves to once it lands on ``base``.

    This is the number a contrast ratio can be calculated against. It lives
    next to the alpha on purpose: the two describe one surface, and a token
    that only tracks one of them is a token that lies.
    """

    def mix(a: int, b: int) -> int:
        return int(a * (1 - alpha) + b * alpha + 0.5)

    channels = [
        f"{mix(int(base[i : i + 2], 16), int(over[i : i + 2], 16)):02X}"
        for i in (1, 3, 5)
    ]
    return "#" + "".join(channels)


_VOID = "#06080C"  # the backdrop base, and the reference every alpha flattens onto
_LIGHT = "#FFFFFF"
_CHALK = "#EDF1F5"

C = {
    "bg": _VOID,
    # Both are derived, so a panel's declared colour can never drift away from
    # the glass it is drawn with.
    "panel": flatten(_VOID, _LIGHT, GLASS["mid"]),
    "raised": flatten(_VOID, _LIGHT, GLASS["high"]),
    "raised_hi": flatten(_VOID, _LIGHT, GLASS["hairline"]),
    "border": "#22262C",
    "text": _CHALK,
    "muted": "#7C8794",
    "faint": "#A6B0BC",
    "accent": "#2F81F7",
    "accent_mid": "#6FB2F9",
    "accent_hi": "#8FC1FF",
    # The action fill. Chalk text never reaches 4.5:1 on the accent itself
    # (3.76 is the ceiling), so the primary button sits on this darker blue.
    # It is a fill only: at 3.28:1 it is too dim to be written on as text.
    "accent_deep": "#3A6BB0",
    # The four hue slots the old palette spent on amber, teal, pink and purple
    # are now grey and blue. The names stay because the call sites do.
    "amber": "#8FC1FF",
    "done": "#C6CFD8",
    "failed": _CHALK,
    "queued": "#7C8794",
    "waiting": "#6FB2F9",
    # The two social buttons keep their networks' colours, because a button
    # that says GitHub in an invented hue is a button nobody recognises. Both
    # already sit inside the brief: one is a near-black, one is a blue.
    "github": "#24292F",
    "linkedin": "#0A66C2",
}

# The state language, once red, amber and violet are gone: grey is not moving,
# blue is moving, chalk is finished. Luminance ranks the blues by urgency and
# the label carries the word, so no state depends on colour alone. Failed also
# inverts its chip - the one place the app flips text and fill.
STATUS_COLORS = {
    "Queued": C["queued"],
    "Downloading": C["accent"],
    "Retrying": C["amber"],
    "Waiting": C["waiting"],
    "Paused": C["faint"],
    "Completed": C["done"],
    "Failed": C["failed"],
}

# Weight is the second channel the palette no longer has: 600 is standing
# still, 700 is doing something, 800 needs a decision from you.
STATUS_WEIGHTS = {
    "Queued": 600,
    "Paused": 600,
    "Downloading": 700,
    "Waiting": 700,
    "Retrying": 700,
    "Completed": 700,
    "Failed": 800,
}

# Every foreground/background pair the sheet actually paints with text. A
# surface nobody writes on is not worth asserting, and a pair missing here is
# a pair nothing checks.
TEXT_SURFACES = {
    "body on the void": ("text", "bg"),
    "body on a panel": ("text", "panel"),
    "secondary on the void": ("muted", "bg"),
    "secondary on a panel": ("muted", "panel"),
    "hint on a panel": ("faint", "panel"),
    "badge on a control": ("faint", "raised"),
    "signal on a panel": ("accent", "panel"),
    "label on the action fill": ("text", "accent_deep"),
    "label on the GitHub fill": ("text", "github"),
    "label on the LinkedIn fill": ("text", "linkedin"),
}

# --------------------------------------------------------------------------- #
# Backdrop
# --------------------------------------------------------------------------- #
# The one painted surface, and the range every panel sits on. Its lit end is
# the panel token on purpose: the containers are transparent down to it, so a
# label on the bare backdrop at the bottom of the window has exactly the
# contrast the same label has on a card. The pools are places where that range
# reaches its ceiling early, not extra light - none of them may be brighter
# than a panel, or every number in TEXT_SURFACES would be a lie about the
# bottom half of the window.
BACKDROP = {
    "top": _VOID,
    "bottom": C["panel"],
    "pool_cool": flatten(_VOID, _LIGHT, 0.055),
    "pool_signal": flatten(_VOID, C["accent"], 0.12),
    # Position as a fraction of the window, radius as a fraction of its
    # height. The rail and the cards are opaque, so the backdrop only reads
    # where a container lets it through: the header band, the margins, and
    # the empty area under a short queue.
    #
    # A pool is a colour, not extra light: it can only lift the surface it
    # sits on, so it belongs where the gradient is still darker than its own
    # peak. Both pools are in the top third because the gradient's ceiling is
    # at the bottom - a pool down there would be a hole in the backdrop.
    "pools": {
        "cool": {"at": (0.72, 0.12), "radius": 0.50, "colour": "pool_cool"},
        "signal": {"at": (0.40, 0.30), "radius": 0.42, "colour": "pool_signal"},
    },
}

# --------------------------------------------------------------------------- #
# Type
# --------------------------------------------------------------------------- #
# Qt has no alias for "the system face", so the stack names one per platform,
# in the order the app ships to them: Windows, then macOS, then Linux. Qt asks
# them in turn and takes the first the machine has, so a box missing its own
# face still lands on something its neighbours would recognise. The sheet and
# the drawn wordmark read this one list - a logotype set in a different family
# from the interface is two brands, not one. No font file is bundled.
UI_FAMILIES = (
    "Segoe UI Variable Display",
    "Segoe UI",  # Windows
    ".AppleSystemUIFont",
    "Helvetica Neue",  # macOS
    "Noto Sans",
    "Cantarell",
    "Ubuntu",
    "Inter",  # Linux
)

# --------------------------------------------------------------------------- #
# Density
# --------------------------------------------------------------------------- #
# ``scale`` shrinks the spacing inside the layouts. ``rail`` is the width of
# the left panel. ``control`` is the height every button and input keeps, so
# a pointer can find it. The rest are the sizes the stylesheet renders.
DENSITY = {
    "comfortable": {
        "scale": 1.0,
        "rail": 280,
        "control": 34,
        "body": 13,
        "title": 19,
        "caption": 10,
        "pad_y": 8,
        "pad_x": 14,
        "field_pad_y": 8,
        "field_pad_x": 10,
        "gap": 10,
    },
    "compact": {
        "scale": 0.72,
        "rail": 248,
        "control": 30,
        "body": 12,
        "title": 17,
        "caption": 9,
        "pad_y": 5,
        "pad_x": 11,
        "field_pad_y": 5,
        "field_pad_x": 8,
        "gap": 7,
    },
}


def stylesheet(density: str = "comfortable") -> str:
    """The whole app stylesheet, rendered from a density's tokens.

    One sheet for the whole app: it carries every selector the interface
    paints, from both of the sheets that came before it.
    """
    t = DENSITY[density]
    body = t["body"]
    caption = t["caption"]
    mono = "'Consolas', 'Cascadia Mono', 'DejaVu Sans Mono', monospace"
    ui = ", ".join(f"'{family}'" for family in UI_FAMILIES) + ", sans-serif"
    well = rgba(_LIGHT, GLASS["low"])
    # The fills are the flattened solids, not the alphas. A translucent card
    # over a gradient is a card whose colour depends on where it happens to
    # sit, and every number in TEXT_SURFACES is measured against one fixed
    # surface. The glass is the elevation and the hairline, not the
    # see-through.
    panel = C["panel"]
    raised = C["raised"]
    edge = rgba(_LIGHT, GLASS["hairline"])
    return f"""
QWidget {{
    color: {C['text']};
    font-family: {ui};
    font-size: {body}px;
}}
QMainWindow, QDialog {{ background: {C['bg']}; }}
QLabel {{ background: transparent; }}

/* ---------- left control rail ---------- */
#Rail {{
    background: {panel};
    border-right: 1px solid {C['border']};
}}
/* #Wordmark paints itself: widgets.wordmark_pixmap draws the name into a
   pixmap at the density's title size, so no rule styles its font. */
#WordmarkSub {{
    font-size: {caption}px;
    color: {C['accent_hi']};
    font-weight: 600;
    background: transparent;
}}
#RailStripe {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {C['accent']}, stop:0.5 {C['accent_hi']}, stop:1 {C['done']});
    border: none;
    border-radius: 2px;
}}
#divider {{ background: {C['border']}; }}
QLabel[role="section"] {{
    color: {C['faint']};
    font-size: {caption}px;
    font-weight: 700;
    background: transparent;
}}
QLabel[role="hint"] {{
    color: {C['faint']};
    font-size: {caption}px;
    background: transparent;
}}
QLabel[role="fieldLabel"] {{
    color: {C['faint']};
    background: transparent;
}}
QLabel[role="hintStrong"] {{
    color: {C['faint']};
    font-size: {caption}px;
    font-weight: 700;
    background: transparent;
}}
QLabel[role="pageTitle"] {{
    font-size: 14px;
    font-weight: 800;
    color: {C['accent_hi']};
    background: transparent;
}}
#AgentHeader {{
    background: {panel};
    border: 1px solid {C['border']};
    border-top: 1px solid {edge};
    border-radius: 12px;
}}

/* ---------- menus ---------- */
QMenuBar {{
    background: {C['bg']};
    color: {C['text']};
    border-bottom: 1px solid {C['border']};
}}
QMenuBar::item {{ background: transparent; padding: 6px 12px; color: {C['text']}; }}
QMenuBar::item:selected {{ background: {C['raised_hi']}; color: {C['text']}; }}
QMenu {{
    background: {C['raised_hi']};
    border: 1px solid {C['border']};
    padding: 6px;
}}
QMenu::item {{ padding: 7px 24px 7px 12px; border-radius: 6px; color: {C['text']}; }}
QMenu::item:selected {{ background: {C['accent_deep']}; color: {C['text']}; }}
QMenu::separator {{ height: 1px; background: {C['border']}; margin: 6px 8px; }}

/* ---------- inputs ---------- */
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox {{
    background: {raised};
    border: 1px solid {C['border']};
    border-radius: 8px;
    padding: {t['field_pad_y']}px {t['field_pad_x']}px;
    selection-background-color: {C['accent_deep']};
    selection-color: {C['text']};
}}
QPlainTextEdit, QTextEdit {{
    font-family: {mono};
    font-size: {body - 1}px;
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus {{
    border: 1px solid {C['accent_hi']};
}}
QLineEdit:disabled, QPlainTextEdit:disabled, QTextEdit:disabled, QComboBox:disabled {{
    color: {C['muted']};
    border-color: {C['border']};
    background: {well};
}}
/* The down indicator is left to the platform style. Styling either
   ::drop-down or ::down-arrow switches Qt's own arrow off, and Qt has no
   CSS border triangle: transparent sides paint as a filled sliver. */
QComboBox QAbstractItemView {{
    background: {C['raised_hi']};
    border: 1px solid {C['border']};
    selection-background-color: {C['accent_deep']};
    selection-color: {C['text']};
    color: {C['text']};
    outline: none;
    padding: 4px;
}}

/* ---------- buttons ---------- */
QPushButton {{
    background: {raised};
    border: 1px solid {C['border']};
    border-top: 1px solid {edge};
    border-radius: 8px;
    padding: {t['pad_y']}px {t['pad_x']}px;
    color: {C['text']};
    font-weight: 600;
}}
QPushButton:hover  {{ background: {C['raised_hi']}; border-color: {C['faint']}; }}
QPushButton:pressed {{ background: {C['accent_deep']}; }}
QPushButton:disabled {{ color: {C['muted']}; border-color: {C['border']}; background: {well}; }}
QPushButton:focus {{
    border: 1px solid {C['accent_hi']};
    background: {C['raised_hi']};
}}

QPushButton[kind="primary"] {{
    background: {C['accent_deep']};
    border: 1px solid {C['accent_deep']};
    border-top: 1px solid {C['accent']};
    color: {C['text']};
    font-weight: 700;
}}
QPushButton[kind="primary"]:hover {{
    background: {C['accent']};
    border-color: {C['accent_hi']};
    color: {C['bg']};
}}
QPushButton[kind="primary"]:pressed {{ background: {C['accent_deep']}; }}
QPushButton[kind="primary"]:disabled {{ background: {well}; border-color: {C['border']}; color: {C['muted']}; }}
/* Each kind repeats the ring because ``QPushButton[kind="primary"]`` and
   ``QPushButton:focus`` tie on specificity: the later, calmer rule wins and
   the focused button looks untouched. Hover is told apart by its fill. */
QPushButton[kind="primary"]:focus {{ border-color: {C['accent_hi']}; }}

QPushButton[kind="danger"] {{ color: {C['failed']}; border-color: {C['border']}; }}
QPushButton[kind="danger"]:hover {{ border-color: {C['accent_hi']}; background: {C['raised_hi']}; }}
QPushButton[kind="danger"]:focus {{ border-color: {C['accent_hi']}; }}

QPushButton[kind="ghost"] {{
    background: transparent;
    border: 1px solid transparent;
    color: {C['muted']};
    font-weight: 500;
    padding: {max(4, t['pad_y'] - 2)}px {max(8, t['pad_x'] - 4)}px;
}}
QPushButton[kind="ghost"]:hover {{ color: {C['text']}; border-color: {C['border']}; }}
QPushButton[kind="ghost"]:focus {{ border-color: {C['accent_hi']}; }}

/* ---------- source tabs ---------- */
QPushButton[kind="tab"] {{
    background: {raised};
    border: 1px solid {C['border']};
    border-radius: 8px;
    padding: {max(5, t['pad_y'] - 1)}px {t['pad_x']}px;
    color: {C['muted']};
    font-size: {body - 1}px;
    font-weight: 600;
    /* Emoji glyphs fall back to a wider font than QFontMetrics measures, so
       the text needs padding or the last letter is clipped. Keep it small:
       the two source tabs share a 285px rail. */
}}
QPushButton[kind="tab"]:hover {{
    color: {C['text']};
    border-color: {C['faint']};
}}
QPushButton[kind="tab"]:checked {{
    background: {C['accent_deep']};
    border: 1px solid {C['accent']};
    color: {C['text']};
    /* No weight change here: sizeHint() is measured with the calm font, so
       bolding only the active tab paints wider text into a narrower box and
       the label loses its last letter. The fill, border and text already say
       which tab is active. */
}}
QPushButton[kind="tab"]:focus {{ border-color: {C['accent_hi']}; }}

/* ---------- workspace ---------- */
#WorkHeader, #NavBar {{
    background: transparent;
    border-bottom: 1px solid {C['border']};
}}
#Chip {{
    background: {panel};
    border: 1px solid {C['border']};
    border-top: 1px solid {edge};
    border-radius: 9px;
}}
#Chip:hover {{ border-color: {C['accent_hi']}; }}
QLabel[role="chipValue"] {{
    font-size: {t['title'] - 2}px;
    font-weight: 700;
    color: {C['accent_hi']};
    background: transparent;
}}
QLabel[role="chipLabel"] {{
    font-size: {caption}px;
    color: {C['muted']};
    font-weight: 700;
    background: transparent;
}}

#Card {{
    background: {panel};
    border: 1px solid {C['border']};
    border-top: 1px solid {edge};
    border-radius: 10px;
}}
#Card:hover {{ border-color: {C['faint']}; }}
#Spine {{ border-radius: 2px; }}
QLabel[role="cardTitle"] {{
    font-size: {body}px;
    font-weight: 600;
    color: {C['text']};
    background: transparent;
}}
QLabel[role="cardUrl"] {{
    font-family: {mono};
    font-size: {body - 2}px;
    color: {C['faint']};
    background: transparent;
}}
QLabel[role="meta"] {{
    font-family: {mono};
    font-size: {body - 2}px;
    color: {C['muted']};
    background: transparent;
}}
QLabel[role="error"] {{
    font-size: {body - 2}px;
    color: {C['failed']};
    font-weight: 700;
    background: transparent;
}}
QLabel[role="badge"] {{
    background: {C['raised']};
    border: 1px solid {C['border']};
    border-radius: 5px;
    padding: 2px 7px;
    font-size: {caption}px;
    font-weight: 700;
    color: {C['faint']};
}}
QLabel[role="status"] {{
    font-size: {caption}px;
    font-weight: 700;
    background: transparent;
}}
#EmptyState {{
    color: {C['faint']};
    font-size: {body}px;
    background: transparent;
}}

QProgressBar {{
    background: {well};
    border: none;
    border-radius: 3px;
    height: 6px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    border-radius: 3px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {C['accent_deep']}, stop:1 {C['accent']});
}}

QCheckBox {{
    spacing: 8px; color: {C['text']}; background: transparent;
    /* The box itself is small, so the row around it is given the height a
       pointer needs to hit it. */
    min-height: 24px;
}}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {C['border']};
    border-radius: 4px;
    background: {raised};
}}
QCheckBox::indicator:hover {{ border-color: {C['accent_hi']}; }}
QCheckBox::indicator:checked {{
    background: {C['accent']};
    /* The calm edge is the fill, not the ring colour: a checked box that
       already wears accent_hi shows no change at all when focus asks for
       accent_hi, and a keyboard user tabbing past it loses the cursor. */
    border-color: {C['accent']};
}}
/* The state goes after the sub-control: QCheckBox:focus::indicator parses,
   and paints nothing. It also has to sit below :checked, which ties on
   specificity and would otherwise keep a focused box looking untouched. */
QCheckBox::indicator:focus {{ border-color: {C['accent_hi']}; }}

/* The queue's empty area is the one place the backdrop is guaranteed to  */
/* read, so the scroll area and its host let it through.                   */
QScrollArea {{ border: none; background: transparent; }}
#QueueHost {{ background: transparent; }}
QScrollBar:vertical {{
    background: transparent; width: 10px; margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {C['raised_hi']}; border-radius: 5px; min-height: 40px;
}}
QScrollBar::handle:vertical:hover {{ background: {C['faint']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{
    background: transparent; height: 10px; margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {C['raised_hi']}; border-radius: 5px; min-width: 40px;
}}
QScrollBar::handle:horizontal:hover {{ background: {C['faint']}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: transparent; }}

#StatusBar {{
    background: {panel};
    border-top: 1px solid {edge};
}}
QLabel[role="statusText"] {{
    color: {C['muted']};
    font-size: {body - 2}px;
    background: transparent;
}}

/* ---------- usage notice ---------- */
QLabel[role="notice"] {{
    color: {C['amber']};
    font-size: {body - 2}px;
    font-weight: 600;
    background: transparent;
}}
#ShieldBadge {{ background: transparent; }}

/* ---------- tooltips ---------- */
QToolTip {{
    background: {C['raised_hi']};
    color: {C['text']};
    border: 1px solid {C['accent_hi']};
    padding: 5px 8px;
}}

/* ---------- settings, music, vertical studio ---------- */
#SettingsPage, #SettingsHost, #MusicPage, #VerticalStudioPage {{ background: transparent; }}

/* The drop target is a well with a dashed edge: it holds nothing yet, and
   the dashes are what say "put something here". */
#DropZone {{
    background: {well};
    border: 1px dashed {C['border']};
    border-radius: 10px;
}}
QListWidget {{
    background: {C['panel']};
    color: {C['text']};
    border: 1px solid {C['border']};
    border-radius: 10px;
    outline: 0;
}}
QListWidget::item {{ padding: 6px 8px; }}
QListWidget::item:selected {{
    background: {C['accent_deep']};
    color: {C['text']};
}}

/* ---------- tables ---------- */
QTableWidget {{
    background: {C['panel']};
    alternate-background-color: {C['raised']};
    color: {C['text']};
    gridline-color: {C['border']};
    selection-background-color: {C['accent_deep']};
    selection-color: {C['text']};
    border: 1px solid {C['border']};
    border-radius: 10px;
}}
QTableWidget::item {{ padding: 6px 8px; }}
QHeaderView::section {{
    background: {C['raised']};
    color: {C['accent_hi']};
    border: none;
    border-bottom: 1px solid {C['border']};
    padding: 8px;
    font-weight: 700;
}}

/* ---------- tabs (used by embedded pages) ---------- */
QTabWidget::pane {{
    background: {C['bg']};
    border: 1px solid {C['border']};
    border-radius: 10px;
}}
QTabBar::tab {{
    background: {C['panel']};
    color: {C['muted']};
    padding: {t['pad_y']}px 16px;
    margin-right: 4px;
    border: 1px solid {C['border']};
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
}}
QTabBar::tab:hover {{ color: {C['text']}; border-color: {C['faint']}; }}
QTabBar::tab:selected {{
    background: {C['accent_deep']};
    color: {C['text']};
    border-color: {C['accent']};
}}
QTabBar::tab:focus {{ border-color: {C['accent_hi']}; }}
"""


# Kept for the callers that expect a stylesheet, not a function.
STYLESHEET = stylesheet("comfortable")


def _remember_base(widget: QWidget, name: str, value) -> None:
    """Store a widget's original value the first time it is seen.

    The density is applied more than once - the window is re-laid out when
    the user changes the setting - and each application has to start from
    the original, not from the last scaled value.
    """
    if widget.property(name) is None:
        widget.setProperty(name, value)


def _rescale_layouts(widget: QWidget, scale: float) -> None:
    for layout in widget.findChildren(QLayout):
        margins = layout.contentsMargins()
        _remember_base(layout, "densityMargins", (margins.left(), margins.top(), margins.right(), margins.bottom()))
        left, top, right, bottom = layout.property("densityMargins")
        layout.setContentsMargins(
            int(left * scale), int(top * scale), int(right * scale), int(bottom * scale)
        )
        _remember_base(layout, "densitySpacing", layout.spacing())
        layout.setSpacing(max(0, int(layout.property("densitySpacing") * scale)))


def _rescale_controls(widget: QWidget, scale: float, control_height: int) -> None:
    """Keep every control big enough to click, and shrink the rest."""
    for child in widget.findChildren(QWidget):
        base = child.minimumHeight()
        if base > 0:
            _remember_base(child, "densityMinHeight", base)
            original = child.property("densityMinHeight")
            child.setMinimumHeight(max(control_height - 4, int(original * scale)))


def apply_density(window: QWidget, compact: bool) -> None:
    """Render the app at the given density and re-lay it out.

    ``compact`` fits the interface on a small laptop. The choice is the
    user's: the Settings page offers "follow the window" and two fixed
    choices.
    """
    name = "compact" if compact else "comfortable"
    tokens = DENSITY[name]

    app = QApplication.instance()
    if app is not None:
        app.setStyleSheet(stylesheet(name))

    _rescale_layouts(window, tokens["scale"])
    _rescale_controls(window, tokens["scale"], tokens["control"])

    rail = window.findChild(QWidget, "Rail")
    if rail is not None:
        _remember_base(rail, "densityRailWidth", tokens["rail"])
        # The token is the floor, not the cap: how wide a label needs is the
        # platform font's business, and a Linux face asks for more than the
        # Windows one the token was tuned on. Capping at the token clipped
        # "Account based" and "Add to queue" on Linux.
        rail.setFixedWidth(max(tokens["rail"], rail.layout().minimumSize().width()))

    window.updateGeometry()
    if window.layout() is not None:
        window.layout().activate()
