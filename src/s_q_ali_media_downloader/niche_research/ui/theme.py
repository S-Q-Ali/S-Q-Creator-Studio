"""Unified dark ink-plum stylesheet for the research UI.

The research suite used to ship its own separate look (white/zinc cards, red
accent, OS-driven light/dark switching). As of 2.1 it renders the app's single
dark ink-plum palette with a cyan accent, so the Niche Research surface reads as
one family with the downloader: ``research_style()`` always returns the dark
theme now, and the ``dark`` argument is kept only for API compatibility.
"""

from __future__ import annotations

# App-wide palette (dark ink-plum + cyan accent) — mirrors theme.py.C
BG = "#100E14"
CARD = "#1A1722"
PANEL = "#241F30"
BORDER = "#2A2534"
BORDER_HOVER = "#3A3347"
TEXT = "#EAE8F1"
MUTED = "#8B83A0"

ACCENT = "#22D3EE"
ACCENT_HOVER = "#67E8F9"
ACCENT_TEXT = "#062A2A"
TEAL = "#2DD4BF"

GREEN = "#34D399"
YELLOW = "#FBBF24"
RED = "#F87171"
BLUE = "#93C5FD"
PURPLE = "#C084FC"
DANGER = "#DC2626"

# Score-badge fills — Tailwind 700-line solids, WCAG-AA with white text
GREEN_FILL = "#15803d"
LIME_FILL = "#4d7c0f"
YELLOW_FILL = "#a16207"
ORANGE_FILL = "#c2410c"
RED_FILL = "#b91c1c"

# Soft chip fills for tier/new/rapid/AI badges against the dark background
CHIP_GREEN_BG = "#052E16"
CHIP_AMBER_BG = "#451A03"
CHIP_BLUE_BG = "#172554"
CHIP_PURPLE_BG = "#3B0764"

# App-wide type family — matches the downloader's theme.py so the research
# suite reads as one family with the rest of the app.
FONT_FAMILY = "'Segoe UI Variable Display', 'Segoe UI', 'Inter', sans-serif"

_C = {
    "bg": BG,
    "card_bg": CARD,
    "card_border": BORDER,
    "card_border_hover": BORDER_HOVER,
    "panel_bg": PANEL,
    "text_primary": TEXT,
    "text_secondary": MUTED,
    "input_bg": PANEL,
    "input_border": BORDER,
    "hover_bg": BORDER,
    "hover_border": BORDER_HOVER,
    "toggle_bg": PANEL,
    "shadow": "rgba(0, 0, 0, 0.5)",
}


def research_style(dark: bool | None = None) -> str:
    """Build the full research stylesheet (single dark theme).

    ``dark`` is accepted for compatibility with older call sites but ignored –
    the suite always renders the unified dark ink-plum theme.
    """
    return _build_qss(_C)


def _build_qss(c: dict[str, str]) -> str:
    return f"""
QWidget#researchPage {{
    background-color: {c["bg"]};
    color: {c["text_primary"]};
    font-family: {FONT_FAMILY};
    font-size: 14px;
}}

QWidget {{
    color: {c["text_primary"]};
    font-family: {FONT_FAMILY};
}}

QLabel#headerTitle {{
    font-size: 20px;
    font-weight: 700;
    color: {c["text_primary"]};
}}
QLabel#headerSubtitle {{
    font-size: 13px;
    color: {c["text_secondary"]};
}}
QLabel#sectionLabel {{
    font-size: 15px;
    font-weight: 600;
    color: {c["text_primary"]};
}}
QLabel#smallLabel {{
    font-size: 11px;
    color: {c["text_secondary"]};
}}

/* ---- Cards ---- */
QFrame#card {{
    background-color: {c["card_bg"]};
    border: 1px solid {c["card_border"]};
    border-radius: 12px;
}}
QFrame#card[hoverable="true"]:hover {{
    border: 1px solid {c["card_border_hover"]};
}}
QFrame#panel {{
    background-color: {c["panel_bg"]};
    border: 1px solid {c["card_border"]};
    border-radius: 8px;
}}
QFrame#rpmBar {{
    background-color: rgba(45, 212, 191, 0.10);
    border-radius: 8px;
}}
QFrame#emptyState {{
    background-color: transparent;
    border: 2px dashed {c["card_border"]};
    border-radius: 12px;
}}

/* ---- Stat block (Subs/Views/Videos) ---- */
QLabel#statValue {{
    font-size: 18px;
    font-weight: 700;
    color: {c["text_primary"]};
}}
QLabel#statKey {{
    font-size: 10px;
    text-transform: uppercase;
    color: {c["text_secondary"]};
    letter-spacing: 0.5px;
}}

/* ---- Badges ---- */
QPushButton#badge, QLabel#badge {{
    border: none;
    border-radius: 999px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
    background-color: transparent;
}}
QLabel#badgeScoreHigh {{
    color: {GREEN};
    background-color: {CHIP_GREEN_BG};
    border-radius: 999px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
}}
QLabel#badgeScoreMid {{
    color: {YELLOW};
    background-color: {CHIP_AMBER_BG};
    border-radius: 999px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
}}
QLabel#badgeScoreLow {{
    color: {c["text_secondary"]};
    background-color: {c["panel_bg"]};
    border-radius: 999px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
}}
QLabel#badgeNew {{
    color: {BLUE};
    background-color: {CHIP_BLUE_BG};
    border-radius: 999px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
}}
QLabel#badgeRapid {{
    color: {GREEN};
    background-color: {CHIP_GREEN_BG};
    border-radius: 999px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
}}
QLabel#badgeAi {{
    color: {PURPLE};
    background-color: {CHIP_PURPLE_BG};
    border-radius: 999px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
}}

/* ---- Score / competition badges (keyword research) ---- */
QLabel#scoreBadgeGreen, QLabel#scoreBadgeLime, QLabel#scoreBadgeYellow,
QLabel#scoreBadgeOrange, QLabel#scoreBadgeRed {{
    color: #ffffff;
    font-weight: 600;
    font-size: 12px;
    padding: 3px 8px;
    border-radius: 6px;
}}
QLabel#scoreBadgeGreen {{ background-color: {GREEN_FILL}; }}
QLabel#scoreBadgeLime {{ background-color: {LIME_FILL}; }}
QLabel#scoreBadgeYellow {{ background-color: {YELLOW_FILL}; }}
QLabel#scoreBadgeOrange {{ background-color: {ORANGE_FILL}; }}
QLabel#scoreBadgeRed {{ background-color: {RED_FILL}; }}

QLabel#scoreBadgeSmGreen, QLabel#scoreBadgeSmLime, QLabel#scoreBadgeSmYellow,
QLabel#scoreBadgeSmOrange, QLabel#scoreBadgeSmRed {{
    color: #ffffff;
    font-weight: 600;
    font-size: 11px;
    padding: 2px 6px;
    border-radius: 5px;
}}
QLabel#scoreBadgeSmGreen {{ background-color: {GREEN_FILL}; }}
QLabel#scoreBadgeSmLime {{ background-color: {LIME_FILL}; }}
QLabel#scoreBadgeSmYellow {{ background-color: {YELLOW_FILL}; }}
QLabel#scoreBadgeSmOrange {{ background-color: {ORANGE_FILL}; }}
QLabel#scoreBadgeSmRed {{ background-color: {RED_FILL}; }}

QLabel#scoreBadgeLgGreen, QLabel#scoreBadgeLgLime, QLabel#scoreBadgeLgYellow,
QLabel#scoreBadgeLgOrange, QLabel#scoreBadgeLgRed {{
    color: #ffffff;
    font-weight: 600;
    font-size: 15px;
    padding: 6px 14px;
    border-radius: 8px;
}}
QLabel#scoreBadgeLgGreen {{ background-color: {GREEN_FILL}; }}
QLabel#scoreBadgeLgLime {{ background-color: {LIME_FILL}; }}
QLabel#scoreBadgeLgYellow {{ background-color: {YELLOW_FILL}; }}
QLabel#scoreBadgeLgOrange {{ background-color: {ORANGE_FILL}; }}
QLabel#scoreBadgeLgRed {{ background-color: {RED_FILL}; }}

QLabel#competitionBadgeDc2626 {{
    color: #ffffff;
    background-color: #b91c1c;
    border-radius: 999px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: 600;
}}
QLabel#competitionBadgeEab308 {{
    color: #ffffff;
    background-color: #a16207;
    border-radius: 999px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: 600;
}}
QLabel#competitionBadge16a34a {{
    color: #ffffff;
    background-color: #15803d;
    border-radius: 999px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: 600;
}}

/* ---- Keyword detail header ---- */
QLabel#kwTitle {{ font-size: 18px; font-weight: 700; }}
QLabel#kwMuted {{ font-size: 12px; color: {c["text_secondary"]}; }}
QLabel#kwMetricValue {{ font-size: 20px; font-weight: 700; }}
QLabel#kwMetricLabel {{ font-size: 10px; text-transform: uppercase; color: {c["text_secondary"]}; }}

/* ---- Keyword table / chips ---- */
QLabel#linkLabel {{ color: {ACCENT_HOVER}; font-size: 12px; font-weight: 600; }}
QLabel#chip {{
    background-color: {c["panel_bg"]};
    border: 1px solid {c["card_border"]};
    border-radius: 999px;
    padding: 4px 12px;
    font-size: 12px;
}}
QLabel#chip:hover {{ border: 1px solid {ACCENT}; color: {ACCENT_HOVER}; }}

/* ---- Scorecard ---- */
QLabel#seoCheckPass {{
    background-color: #15803d;
    border-radius: 8px;
    color: #ffffff;
    font-weight: 700;
    font-size: 9px;
    min-width: 15px;
    min-height: 15px;
    max-width: 15px;
    max-height: 15px;
}}
QLabel#seoCheckPart {{
    background-color: #a16207;
    border-radius: 8px;
    color: #ffffff;
    font-weight: 700;
    font-size: 9px;
    min-width: 15px;
    min-height: 15px;
    max-width: 15px;
    max-height: 15px;
}}
QLabel#seoCheckFail {{
    background-color: #b91c1c;
    border-radius: 8px;
    color: #ffffff;
    font-weight: 700;
    font-size: 9px;
    min-width: 15px;
    min-height: 15px;
    max-width: 15px;
    max-height: 15px;
}}
QLabel#checkName {{ font-size: 13px; }}
QLabel#checkMeta {{ font-size: 12px; color: {c["text_secondary"]}; }}
QLabel#urlTitle {{ font-size: 16px; font-weight: 600; }}
QLabel#urlMeta {{ font-size: 12px; color: {c["text_secondary"]}; }}
QPushButton#modeToggle {{
    background-color: {c["card_bg"]};
    color: {c["text_secondary"]};
    border: none;
    border-radius: 0;
    padding: 8px 18px;
    font-size: 13px;
}}
QPushButton#modeToggle[active="true"] {{
    background-color: {ACCENT};
    color: {ACCENT_TEXT};
}}

QTableWidget {{
    background-color: {c["card_bg"]};
    color: {c["text_primary"]};
    border: 1px solid {c["card_border"]};
    border-radius: 8px;
    gridline-color: {c["card_border"]};
    font-size: 13px;
}}
QTableWidget::item {{ border: none; padding: 8px; }}
QTableWidget::item:selected {{ background-color: {c["hover_bg"]}; color: {c["text_primary"]}; }}
QHeaderView::section {{
    background-color: {c["panel_bg"]};
    color: {c["text_secondary"]};
    border: none;
    border-bottom: 1px solid {c["card_border"]};
    padding: 8px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
}}

/* ---- Buttons ---- */
QPushButton {{
    background-color: {ACCENT};
    color: {ACCENT_TEXT};
    border: none;
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 500;
}}
QPushButton:hover {{
    background-color: {ACCENT_HOVER};
}}
QPushButton:disabled {{
    background-color: {c["hover_bg"]};
    color: {c["text_secondary"]};
}}
QPushButton[variant="outline"] {{
    background-color: {c["card_bg"]};
    color: {c["text_primary"]};
    border: 1px solid {c["input_border"]};
}}
QPushButton[variant="outline"]:hover {{
    background-color: {c["hover_bg"]};
    border: 1px solid {c["hover_border"]};
}}
QPushButton[variant="ghost"] {{
    background-color: transparent;
    color: {c["text_secondary"]};
    padding: 6px 10px;
    font-size: 12px;
}}
QPushButton[variant="ghost"]:hover {{
    color: {c["text_primary"]};
    background-color: {c["hover_bg"]};
}}
QPushButton[variant="danger"] {{
    background-color: {DANGER};
    color: #ffffff;
}}

/* ---- Inputs ---- */
QComboBox {{
    background-color: {c["input_bg"]};
    color: {c["text_primary"]};
    border: 1px solid {c["input_border"]};
    border-radius: 8px;
    padding: 7px 14px;
    font-size: 13px;
    min-height: 18px;
}}
QComboBox:hover {{
    border: 1px solid {c["hover_border"]};
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    background-color: {c["input_bg"]};
    color: {c["text_primary"]};
    border: 1px solid {c["input_border"]};
    selection-background-color: {c["hover_bg"]};
    selection-color: {c["text_primary"]};
    outline: none;
    padding: 4px;
}}
QComboBox QAbstractItemView::item {{
    padding: 6px 10px;
}}
QComboBox QAbstractItemView::item:selected {{
    background-color: {c["hover_bg"]};
    color: {c["text_primary"]};
}}
QLineEdit, QPlainTextEdit, QTextEdit {{
    background-color: {c["input_bg"]};
    color: {c["text_primary"]};
    border: 1px solid {c["input_border"]};
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 13px;
    selection-background-color: {ACCENT};
    selection-color: {ACCENT_TEXT};
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{
    border: 1px solid {ACCENT};
}}

/* ---- Scroll areas ---- */
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{
    background: #3A3347;
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}

/* ---- Status bar ---- */
QFrame#statusBar {{
    background-color: {c["panel_bg"]};
    border: 1px solid {c["card_border"]};
    border-radius: 8px;
}}
QLabel#statusText {{
    font-size: 12px;
    color: {c["text_secondary"]};
}}
QLabel#statusError {{
    font-size: 12px;
    font-weight: 500;
    color: {RED};
}}
QLabel#statusOk {{
    font-size: 12px;
    font-weight: 500;
    color: {GREEN};
}}

/* ---- Growth / misc text ---- */
QLabel#growthPositive {{ color: {GREEN}; font-weight: 500; font-size: 13px; }}
QLabel#growthNegative {{ color: {RED}; font-weight: 500; font-size: 13px; }}
QLabel#rpmLabel {{ color: {TEAL}; font-size: 12px; font-weight: 600; }}
QLabel#rpmSubLabel {{ color: {TEAL}; font-size: 10px; }}

/* ---- Modal (Analysis dialog) ---- */
QDialog#analysisModal {{ background-color: {c["panel_bg"]}; }}
QFrame#modalPanel {{
    background-color: {c["card_bg"]};
    border: 1px solid {c["card_border"]};
    border-radius: 12px;
}}
QLabel#modalHeader {{ font-size: 17px; font-weight: 600; color: {c["text_primary"]}; }}
QLabel#modalSubHeader {{ font-size: 12px; color: {c["text_secondary"]}; }}
QPushButton#tabBtn {{
    background-color: {c["card_bg"]};
    color: {c["text_secondary"]};
    border: none;
    border-radius: 8px;
    padding: 7px 14px;
    font-size: 12px;
    font-weight: 500;
}}
QPushButton#tabBtn:hover {{ background-color: {c["hover_bg"]}; color: {c["text_primary"]}; }}
QPushButton#tabBtn[active="true"] {{
    background-color: {ACCENT};
    color: {ACCENT_TEXT};
}}
QLabel#statTileValue {{ font-size: 16px; font-weight: 700; color: {c["text_primary"]}; }}
QLabel#statTileLabel {{ font-size: 11px; color: {c["text_secondary"]}; }}
QFrame#svgCard {{ background-color: {c["panel_bg"]}; border: 1px solid {c["card_border"]}; border-radius: 10px; }}
QLabel#svgMeta {{ font-size: 11px; color: {c["text_secondary"]}; text-transform: uppercase; font-weight: 600; letter-spacing: 0.4px; }}
QLabel#svgBody {{ font-size: 13px; color: {c["text_primary"]}; }}
QFrame#thumbPreview {{
    background-color: {c["panel_bg"]};
    border: 1px solid {c["card_border"]};
    border-radius: 8px;
}}

/* ---- Settings ---- */
QLabel#settingsTitle {{ font-size: 15px; font-weight: 600; color: {c["text_primary"]}; }}
QLabel#settingsHint {{ font-size: 12px; color: {c["text_secondary"]}; }}
QLabel#formLabel {{ font-size: 13px; font-weight: 500; color: {c["text_primary"]}; }}
QLabel#formHint {{ font-size: 11px; color: {c["text_secondary"]}; }}

/* ---- Tooltips ---- */
QToolTip {{
    background-color: {PANEL};
    color: {TEXT};
    border: 1px solid {BORDER_HOVER};
    border-radius: 6px;
    padding: 6px 8px;
    font-size: 12px;
}}

/* ---- Research container sidebar ---- */
QFrame#researchSidebar {{
    background-color: {c["card_bg"]};
    border-right: 1px solid {c["card_border"]};
}}
QLabel#researchBrand {{
    font-size: 15px;
    font-weight: 800;
    color: {c["text_primary"]};
    text-transform: uppercase;
    letter-spacing: 1.5px;
}}
QLabel#researchSub {{ font-size: 11px; color: {c["text_secondary"]}; }}
QPushButton[sidebar="true"] {{
    background-color: transparent;
    color: {c["text_secondary"]};
    border: none;
    border-radius: 8px;
    padding: 9px 12px;
    font-size: 13px;
    font-weight: 500;
    text-align: left;
}}
QPushButton[sidebar="true"]:hover {{ background-color: {c["hover_bg"]}; color: {c["text_primary"]}; }}
QPushButton[sidebar="true"][active="true"] {{ background-color: {ACCENT}; color: {ACCENT_TEXT}; }}
"""