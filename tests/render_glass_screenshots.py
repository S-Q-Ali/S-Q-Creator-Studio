"""Render the real MainWindow on the glass sheet and write the proof shots.

Two outputs. ``screenshots/`` keeps the pictures the README shows - one per
workspace page, plus the agent tab's third mode and the compact layout. The
review grid goes to a scratch directory, because the repo has no business
carrying forty PNGs.

The report prints what was measured and nothing else: geometry, the colours
that dominate each shot, the contrast of the pairs the sheet paints. It never
says a screen looks right - that judgement belongs to whoever opens the app.
"""

import os
import sys
import tempfile
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

# A render must not read this machine's settings: a download folder printed in
# a shipped screenshot is somebody's path.
_SANDBOX = tempfile.mkdtemp(prefix="sq-glass-render-")
for _var in ("APPDATA", "LOCALAPPDATA", "HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME"):
    os.environ[_var] = _SANDBOX
# The env folders do not cover everything. On Windows the preferences live in
# the registry, so a render that only redirected APPDATA would still print the
# real download folder. This is the same hook the test suite uses.
os.environ["SQ_SETTINGS_FILE"] = os.path.join(_SANDBOX, "settings.ini")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication
from test_theme import contrast  # takes the hex strings the palette holds
from test_ui_layout import SIZES

from s_q_ali_media_downloader.theme import C, stylesheet
from s_q_ali_media_downloader.ui.agent_tab import MODE_SOCIAL, MODE_YOUTUBE
from s_q_ali_media_downloader.ui.main_window import MainWindow
from s_q_ali_media_downloader.ui.widgets import Job

#: The workspace pages, by the nav button that shows them and their stack index.
PAGES = {
    "download": ("btn_nav_queue", 0),
    "music": ("btn_nav_music", 1),
    "studio": ("btn_nav_studio", 2),
    "agent": ("btn_nav_agent", 3),
    "social": ("btn_nav_agent", 3),
    "settings": ("btn_nav_settings", 4),
}

#: What the README shows: file -> (page, size, density).
TRACKED = {
    "interface.png": ("download", (1440, 900), "comfortable"),
    "music.png": ("music", (1440, 900), "comfortable"),
    "studio.png": ("studio", (1440, 900), "comfortable"),
    "agent.png": ("agent", (1440, 900), "comfortable"),
    "social-discovery.png": ("social", (1440, 900), "comfortable"),
    "settings.png": ("settings", (1440, 900), "comfortable"),
    "compact.png": ("download", (1280, 720), "compact"),
}

#: Four rows, so the spine is doing its job in every queue shot: waiting,
#: moving, finished and failed, told apart without reading a word. The card
#: badge only knows YouTube and TikTok, so every URL here is one of those two.
SEED = [
    (
        "https://www.tiktok.com/@creator/video/1234567890",
        "60-second morning routine, no cuts",
        "Queued",
        "",
        "",
    ),
    (
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "How I edit a whole video in ten minutes",
        "Started",
        "",
        "",
    ),
    (
        "https://www.youtube.com/watch?v=M7lgCMcTcDw",
        "The full build guide, nothing skipped",
        "Completed",
        "12 MB",
        "",
    ),
    (
        "https://www.tiktok.com/@creator/video/1470863213433064101",
        "Why the last update broke everything",
        "Failed",
        "—",
        "HTTP 403",
    ),
]

#: The rail prints the download folder and the Settings page prints it in
#: full, so a render would otherwise ship this machine's home directory - and
#: whoever's name is in it - in a public screenshot.
FOLDER = "C:/Users/Creator/Downloads/S-Q Creator Studio"


def load_system_fonts():
    """The offscreen platform has no font database; give it this machine's.

    With nothing loaded every glyph in a render is tofu, and a tofu screenshot
    proves nothing about the faces the shipped app finds. Loading the whole
    font folder is what the native platform sees, so the shots match it.
    """
    if QFontDatabase.families():
        return len(QFontDatabase.families())
    folder = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    if not os.path.isdir(folder):
        return 0
    for name in sorted(os.listdir(folder)):
        if name.lower().endswith((".ttf", ".ttc", ".otf")):
            QFontDatabase.addApplicationFont(os.path.join(folder, name))
    return len(QFontDatabase.families())


def pump(app):
    for _ in range(6):
        app.processEvents()


def seed_queue(window):
    for url, title, state, size, error in SEED:
        job = Job(url)
        job.title = title
        window._add_job(job)
        if state == "Started":
            window.on_started(job.uid, None)
            window.on_progress(job.uid, 42.0, "7.7 MB", "1.2 MB/s")
        elif state != "Queued":
            window.on_result(job.uid, state, size, error)


def show(window, page):
    button, index = PAGES[page]
    getattr(window, button).setChecked(True)
    window.workspace_stack.setCurrentIndex(index)
    if page in ("agent", "social"):
        window.agent_tab.mode_combo.setCurrentText(
            MODE_SOCIAL if page == "social" else MODE_YOUTUBE
        )


def set_density(window, compact):
    window.settings_page.compact_check.setChecked(compact)
    window._apply_density()


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
    sampled = sum(counts.values())
    top = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:4]
    blue = sum(n for rgb, n in counts.items() if rgb[2] > 150 and rgb[2] > rgb[0] + 60)
    print(
        f"{name}: {image.width()}x{image.height()} "
        f"window={window.width()}x{window.height()} blue={blue / max(1, sampled):.1%}"
    )
    print("   dominant:", ", ".join(f"#{r:02X}{g:02X}{b:02X}={n}" for (r, g, b), n in top))


def main():
    app = QApplication([])
    print(f"fonts: {load_system_fonts()} families")
    sheet = stylesheet("comfortable")
    app.setStyleSheet(sheet)
    print(f"stylesheet: {len(sheet)} chars, {sheet.count('{')} rule bodies")
    print(
        f"contrast: body text on a panel {contrast(C['text'], C['panel']):.2f}:1, "
        f"checked tab {contrast(C['text'], C['accent_deep']):.2f}:1"
    )

    window = MainWindow()
    window.settings_page.folder_edit.setText(FOLDER)
    window.music_page.folder.setText(FOLDER)
    seed_queue(window)

    review = Path(sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="sq-review-"))
    review.mkdir(parents=True, exist_ok=True)
    print(f"\nreview grid -> {review}")
    for density in ("comfortable", "compact"):
        set_density(window, density == "compact")
        for size in SIZES:
            window.resize(*size)
            for page in PAGES:
                show(window, page)
                save(window, app, f"{density}_{size[0]}x{size[1]}_{page}.png", review)

    print("\ntracked screenshots")
    shots = ROOT / "screenshots"
    shots.mkdir(exist_ok=True)
    for name, (page, size, density) in TRACKED.items():
        set_density(window, density == "compact")
        window.resize(*size)
        show(window, page)
        save(window, app, name, shots)

    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
