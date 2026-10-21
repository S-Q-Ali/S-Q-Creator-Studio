"""Visual identity for S-Q Creator Studio.

Palette: ink-plum base with a cool cyan accent. Status colours are
carried on a vertical spine at the left edge of every queue card, which
is the one signature element of the interface.

The app has two densities. ``comfortable`` is the roomy default;
``compact`` fits the whole interface on a 1280x720 laptop without a single
control being clipped. The same rules are written once and rendered from a
token set, so the two densities cannot drift apart.
"""

from PySide6.QtWidgets import QApplication, QLayout, QWidget

C = {
    "bg": "#100E14",
    "panel": "#1A1722",
    "raised": "#241F30",
    "raised_hi": "#2E2840",
    "border": "#332C42",
    "text": "#EFEAF5",
    "muted": "#9C93AE",
    "faint": "#A79EB8",
    "accent": "#22D3EE",
    "accent_hi": "#67E8F9",
    "amber": "#FFB020",
    "done": "#2DD4BF",
    "failed": "#F2547D",
    "queued": "#9C93AE",
    "waiting": "#A78BFA",
}

STATUS_COLORS = {
    "Queued": "#9C93AE",
    "Downloading": "#22D3EE",
    "Retrying": "#FFB020",
    "Waiting": "#A78BFA",
    "Paused": "#FFB020",
    "Completed": "#2DD4BF",
    "Failed": "#F2547D",
    "Skipped": "#8B83A0",
}

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

CURRENT_DENSITY = "comfortable"


def stylesheet(density: str = "comfortable") -> str:
    """The whole app stylesheet, rendered from a density's tokens."""
    t = DENSITY[density]
    body = t["body"]
    caption = t["caption"]
    return f"""
QWidget {{
    background: {C['bg']};
    color: {C['text']};
    font-family: 'Segoe UI Variable Display', 'Segoe UI', 'Inter', sans-serif;
    font-size: {body}px;
}}

/* ---------- left control rail ---------- */
#Rail {{
    background: {C['panel']};
    border-right: 1px solid {C['border']};
}}
#Wordmark {{
    font-size: {t['title']}px;
    font-weight: 700;
    letter-spacing: 3px;
    color: {C['text']};
    background: transparent;
}}
#WordmarkSub {{
    font-size: {caption}px;
    letter-spacing: 4px;
    color: {C['accent']};
    font-weight: 600;
    background: transparent;
}}
#RailStripe {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {C['accent']}, stop:0.5 {C['accent_hi']}, stop:1 {C['done']});
    border: none;
    border-radius: 2px;
}}
QLabel[role="section"] {{
    color: {C['faint']};
    font-size: {caption}px;
    font-weight: 700;
    letter-spacing: 2px;
    background: transparent;
}}
QLabel[role="hint"] {{
    color: {C['faint']};
    font-size: {caption}px;
    background: transparent;
}}
QLabel {{ background: transparent; }}

/* ---------- inputs ---------- */
QLineEdit, QPlainTextEdit, QComboBox {{
    background: {C['raised']};
    border: 1px solid {C['border']};
    border-radius: 8px;
    padding: {t['field_pad_y']}px {t['field_pad_x']}px;
    selection-background-color: {C['accent']};
    selection-color: #14100E;
}}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{
    border: 1px solid {C['accent']};
}}
QPlainTextEdit {{
    font-family: 'Consolas', 'Cascadia Mono', monospace;
    font-size: {body - 1}px;
}}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {C['muted']};
    margin-right: 10px;
}}
QComboBox QAbstractItemView {{
    background: {C['raised']};
    border: 1px solid {C['border']};
    selection-background-color: {C['accent']};
    selection-color: #14100E;
    outline: none;
    padding: 4px;
}}

/* ---------- buttons ---------- */
QPushButton {{
    background: {C['raised']};
    border: 1px solid {C['border']};
    border-radius: 8px;
    padding: {t['pad_y']}px {t['pad_x']}px;
    color: {C['text']};
    font-weight: 600;
}}
QPushButton:hover  {{ background: {C['raised_hi']}; border-color: {C['faint']}; }}
QPushButton:pressed {{ background: {C['panel']}; }}
QPushButton:disabled {{ color: {C['muted']}; border-color: {C['border']}; background: {C['panel']}; }}

QPushButton[kind="primary"] {{
    background: {C['accent']};
    border: 1px solid {C['accent']};
    color: #17100C;
}}
QPushButton[kind="primary"]:hover {{
    background: {C['accent_hi']};
    border-color: {C['accent_hi']};
}}
QPushButton[kind="primary"]:disabled {{ background: {C['raised']}; border-color: {C['border']}; color: {C['muted']}; }}

QPushButton[kind="danger"] {{ color: {C['failed']}; }}
QPushButton[kind="danger"]:hover {{ border-color: {C['failed']}; background: {C['raised_hi']}; }}

QPushButton[kind="ghost"] {{
    background: transparent;
    border: 1px solid transparent;
    color: {C['muted']};
    font-weight: 500;
    padding: {max(4, t['pad_y'] - 2)}px {max(8, t['pad_x'] - 4)}px;
}}
QPushButton[kind="ghost"]:hover {{ color: {C['text']}; border-color: {C['border']}; }}

/* ---------- source tabs ---------- */
QPushButton[kind="tab"] {{
    background: {C['raised']};
    border: 1px solid {C['border']};
    border-radius: 8px;
    padding: {max(5, t['pad_y'] - 1)}px {t['pad_x']}px;
    color: {C['muted']};
    font-size: {body - 1}px;
    font-weight: 600;
}}
QPushButton[kind="tab"]:hover {{
    color: {C['text']};
    border-color: {C['faint']};
}}
QPushButton[kind="tab"]:checked {{
    background: {C['accent']};
    border-color: {C['accent']};
    color: #17100C;
}}

/* ---------- workspace ---------- */
#WorkHeader {{
    background: {C['bg']};
    border-bottom: 1px solid {C['border']};
}}
#NavBar {{
    background: {C['bg']};
    border-bottom: 1px solid {C['border']};
}}
#Chip {{
    background: {C['panel']};
    border: 1px solid {C['border']};
    border-radius: 9px;
}}
QLabel[role="chipValue"] {{ font-size: {t['title'] - 2}px; font-weight: 700; background: transparent; }}
QLabel[role="chipLabel"] {{
    font-size: {caption}px; letter-spacing: 1.5px; color: {C['faint']};
    font-weight: 700; background: transparent;
}}

#Card {{
    background: {C['panel']};
    border: 1px solid {C['border']};
    border-radius: 10px;
}}
#Card:hover {{ border-color: {C['faint']}; }}
#Spine {{ border-radius: 2px; }}
QLabel[role="cardTitle"] {{ font-size: {body}px; font-weight: 600; background: transparent; }}
QLabel[role="cardUrl"] {{
    font-family: 'Consolas', 'Cascadia Mono', monospace;
    font-size: {body - 2}px; color: {C['faint']}; background: transparent;
}}
QLabel[role="meta"] {{
    font-family: 'Consolas', 'Cascadia Mono', monospace;
    font-size: {body - 2}px; color: {C['muted']}; background: transparent;
}}
QLabel[role="error"] {{ font-size: {body - 2}px; color: {C['failed']}; background: transparent; }}
QLabel[role="badge"] {{
    background: {C['raised']};
    border: 1px solid {C['border']};
    border-radius: 5px;
    padding: 2px 7px;
    font-size: {caption}px;
    font-weight: 700;
    letter-spacing: 1px;
    color: {C['muted']};
}}
QLabel[role="status"] {{
    font-size: {caption}px; font-weight: 700; letter-spacing: 1.5px; background: transparent;
}}
#EmptyState {{
    color: {C['faint']};
    font-size: {body}px;
    background: transparent;
}}

QProgressBar {{
    background: {C['raised']};
    border: none;
    border-radius: 3px;
    height: 6px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    border-radius: 3px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {C['accent']}, stop:1 {C['amber']});
}}

QCheckBox {{
    spacing: 8px; color: {C['muted']}; background: transparent;
    /* The box itself is small, so the row around it is given the height a
       pointer needs to hit it. */
    min-height: 24px;
}}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {C['border']};
    border-radius: 4px;
    background: {C['raised']};
}}
QCheckBox::indicator:hover {{ border-color: {C['accent']}; }}
QCheckBox::indicator:checked {{
    background: {C['accent']};
    border-color: {C['accent']};
}}

QScrollArea {{ border: none; background: {C['bg']}; }}
#QueueHost {{ background: {C['bg']}; }}
QScrollBar:vertical {{
    background: transparent; width: 10px; margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {C['raised_hi']}; border-radius: 5px; min-height: 40px;
}}
QScrollBar::handle:vertical:hover {{ background: {C['faint']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}

#StatusBar {{
    background: {C['panel']};
    border-top: 1px solid {C['border']};
}}
QLabel[role="statusText"] {{
    color: {C['muted']};
    font-size: {body - 2}px;
    background: transparent;
}}

/* ---------- usage notice ---------- */
#NoticeBar {{
    background: #241C14;
    border-top: 1px solid #3E2F1C;
}}
QLabel[role="notice"] {{
    color: {C['amber']};
    font-size: {body - 2}px;
    font-weight: 600;
    letter-spacing: 0.2px;
    background: transparent;
}}

/* ---------- social bar ---------- */
#SocialBar {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #141020, stop:1 #17121F);
    border-top: 1px solid {C['border']};
}}
QLabel[role="follow"] {{
    color: {C['accent']};
    font-size: {body}px;
    font-weight: 800;
    letter-spacing: 3px;
    background: transparent;
}}

QToolTip {{
    background: {C['raised']};
    color: {C['text']};
    border: 1px solid {C['border']};
    padding: 5px 8px;
}}

/* ---------- settings page ---------- */
#SettingsPage, #SettingsHost {{ background: {C['bg']}; }}
QLabel[role="cardHint"] {{ color: {C['faint']}; font-size: {caption}px; }}

/* ---------- tables ---------- */
QTableWidget {{
    background: {C['panel']};
    border: 1px solid {C['border']};
    border-radius: 10px;
    gridline-color: {C['border']};
    selection-background-color: {C['raised_hi']};
    selection-color: {C['text']};
}}
QTableWidget::item {{ padding: 6px 8px; }}
QHeaderView::section {{
    background: {C['panel']};
    color: {C['accent']};
    border: none;
    border-bottom: 1px solid {C['border']};
    padding: 8px;
    font-weight: 700;
}}
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
    global CURRENT_DENSITY
    name = "compact" if compact else "comfortable"
    CURRENT_DENSITY = name
    tokens = DENSITY[name]

    app = QApplication.instance()
    if app is not None:
        app.setStyleSheet(stylesheet(name))

    _rescale_layouts(window, tokens["scale"])
    _rescale_controls(window, tokens["scale"], tokens["control"])

    rail = window.findChild(QWidget, "Rail")
    if rail is not None:
        _remember_base(rail, "densityRailWidth", tokens["rail"])
        rail.setFixedWidth(tokens["rail"])

    window.updateGeometry()
    window.layout().activate()
