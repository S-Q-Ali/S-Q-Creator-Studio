"""Niche-Scope themed stylesheet for the research UI (Tailwind zinc + red-600).

The research suite renders its own look (white/zinc cards, red accent, auto
dark mode) independently of the app's dark-cyan downloader theme: each research
page applies ``research_style()`` to its own widget tree, so colors never leak
the other way.
"""

from __future__ import annotations

import os

from PySide6.QtGui import QGuiApplication, QStyleHints

# Tailwind palette used by Niche-Scope
RED_600 = "#dc2626"
RED_700 = "#b91c1c"
ZINC_50 = "#fafafa"
ZINC_100 = "#f4f4f5"
ZINC_200 = "#e4e4e7"
ZINC_300 = "#d4d4d8"
ZINC_400 = "#a1a1aa"
ZINC_500 = "#71717a"
ZINC_600 = "#52525b"
ZINC_700 = "#3f3f46"
ZINC_800 = "#27272a"
ZINC_850 = "#1f1f23"
ZINC_900 = "#18181b"
GREEN_50 = "#f0fdf4"
GREEN_100 = "#dcfce7"
GREEN_600 = "#16a34a"
GREEN_700 = "#15803d"
GREEN_800 = "#166534"
YELLOW_100 = "#fef9c3"
YELLOW_600 = "#ca8a04"
YELLOW_700 = "#a16207"
BLUE_100 = "#dbeafe"
BLUE_700 = "#1d4ed8"
PURPLE_100 = "#f3e8ff"
PURPLE_700 = "#7e22ce"

LIGHT: dict[str, str] = {
    "bg": ZINC_50,
    "card_bg": "#ffffff",
    "card_border": ZINC_200,
    "card_border_hover": ZINC_300,
    "panel_bg": ZINC_100,
    "text_primary": ZINC_900,
    "text_secondary": ZINC_500,
    "input_bg": "#ffffff",
    "input_border": ZINC_200,
    "hover_bg": ZINC_50,
    "hover_border": ZINC_300,
    "toggle_bg": ZINC_100,
    "shadow": "rgba(0, 0, 0, 0.08)",
}

DARK: dict[str, str] = {
    "bg": ZINC_900,
    "card_bg": ZINC_800,
    "card_border": ZINC_700,
    "card_border_hover": ZINC_600,
    "panel_bg": ZINC_850,
    "text_primary": "#ffffff",
    "text_secondary": ZINC_400,
    "input_bg": ZINC_800,
    "input_border": ZINC_700,
    "hover_bg": ZINC_700,
    "hover_border": ZINC_600,
    "toggle_bg": ZINC_700,
    "shadow": "rgba(0, 0, 0, 0.5)",
}


def system_dark_preferred() -> bool:
    try:
        scheme = QGuiApplication.styleHints().colorScheme()
        return scheme in (QStyleHints.ColorScheme.Dark, QStyleHints.ColorScheme.Unknown)
    except Exception:
        return bool(os.environ.get("QT_QPA_PLATFORM") != "offscreen")


def research_style(dark: bool | None = None) -> str:
    """Build the full Niche-Scope stylesheet for the research UI subtree."""
    if dark is None:
        dark = system_dark_preferred()
    c = DARK if dark else LIGHT
    return _build_qss(c, dark)


def _build_qss(c: dict[str, str], dark: bool) -> str:
    solution = DARK if dark else LIGHT
    return f"""
QWidget#researchPage {{
    background-color: {c["bg"]};
    color: {c["text_primary"]};
    font-size: 14px;
}}

QWidget {{
    color: {c["text_primary"]};
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
    background-color: {GREEN_100};
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
    color: {GREEN_700};
    background-color: {GREEN_100};
    border-radius: 999px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
}}
QLabel#badgeScoreMid {{
    color: {YELLOW_700};
    background-color: {YELLOW_100};
    border-radius: 999px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
}}
QLabel#badgeScoreLow {{
    color: {c["text_primary"]};
    background-color: {c["panel_bg"]};
    border-radius: 999px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
}}
QLabel#badgeNew {{
    color: {BLUE_700};
    background-color: {BLUE_100};
    border-radius: 999px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
}}
QLabel#badgeRapid {{
    color: {GREEN_700};
    background-color: {GREEN_100};
    border-radius: 999px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
}}
QLabel#badgeAi {{
    color: {PURPLE_700};
    background-color: {PURPLE_100};
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
QLabel#scoreBadgeGreen {{ background-color: #22c55e; }}
QLabel#scoreBadgeLime {{ background-color: #84cc16; }}
QLabel#scoreBadgeYellow {{ background-color: #eab308; }}
QLabel#scoreBadgeOrange {{ background-color: #f97316; }}
QLabel#scoreBadgeRed {{ background-color: #dc2626; }}

QLabel#scoreBadgeSmGreen, QLabel#scoreBadgeSmLime, QLabel#scoreBadgeSmYellow,
QLabel#scoreBadgeSmOrange, QLabel#scoreBadgeSmRed {{
    color: #ffffff;
    font-weight: 600;
    font-size: 11px;
    padding: 2px 6px;
    border-radius: 5px;
}}
QLabel#scoreBadgeSmGreen {{ background-color: #22c55e; }}
QLabel#scoreBadgeSmLime {{ background-color: #84cc16; }}
QLabel#scoreBadgeSmYellow {{ background-color: #eab308; }}
QLabel#scoreBadgeSmOrange {{ background-color: #f97316; }}
QLabel#scoreBadgeSmRed {{ background-color: #dc2626; }}

QLabel#scoreBadgeLgGreen, QLabel#scoreBadgeLgLime, QLabel#scoreBadgeLgYellow,
QLabel#scoreBadgeLgOrange, QLabel#scoreBadgeLgRed {{
    color: #ffffff;
    font-weight: 600;
    font-size: 15px;
    padding: 6px 14px;
    border-radius: 8px;
}}
QLabel#scoreBadgeLgGreen {{ background-color: #22c55e; }}
QLabel#scoreBadgeLgLime {{ background-color: #84cc16; }}
QLabel#scoreBadgeLgYellow {{ background-color: #eab308; }}
QLabel#scoreBadgeLgOrange {{ background-color: #f97316; }}
QLabel#scoreBadgeLgRed {{ background-color: #dc2626; }}

QLabel#competitionBadgeDc2626 {{
    color: #ffffff;
    background-color: #dc2626;
    border-radius: 999px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: 600;
}}
QLabel#competitionBadgeEab308 {{
    color: #000000;
    background-color: #eab308;
    border-radius: 999px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: 600;
}}
QLabel#competitionBadge16a34a {{
    color: #ffffff;
    background-color: #16a34a;
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
QLabel#linkLabel {{ color: {RED_600}; font-size: 12px; font-weight: 600; }}
QLabel#chip {{
    background-color: {c["panel_bg"]};
    border: 1px solid {c["card_border"]};
    border-radius: 999px;
    padding: 4px 12px;
    font-size: 12px;
}}
QLabel#chip:hover {{ border: 1px solid {RED_600}; color: {RED_600}; }}

/* ---- Scorecard ---- */
QLabel#seoCheckPass {{
    background-color: #22c55e;
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
    background-color: #eab308;
    border-radius: 8px;
    color: #000000;
    font-weight: 700;
    font-size: 9px;
    min-width: 15px;
    min-height: 15px;
    max-width: 15px;
    max-height: 15px;
}}
QLabel#seoCheckFail {{
    background-color: #dc2626;
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
    background-color: {RED_600};
    color: #ffffff;
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
    background-color: {RED_600};
    color: #ffffff;
    border: none;
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 500;
}}
QPushButton:hover {{
    background-color: {RED_700};
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
    background-color: {RED_600};
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
    selection-background-color: {RED_600};
    selection-color: #ffffff;
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{
    border: 1px solid {RED_600};
}}

/* ---- Scroll areas ---- */
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{
    background: {c["input_border"]};
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
    color: #dc2626;
}}
QLabel#statusOk {{
    font-size: 12px;
    font-weight: 500;
    color: {GREEN_600};
}}

/* ---- Growth / misc text ---- */
QLabel#growthPositive {{ color: {GREEN_600}; font-weight: 500; font-size: 13px; }}
QLabel#growthNegative {{ color: #dc2626; font-weight: 500; font-size: 13px; }}
QLabel#rpmLabel {{ color: {GREEN_700}; font-size: 12px; font-weight: 600; }}
QLabel#rpmSubLabel {{ color: {GREEN_700}; font-size: 10px; }}

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
    background-color: {RED_600};
    color: #ffffff;
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
    background-color: {solution["text_primary"]};
    color: {solution["card_bg"]};
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
    font-size: 14px;
    font-weight: 700;
    color: {c["text_primary"]};
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
QPushButton[sidebar="true"][active="true"] {{ background-color: {RED_600}; color: #ffffff; }}
W
"""
