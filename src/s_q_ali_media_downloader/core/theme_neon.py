"""Neon theme styling for S-Q Creator Studio.

Qt Style Sheets support a narrower property set than the web: there is no
``box-shadow``, ``text-shadow``, ``transition`` or CSS animation. The neon
look is built from high-contrast borders, gradients and the real drop-shadow
effects applied to the primary buttons in the main window.
"""

from typing import ClassVar

from PySide6.QtWidgets import QApplication


class NeonTheme:
    """Neon theme implementation with vibrant electric-blue accents."""

    # Color Palette
    COLORS: ClassVar[dict[str, str]] = {
        # Base colors
        "bg_primary": "#0a0a0a",
        "bg_deep": "#070b12",
        "bg_surface": "#0e1626",
        "bg_elevated": "#101b2d",
        "bg_rail": "#0c1220",
        # Electric Blue (primary)
        "primary": "#00d4ff",
        "primary_light": "#67e8f9",
        "primary_dark": "#0ea5e9",
        "primary_glow": "#7dd3fc",
        # Electric Purple (secondary)
        "secondary": "#7c3aed",
        "secondary_light": "#a855f7",
        "secondary_dark": "#6d28d9",
        # Electric Pink (accent)
        "accent": "#ec4899",
        "accent_light": "#f472b6",
        "accent_dark": "#db2777",
        # Status colors
        "success": "#10b981",
        "success_glow": "#34d399",
        "warning": "#f59e0b",
        "warning_glow": "#fbbf24",
        "error": "#ef4444",
        "error_glow": "#f87171",
        # Text colors
        "text_primary": "#e8f6ff",
        "text_secondary": "#b9cbe0",
        "text_muted": "#8b9bb4",
        "text_disabled": "#5b6b80",
        # Borders
        "border": "#1b2b44",
        "border_strong": "#243b5a",
        "border_light": "#2b476b",
    }

    @classmethod
    def get_stylesheet(cls) -> str:
        """Get the complete neon stylesheet."""
        return cls._get_main_stylesheet()

    @classmethod
    def apply(cls, app: QApplication):
        """Apply neon theme to the application."""
        app.setStyleSheet(cls.get_stylesheet())

    @classmethod
    def _get_main_stylesheet(cls) -> str:
        """Generate the main stylesheet."""
        c = cls.COLORS
        return f"""
/* ============================================================
   S-Q Creator Studio - Neon Theme
   Qt-valid QSS: gradients, borders and high-contrast accents.
   ============================================================ */

QWidget {{
    background-color: {c['bg_primary']};
    color: {c['text_primary']};
    font-family: "Segoe UI";
    font-size: 13px;
}}
QMainWindow, QDialog {{ background-color: {c['bg_primary']}; }}
QLabel {{ background: transparent; }}
QToolTip {{
    background-color: {c['bg_elevated']};
    color: {c['text_primary']};
    border: 1px solid {c['primary']};
    border-radius: 6px;
    padding: 6px 8px;
}}

/* ---------------- menus ---------------- */
QMenuBar {{
    background-color: {c['bg_rail']};
    color: {c['text_primary']};
    border-bottom: 1px solid {c['border']};
}}
QMenuBar::item {{ background: transparent; padding: 6px 12px; color: {c['text_primary']}; }}
QMenuBar::item:selected {{ background-color: {c['bg_elevated']}; color: {c['primary_light']}; }}
QMenu {{
    background-color: {c['bg_surface']};
    border: 1px solid {c['border_strong']};
    padding: 6px;
}}
QMenu::item {{ padding: 7px 24px 7px 12px; border-radius: 5px; color: {c['text_primary']}; }}
QMenu::item:selected {{ background-color: {c['primary']}; color: {c['bg_primary']}; }}
QMenu::separator {{ height: 1px; background: {c['border']}; margin: 6px 8px; }}

/* ---------------- left rail ---------------- */
#Rail {{
    background-color: {c['bg_rail']};
    border-right: 1px solid {c['border']};
}}
#Wordmark {{
    color: {c['text_primary']};
    font-size: 19px;
    font-weight: 800;
    background: transparent;
}}
#WordmarkSub {{
    color: {c['primary']};
    font-size: 10px;
    font-weight: 700;
    background: transparent;
}}
#RailStripe {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {c['primary']}, stop:0.5 {c['secondary_light']}, stop:1 {c['accent']});
    border: none;
    border-radius: 2px;
}}
#divider {{ background: {c['border_strong']}; }}

QLabel[role="section"] {{
    color: {c['primary_glow']};
    font-size: 10px;
    font-weight: 700;
    background: transparent;
}}
QLabel[role="hint"] {{
    color: {c['text_muted']};
    font-size: 11px;
    background: transparent;
}}
QLabel[role="pageTitle"] {{
    color: {c['primary']};
    font-size: 14px;
    font-weight: 800;
    background: transparent;
}}
#AgentHeader {{
    background-color: {c['bg_surface']};
    border: 1px solid {c['border']};
    border-radius: 12px;
}}

/* ---------------- inputs ---------------- */
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox {{
    background-color: {c['bg_surface']};
    border: 1px solid {c['border_strong']};
    border-radius: 8px;
    padding: 8px 10px;
    color: {c['text_primary']};
    selection-background-color: {c['primary']};
    selection-color: {c['bg_primary']};
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus {{
    border: 1px solid {c['primary']};
    background-color: {c['bg_elevated']};
}}
QLineEdit:disabled, QPlainTextEdit:disabled, QTextEdit:disabled, QComboBox:disabled {{
    color: {c['text_disabled']};
    border-color: {c['border']};
    background-color: {c['bg_rail']};
}}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox QAbstractItemView {{
    background-color: {c['bg_surface']};
    border: 1px solid {c['border_strong']};
    selection-background-color: {c['primary']};
    selection-color: {c['bg_primary']};
    color: {c['text_primary']};
    padding: 4px;
}}

/* ---------------- buttons ---------------- */
QPushButton {{
    background-color: {c['bg_elevated']};
    border: 1px solid {c['border_strong']};
    border-radius: 8px;
    padding: 8px 14px;
    color: {c['text_secondary']};
    font-weight: 600;
}}
QPushButton:hover {{
    background-color: #13233a;
    border-color: {c['primary']};
    color: #ffffff;
}}
QPushButton:pressed {{ background-color: #0b1524; }}
QPushButton:disabled {{
    background-color: {c['bg_rail']};
    border-color: {c['border']};
    color: {c['text_disabled']};
}}

QPushButton[kind="primary"] {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {c['primary']}, stop:1 {c['primary_dark']});
    border: 1px solid {c['primary_light']};
    color: {c['bg_primary']};
    font-weight: 800;
}}
QPushButton[kind="primary"]:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {c['primary_light']}, stop:1 {c['primary']});
    border-color: #ffffff;
    color: {c['bg_primary']};
}}
QPushButton[kind="primary"]:pressed {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {c['primary_dark']}, stop:1 {c['primary']});
}}
QPushButton[kind="primary"]:disabled {{
    background-color: {c['bg_elevated']};
    border-color: {c['border']};
    color: {c['text_disabled']};
}}

QPushButton[kind="danger"] {{ color: {c['error_glow']}; border-color: #4a1d2b; }}
QPushButton[kind="danger"]:hover {{
    border-color: {c['accent']};
    color: #ffe4ef;
    background-color: #2a1220;
}}

QPushButton[kind="ghost"] {{
    background: transparent;
    border: 1px solid transparent;
    color: {c['text_muted']};
    font-weight: 500;
    padding: 6px 10px;
}}
QPushButton[kind="ghost"]:hover {{
    color: {c['text_primary']};
    border-color: {c['border_strong']};
    background-color: {c['bg_surface']};
}}

QPushButton[kind="tab"] {{
    background-color: {c['bg_surface']};
    border: 1px solid {c['border']};
    border-radius: 8px;
    color: {c['text_muted']};
    font-weight: 600;
    /* Emoji glyphs fall back to a wider font than QFontMetrics measures, so
       the text needs padding or the last letter is clipped. Keep it small:
       the two source tabs share a 285px rail. */
    padding: 6px 10px;
}}
QPushButton[kind="tab"]:hover {{ color: {c['text_primary']}; border-color: {c['primary']}; }}
QPushButton[kind="tab"]:checked {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {c['primary']}, stop:1 {c['secondary']});
    border-color: {c['primary_light']};
    color: #ffffff;
}}

/* ---------------- workspace header ---------------- */
#WorkHeader, #NavBar {{
    background-color: {c['bg_primary']};
    border-bottom: 1px solid {c['border']};
}}
#Chip {{
    background-color: {c['bg_surface']};
    border: 1px solid {c['border']};
    border-radius: 9px;
}}
#Chip:hover {{ border-color: {c['primary']}; }}
QLabel[role="chipValue"] {{
    color: {c['primary']};
    font-size: 17px;
    font-weight: 800;
    background: transparent;
}}
QLabel[role="chipLabel"] {{
    color: {c['text_muted']};
    font-size: 9px;
    font-weight: 700;
    background: transparent;
}}

/* ---------------- queue cards ---------------- */
#Card {{
    background-color: {c['bg_surface']};
    border: 1px solid {c['border']};
    border-left: 3px solid {c['primary']};
    border-radius: 10px;
}}
#Card:hover {{ border-color: {c['primary']}; background-color: #101c2e; }}
#Spine {{ border-radius: 2px; }}
QLabel[role="cardTitle"] {{ color: #f8fbff; font-size: 13px; font-weight: 600; }}
QLabel[role="cardUrl"] {{ color: {c['primary_glow']}; font-size: 11px; }}
QLabel[role="meta"] {{ color: {c['text_muted']}; font-size: 11px; }}
QLabel[role="error"] {{ color: {c['error_glow']}; font-size: 11px; }}
QLabel[role="badge"] {{
    color: {c['primary']};
    font-size: 9px;
    font-weight: 800;
    border: 1px solid #1b4a63;
    border-radius: 6px;
    padding: 2px 6px;
}}
QLabel[role="status"] {{ font-weight: 700; }}
#EmptyState {{ color: {c['text_muted']}; font-size: 13px; }}

/* ---------------- progress, checks, scrollbars ---------------- */
QProgressBar {{
    background-color: {c['bg_surface']};
    border: 1px solid {c['border']};
    border-radius: 5px;
    height: 8px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {c['primary']}, stop:1 {c['secondary']});
    border-radius: 4px;
}}
QCheckBox {{
    spacing: 8px;
    color: {c['text_secondary']};
    background: transparent;
    /* The box is 16px; the row still needs a pointer-sized target. */
    min-height: 24px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {c['border_light']};
    border-radius: 4px;
    background-color: {c['bg_surface']};
}}
QCheckBox::indicator:hover {{ border-color: {c['primary']}; }}
QCheckBox::indicator:checked {{
    background-color: {c['primary']};
    border-color: {c['primary_light']};
}}
QScrollArea {{ border: none; background-color: {c['bg_primary']}; }}
#QueueHost {{ background-color: {c['bg_primary']}; }}
QScrollBar:vertical {{
    background: {c['bg_primary']};
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {c['border_strong']};
    border-radius: 5px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: {c['primary']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{ background: {c['bg_primary']}; height: 10px; margin: 0; }}
QScrollBar::handle:horizontal {{
    background: {c['border_strong']};
    border-radius: 5px;
    min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{ background: {c['primary']}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: transparent; }}

/* ---------------- status bar ---------------- */
#StatusBar {{
    background-color: {c['bg_rail']};
    border-top: 1px solid {c['border']};
}}
QLabel[role="statusText"] {{ color: {c['text_muted']}; font-size: 11px; }}
QLabel[role="notice"] {{ color: {c['warning_glow']}; font-size: 11px; font-weight: 600; }}

/* ---------------- settings / tables ---------------- */
#SettingsPage, #SettingsHost {{ background-color: {c['bg_primary']}; }}
QTableWidget {{
    background-color: {c['bg_surface']};
    alternate-background-color: #0b1320;
    color: {c['text_primary']};
    gridline-color: {c['border']};
    border: 1px solid {c['border']};
    border-radius: 8px;
    selection-background-color: #123a4d;
    selection-color: #ffffff;
}}
QTableWidget::item {{ padding: 6px 8px; }}
QHeaderView::section {{
    background-color: {c['bg_elevated']};
    color: {c['primary_glow']};
    border: none;
    border-bottom: 1px solid {c['border_strong']};
    padding: 6px 8px;
    font-weight: 700;
}}

/* ---------------- tabs (used by embedded pages) ---------------- */
QTabWidget::pane {{
    background-color: {c['bg_surface']};
    border: 1px solid {c['border']};
    border-radius: 10px;
}}
QTabBar::tab {{
    background-color: {c['bg_surface']};
    color: {c['text_muted']};
    padding: 8px 16px;
    margin-right: 4px;
    border: 1px solid {c['border']};
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
}}
QTabBar::tab:hover {{ color: {c['primary']}; border-color: {c['primary']}; }}
QTabBar::tab:selected {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {c['primary']}, stop:1 {c['secondary']});
    color: #ffffff;
    border-color: {c['primary_light']};
    font-weight: 700;
}}
"""
