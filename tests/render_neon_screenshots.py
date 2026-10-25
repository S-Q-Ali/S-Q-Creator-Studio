"""Render the real MainWindow with the neon theme and capture proof shots."""

import os
import sys
import tempfile
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="sq-neon-test-")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication

from s_q_ali_media_downloader.ui.main_window import MainWindow
from s_q_ali_media_downloader.ui.themes import apply_neon_theme


def load_system_fonts():
    """The offscreen platform has no font database; load Windows' fonts."""
    if QFontDatabase.families():
        return
    folder = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    for name in (
        "segoeui.ttf",
        "segoeuib.ttf",
        "segoeuii.ttf",
        "seguisb.ttf",
        "consola.ttf",
        "seguiemj.ttf",
    ):
        path = os.path.join(folder, name)
        if os.path.isfile(path):
            QFontDatabase.addApplicationFont(path)


def pump(app):
    for _ in range(6):
        app.processEvents()


def save(window, app, name, out_dir):
    pump(app)
    path = out_dir / name
    pixmap = window.grab()
    pixmap.save(str(path), "PNG")
    image = pixmap.toImage()
    counts = {}
    for y in range(0, image.height(), 3):
        for x in range(0, image.width(), 3):
            rgb = image.pixelColor(x, y).getRgb()[:3]
            counts[rgb] = counts.get(rgb, 0) + 1
    top = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:6]
    cyan = sum(n for rgb, n in counts.items() if rgb[2] > 180 and rgb[1] > 150 and rgb[0] < 120)
    print(f"\n{name}: {image.width()}x{image.height()} -> {path}")
    print("  top colors:", ", ".join(f"{rgb}={n}" for rgb, n in top))
    print(f"  cyan-ish pixels: {cyan}")
    return image


def main():
    app = QApplication([])
    load_system_fonts()
    apply_neon_theme(app)
    print("stylesheet chars:", len(app.styleSheet()))
    print("theme property:", app.property("s_q_theme"))

    window = MainWindow()
    window.resize(1568, 1097)
    window.show()
    pump(app)

    out = ROOT / "screenshots"
    out.mkdir(exist_ok=True)
    save(window, app, "neon_portable_queue.png", out)

    window.btn_nav_agent.setChecked(True)
    window.workspace_stack.setCurrentIndex(1)
    save(window, app, "neon_portable_agent.png", out)

    window.btn_nav_settings.setChecked(True)
    window.workspace_stack.setCurrentIndex(2)
    save(window, app, "neon_portable_settings.png", out)

    # The density path used to wipe the theme. It must keep it now.
    window.settings_page.compact_check.setChecked(True)
    window._apply_density()
    pump(app)
    print("\nafter density change, theme property:", app.property("s_q_theme"))
    print("after density change, stylesheet chars:", len(app.styleSheet()))
    assert app.property("s_q_theme") == "neon"
    assert "00d4ff" in app.styleSheet()

    window.close()
    print("\nOK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
