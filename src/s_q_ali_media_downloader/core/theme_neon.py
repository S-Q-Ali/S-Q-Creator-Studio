"""Neon theme styling for S-Q Creator Studio.

A high-contrast, glowing UI design system with electric blue accents.
Perfect for modern desktop applications that need to stand out.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication


class NeonTheme:
    """Neon theme implementation with glow effects and vibrant colors."""
    
    # Color Palette
    COLORS = {
        # Base colors
        'bg_primary': '#0a0a0a',
        'bg_surface': '#1a1a2e',
        'bg_elevated': '#16213e',
        
        # Electric Blue (primary)
        'primary': '#00d4ff',
        'primary_light': '#38bdf8',
        'primary_dark': '#0ea5e9',
        'primary_glow': '#7dd3fc',
        
        # Electric Purple (secondary)
        'secondary': '#7c3aed',
        'secondary_light': '#a855f7',
        'secondary_dark': '#6d28d9',
        
        # Electric Pink (accent)
        'accent': '#ec4899',
        'accent_light': '#f472b6',
        'accent_dark': '#db2777',
        
        # Status colors
        'success': '#10b981',
        'success_glow': '#34d399',
        'warning': '#f59e0b',
        'warning_glow': '#fbbf24',
        'error': '#ef4444',
        'error_glow': '#f87171',
        
        # Text colors
        'text_primary': '#ffffff',
        'text_secondary': '#e0e0e0',
        'text_muted': '#a0a0a0',
        'text_disabled': '#707070',
        
        # Border colors
        'border_light': 'rgba(0, 212, 255, 0.2)',
        'border_medium': 'rgba(0, 212, 255, 0.3)',
        'border_strong': 'rgba(0, 212, 255, 0.5)',
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
        return f"""
/* ========================================
   S-Q Creator Studio - Neon Theme
   High-contrast glowing UI design system
   ======================================== */

/* Global Reset */
* {{
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}}

/* QMainWindow */
QMainWindow {{
    background-color: {cls.COLORS['bg_primary']};
    color: {cls.COLORS['text_primary']};
    font-family: "Segoe UI", "SF Pro", "Roboto", sans-serif;
}}

/* =====================
   MENUS & TOOLBARS
   ===================== */

QMenuBar {{
    background-color: {cls.COLORS['bg_surface']};
    color: {cls.COLORS['text_primary']};
    border-bottom: 2px solid {cls.COLORS['primary']};
    padding: 4px;
}}

QMenuBar::item {{
    background: transparent;
    padding: 6px 12px;
    border-radius: 4px;
    color: {cls.COLORS['text_primary']};
}}

QMenuBar::item:selected {{
    background-color: {cls.COLORS['primary']};
    color: {cls.COLORS['bg_primary']};
    box-shadow: 0 0 10px {cls.COLORS['primary_glow']};
}}

QMenu {{
    background-color: {cls.COLORS['bg_surface']};
    border: 1px solid {cls.COLORS['border_medium']};
    border-radius: 8px;
    padding: 8px;
}}

QMenu::item {{
    padding: 8px 32px 8px 16px;
    color: {cls.COLORS['text_primary']};
    border-radius: 4px;
    margin: 2px 4px;
}}

QMenu::item:selected {{
    background-color: {cls.COLORS['primary']};
    color: {cls.COLORS['bg_primary']};
    box-shadow: 0 0 15px {cls.COLORS['primary_glow']};
}}

QMenu::separator {{
    height: 1px;
    background: {cls.COLORS['border_medium']};
    margin: 8px 12px;
}}

/* =====================
   BUTTONS
   ===================== */

QPushButton {{
    background-color: transparent;
    border: 2px solid {cls.COLORS['primary']};
    border-radius: 8px;
    padding: 12px 24px;
    color: {cls.COLORS['primary']};
    font-weight: 600;
    font-size: 14px;
    min-width: 100px;
    min-height: 40px;
    box-shadow: 0 0 10px {cls.COLORS['primary']}20;
    transition: all 0.3s ease;
}}

QPushButton:hover {{
    background-color: {cls.COLORS['primary']};
    color: {cls.COLORS['bg_primary']};
    box-shadow: 
        0 0 20px {cls.COLORS['primary']},
        0 0 40px {cls.COLORS['primary']}40;
}}

QPushButton:pressed {{
    background-color: {cls.COLORS['primary_dark']};
    border-color: {cls.COLORS['primary_dark']};
    box-shadow: 0 0 10px {cls.COLORS['primary_dark']}30;
}}

QPushButton:disabled {{
    background-color: transparent;
    border-color: {cls.COLORS['text_disabled']};
    color: {cls.COLORS['text_disabled']};
    box-shadow: none;
}}

/* Primary gradient button */
QPushButton[theme="primary"] {{
    background: linear-gradient(135deg, {cls.COLORS['primary']}, {cls.COLORS['primary_light']});
    border: none;
    color: {cls.COLORS['bg_primary']};
    font-weight: 700;
    font-size: 15px;
    padding: 14px 32px;
    min-width: 120px;
    box-shadow: 
        0 0 20px {cls.COLORS['primary']},
        0 8px 32px {cls.COLORS['primary']}30;
}}

QPushButton[theme="primary"]:hover {{
    box-shadow: 
        0 0 30px {cls.COLORS['primary']},
        0 12px 48px {cls.COLORS['primary']}50;
    transform: translateY(-2px);
}}

/* Secondary button */
QPushButton[theme="secondary"] {{
    background: transparent;
    border: 2px solid {cls.COLORS['secondary']};
    color: {cls.COLORS['secondary']};
    font-weight: 600;
    box-shadow: 0 0 15px {cls.COLORS['secondary']}20;
}}

QPushButton[theme="secondary"]:hover {{
    background-color: {cls.COLORS['secondary']};
    color: {cls.COLORS['text_primary']};
    box-shadow: 
        0 0 25px {cls.COLORS['secondary']},
        0 0 50px {cls.COLORS['secondary']}40;
}}

/* Accent button */
QPushButton[theme="accent"] {{
    background: linear-gradient(135deg, {cls.COLORS['accent']}, {cls.COLORS['accent_light']});
    border: none;
    color: {cls.COLORS['text_primary']};
    font-weight: 700;
    box-shadow: 
        0 0 25px {cls.COLORS['accent']},
        0 8px 32px {cls.COLORS['accent']}30;
}}

/* =====================
   CARDS & CONTAINERS
   ===================== */

QFrame#card, QGroupBox {{
    background-color: {cls.COLORS['bg_surface']};
    border: 2px solid {cls.COLORS['border_medium']};
    border-top: 4px solid {cls.COLORS['primary']};
    border-radius: 16px;
    padding: 20px;
    margin-bottom: 16px;
    box-shadow: 
        0 4px 20px rgba(0, 0, 0, 0.3),
        0 0 30px {cls.COLORS['primary']}05;
}}

QFrame#card:hover {{
    border-color: {cls.COLORS['primary']};
    box-shadow: 
        0 8px 32px rgba(0, 0, 0, 0.4),
        0 0 40px {cls.COLORS['primary']}10;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 16px;
    padding: 0 12px;
    color: {cls.COLORS['primary']};
    font-weight: 600;
    font-size: 14px;
    background-color: {cls.COLORS['bg_surface']};
}}

/* =====================
   LABELS & TEXT
   ===================== */

QLabel {{
    color: {cls.COLORS['text_primary']};
    font-size: 14px;
    background: transparent;
}}

QLabel[theme="title"] {{
    font-size: 28px;
    font-weight: 700;
    background: linear-gradient(135deg, {cls.COLORS['primary']}, {cls.COLORS['secondary']});
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    text-shadow: 0 0 20px {cls.COLORS['primary']}30;
}}

QLabel[theme="subtitle"] {{
    font-size: 16px;
    font-weight: 500;
    color: {cls.COLORS['text_secondary']};
}}

QLabel[theme="muted"] {{
    color: {cls.COLORS['text_muted']};
    font-size: 12px;
}}

QLabel[theme="success"] {{
    color: {cls.COLORS['success_glow']};
    text-shadow: 0 0 10px {cls.COLORS['success']}30;
}}

QLabel[theme="warning"] {{
    color: {cls.COLORS['warning_glow']};
    text-shadow: 0 0 10px {cls.COLORS['warning']}30;
}}

QLabel[theme="error"] {{
    color: {cls.COLORS['error_glow']};
    text-shadow: 0 0 10px {cls.COLORS['error']}30;
}}

/* =====================
   INPUT FIELDS
   ===================== */

QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {cls.COLORS['bg_elevated']};
    border: 2px solid {cls.COLORS['border_light']};
    border-radius: 8px;
    padding: 10px 14px;
    color: {cls.COLORS['text_primary']};
    font-size: 14px;
    selection-background-color: {cls.COLORS['primary']};
    selection-color: {cls.COLORS['bg_primary']};
}}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border: 2px solid {cls.COLORS['primary']};
    box-shadow: 0 0 15px {cls.COLORS['primary']}30;
    outline: none;
}}

QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled {{
    background-color: {cls.COLORS['bg_surface']};
    border-color: {cls.COLORS['text_disabled']};
    color: {cls.COLORS['text_disabled']};
}}

QLineEdit::placeholder, QTextEdit::placeholder {{
    color: {cls.COLORS['text_disabled']};
    opacity: 0.6;
}}

/* =====================
   CHECKBOXES & RADIO
   ===================== */

QCheckBox, QRadioButton {{
    spacing: 8px;
    color: {cls.COLORS['text_primary']};
    font-size: 14px;
}}

QCheckBox::indicator, QRadioButton::indicator {{
    width: 20px;
    height: 20px;
    border: 2px solid {cls.COLORS['primary']};
    border-radius: 4px;
    background-color: {cls.COLORS['bg_elevated']};
}}

QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
    border-color: {cls.COLORS['primary_light']};
    box-shadow: 0 0 10px {cls.COLORS['primary']}30;
}}

QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background-color: {cls.COLORS['primary']};
    border-color: {cls.COLORS['primary']};
    image: none;
    box-shadow: 0 0 15px {cls.COLORS['primary']};
}}

QRadioButton::indicator {{
    border-radius: 10px;
}}

QRadioButton::indicator:checked {{
    border-radius: 10px;
    background-color: {cls.COLORS['primary']};
}}

/* =====================
   COMBOBOX & DROPDOWN
   ===================== */

QComboBox {{
    background-color: {cls.COLORS['bg_elevated']};
    border: 2px solid {cls.COLORS['border_light']};
    border-radius: 8px;
    padding: 8px 12px;
    color: {cls.COLORS['text_primary']};
    min-height: 36px;
}}

QComboBox:hover {{
    border-color: {cls.COLORS['primary_light']};
}}

QComboBox:focus {{
    border-color: {cls.COLORS['primary']};
    box-shadow: 0 0 15px {cls.COLORS['primary']}30;
}}

QComboBox::drop-down {{
    border: none;
    width: 36px;
}}

QComboBox::down-arrow {{
    width: 16px;
    height: 16px;
    image: none;
    border-left: 5px solid {cls.COLORS['primary']};
    border-top: 5px solid transparent;
    border-bottom: 5px solid transparent;
    right: 8px;
}}

QComboBox QAbstractItemView {{
    background-color: {cls.COLORS['bg_surface']};
    border: 1px solid {cls.COLORS['border_medium']};
    border-radius: 8px;
    selection-background-color: {cls.COLORS['primary']};
    selection-color: {cls.COLORS['bg_primary']};
    color: {cls.COLORS['text_primary']};
    padding: 4px;
}}

QComboBox QAbstractItemView::item {{
    padding: 8px 12px;
    border-radius: 4px;
    margin: 2px 4px;
}}

QComboBox QAbstractItemView::item:selected {{
    background-color: {cls.COLORS['primary']};
    box-shadow: 0 0 10px {cls.COLORS['primary']};
}}

/* =====================
   SLIDERS & PROGRESS
   ===================== */

QSlider::groove:horizontal {{
    height: 8px;
    background: {cls.COLORS['bg_elevated']};
    border-radius: 4px;
}}

QSlider::handle:horizontal {{
    width: 20px;
    height: 20px;
    margin: -6px 0;
    background: {cls.COLORS['primary']};
    border-radius: 10px;
    box-shadow: 0 0 15px {cls.COLORS['primary']};
}}

QSlider::handle:horizontal:hover {{
    background: {cls.COLORS['primary_light']};
    box-shadow: 0 0 20px {cls.COLORS['primary_light']};
}}

QProgressBar {{
    background-color: {cls.COLORS['bg_elevated']};
    border: none;
    border-radius: 6px;
    height: 10px;
    text-align: center;
    color: {cls.COLORS['text_primary']};
}}

QProgressBar::chunk {{
    background: linear-gradient(90deg, {cls.COLORS['primary']}, {cls.COLORS['primary_light']});
    border-radius: 6px;
    box-shadow: 0 0 15px {cls.COLORS['primary']};
    animation: progress-glow 2s ease-in-out infinite;
}}

@keyframes progress-glow {{
    0%, 100% {{ opacity: 1; }}
    50% {{ opacity: 0.7; }}
}}

/* =====================
   TABS & NAVIGATION
   ===================== */

QTabWidget::pane {{
    background-color: {cls.COLORS['bg_surface']};
    border: 2px solid {cls.COLORS['border_medium']};
    border-radius: 12px;
    padding: 16px;
}}

QTabBar::tab {{
    background-color: transparent;
    color: {cls.COLORS['text_muted']};
    padding: 12px 24px;
    margin-right: 4px;
    border: 2px solid transparent;
    border-bottom: 2px solid {cls.COLORS['border_light']};
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    font-weight: 500;
    transition: all 0.3s ease;
}}

QTabBar::tab:hover {{
    color: {cls.COLORS['primary']};
    border-color: {cls.COLORS['primary']}40;
}}

QTabBar::tab:selected {{
    background-color: {cls.COLORS['bg_elevated']};
    color: {cls.COLORS['primary']};
    border-color: {cls.COLORS['primary']};
    border-bottom: 2px solid {cls.COLORS['bg_surface']};
    box-shadow: 0 -4px 16px {cls.COLORS['primary']}20;
    font-weight: 600;
}}

QTabBar::tab:!selected {{
    margin-top: 2px;
}}

/* =====================
   SCROLLBARS
   ===================== */

QScrollBar:vertical {{
    background-color: {cls.COLORS['bg_surface']};
    width: 10px;
    border-radius: 5px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background-color: {cls.COLORS['border_medium']};
    border-radius: 5px;
    min-height: 30px;
    margin: 2px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {cls.COLORS['primary']};
    box-shadow: 0 0 10px {cls.COLORS['primary']};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    background-color: {cls.COLORS['bg_surface']};
    height: 10px;
    border-radius: 5px;
    margin: 0;
}}

QScrollBar::handle:horizontal {{
    background-color: {cls.COLORS['border_medium']};
    border-radius: 5px;
    min-width: 30px;
    margin: 2px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {cls.COLORS['primary']};
    box-shadow: 0 0 10px {cls.COLORS['primary']};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

/* =====================
   TABLES & TREES
   ===================== */

QTableView, QTreeview, QListView {{
    background-color: {cls.COLORS['bg_elevated']};
    border: 1px solid {cls.COLORS['border_light']};
    border-radius: 8px;
    color: {cls.COLORS['text_primary']};
    gridline-color: {cls.COLORS['border_light']};
}}

QTableView::item, QTreeview::item, QListView::item {{
    padding: 8px;
    border-bottom: 1px solid {cls.COLORS['border_light']};
}}

QTableView::item:selected, QTreeview::item:selected, QListView::item:selected {{
    background-color: {cls.COLORS['primary']};
    color: {cls.COLORS['bg_primary']};
    box-shadow: 0 0 10px {cls.COLORS['primary']};
}}

QHeaderView::section {{
    background-color: {cls.COLORS['bg_surface']};
    color: {cls.COLORS['primary']};
    padding: 10px;
    border: none;
    border-bottom: 2px solid {cls.COLORS['border_medium']};
    font-weight: 600;
    text-transform: uppercase;
    font-size: 11px;
    letter-spacing: 0.5px;
}}

/* =====================
   SPINBOX & NUMBER
   ===================== */

QSpinBox, QDoubleSpinBox {{
    background-color: {cls.COLORS['bg_elevated']};
    border: 2px solid {cls.COLORS['border_light']};
    border-radius: 8px;
    padding: 6px 10px;
    color: {cls.COLORS['text_primary']};
    min-height: 36px;
}}

QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {cls.COLORS['primary']};
    box-shadow: 0 0 15px {cls.COLORS['primary']}30;
}}

QSpinBox::up-button, QDoubleSpinBox::up-button {{
    width: 24px;
    background-color: {cls.COLORS['bg_surface']};
    border-left: 1px solid {cls.COLORS['border_light']};
}}

QSpinBox::down-button, QDoubleSpinBox::down-button {{
    width: 24px;
    background-color: {cls.COLORS['bg_surface']};
    border-left: 1px solid {cls.COLORS['border_light']};
}}

/* =====================
   STATUS BAR
   ===================== */

QStatusBar {{
    background-color: {cls.COLORS['bg_surface']};
    color: {cls.COLORS['text_muted']};
    border-top: 1px solid {cls.COLORS['border_medium']};
    padding: 6px;
}}

QStatusBar::item {{
    border: none;
}}

/* =====================
   TOOLTIPS
   ===================== */

QToolTip {{
    background-color: {cls.COLORS['bg_elevated']};
    color: {cls.COLORS['text_primary']};
    border: 1px solid {cls.COLORS['primary']};
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 12px;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
}}

/* =====================
   DIALOGS & MESSAGES
   ===================== */

QMessageBox {{
    background-color: {cls.COLORS['bg_surface']};
    color: {cls.COLORS['text_primary']};
}}

QMessageBox QLabel {{
    color: {cls.COLORS['text_primary']};
    font-size: 14px;
}}

QMessageBox QPushButton {{
    min-width: 100px;
}}

/* =====================
   SPLASH SCREEN
   ===================== */

QSplashScreen {{
    background: linear-gradient(135deg, {cls.COLORS['bg_primary']}, {cls.COLORS['bg_surface']});
}}

QSplashScreen QLabel {{
    background: linear-gradient(135deg, {cls.COLORS['primary']}, {cls.COLORS['secondary']});
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    font-size: 24px;
    font-weight: 700;
}}
        """
