"""Verify the neon theme is Qt-valid and survives a density change."""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

print("=" * 70)
print("NEON THEME IMPLEMENTATION CHECK")
print("=" * 70)

print("\n1. Import Theme Module:")
from s_q_ali_media_downloader.core.theme_neon import NeonTheme

print("   [OK] NeonTheme imported")

print("\n2. Stylesheet Generation:")
stylesheet = NeonTheme.get_stylesheet()
print(f"   [OK] {len(stylesheet)} characters")

print("\n3. Key Colors:")
for name, color in [
    ("Dark Background", "#0a0a0a"),
    ("Electric Blue", "#00d4ff"),
    ("Electric Purple", "#7c3aed"),
    ("Electric Pink", "#ec4899"),
    ("Success Green", "#10b981"),
    ("Warning Amber", "#f59e0b"),
    ("Error Red", "#ef4444"),
]:
    print(f"   [{'OK' if color in stylesheet else 'FAIL'}] {name}: {color}")

print("\n4. Qt-Supported Features:")
for name, feature in [
    ("Gradient", "qlineargradient"),
    ("Rounded corners", "border-radius"),
    ("Hover states", ":hover"),
    ("Focus states", ":focus"),
]:
    print(f"   [{'OK' if feature in stylesheet else 'FAIL'}] {name}: {feature}")

print("\n5. Unsupported Web CSS Must Be Absent:")
for feature in ("box-shadow", "text-shadow", "linear-gradient", "animation:"):
    print(f"   [{'OK' if feature not in stylesheet else 'FAIL'}] no {feature}")

print("\n6. Real Glow (Qt drop shadow):")
from s_q_ali_media_downloader.ui import main_window

print(f"   [{'OK' if hasattr(main_window, '_neon_glow') else 'FAIL'}] _neon_glow helper")

print("\n7. Theme Manager:")
from PySide6.QtWidgets import QApplication, QWidget

from s_q_ali_media_downloader.theme import apply_density
from s_q_ali_media_downloader.ui.themes import (
    ThemeManager,
    apply_neon_theme,
)

app = QApplication.instance() or QApplication([])
apply_neon_theme(app)
print(f"   [{'OK' if app.property('s_q_theme') == 'neon' else 'FAIL'}] theme property")

manager = ThemeManager(app)
print(f"   [{'OK' if manager.get_available_themes() else 'FAIL'}] ThemeManager")

print("\n8. Density Change Keeps Neon:")
apply_density(QWidget(), False)
kept = app.property("s_q_theme") == "neon" and "#00d4ff" in app.styleSheet()
print(f"   [{'OK' if kept else 'FAIL'}] theme survives apply_density()")

print("\n" + "=" * 70)
print("DONE")
print("=" * 70)
