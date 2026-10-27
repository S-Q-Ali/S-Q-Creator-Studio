"""Test script to verify neon theme is applied correctly.

This script launches the S-Q Creator Studio app in headless mode,
takes screenshots, and verifies that the neon theme styles are applied.
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

# Import the app components
from s_q_ali_media_downloader.ui.main_window import MainWindow


def capture_screenshot(window, filename: str):
    """Capture screenshot of the window."""
    # Create pixmap from window
    pixmap = window.grab()
    
    # Save screenshot
    screenshot_path = Path(__file__).parent.parent / "screenshots" / filename
    screenshot_path.parent.mkdir(exist_ok=True)
    pixmap.save(str(screenshot_path), "PNG")
    
    print(f"[OK] Captured: {screenshot_path}")
    return screenshot_path


def verify_neon_theme(window) -> dict:
    """Verify that neon theme is applied by checking stylesheet."""
    stylesheet = window.styleSheet()
    
    verification = {
        "stylesheet_present": bool(stylesheet),
        "dark_background": "#0a0a0a" in stylesheet if stylesheet else False,
        "electric_blue": "#00d4ff" in stylesheet if stylesheet else False,
        "glow_effects": "box-shadow" in stylesheet if stylesheet else False,
        "gradient_buttons": "linear-gradient" in stylesheet if stylesheet else False,
        "neon_colors": {
            "primary": "#00d4ff" in stylesheet if stylesheet else False,
            "secondary": "#7c3aed" in stylesheet if stylesheet else False,
            "accent": "#ec4899" in stylesheet if stylesheet else False,
        },
        "status_colors": {
            "success": "#10b981" in stylesheet if stylesheet else False,
            "warning": "#f59e0b" in stylesheet if stylesheet else False,
            "error": "#ef4444" in stylesheet if stylesheet else False,
        },
    }
    
    return verification


def run_theme_tests():
    """Run complete neon theme verification."""
    print("=" * 70)
    print("S-Q Creator Studio - Neon Theme Verification")
    print("=" * 70)
    
    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("S-Q Creator Studio - Test")
    
    # Apply neon theme manually (since we're not using app.py main)
    from s_q_ali_media_downloader.ui.themes import apply_neon_theme
    apply_neon_theme(app)
    
    print("\n[OK] Neon theme applied to application")
    
    # Create main window (with error handling)
    try:
        window = MainWindow()
    except Exception as e:
        print(f"\n[WARN] MainWindow creation error: {e}")
        print("   Continuing with verification anyway...")
        window = None
    
    print("\nTEST RESULTS:\n")
    
    # 1. Check if window created successfully
    print("1. Window Creation:")
    if window:
        print("   [OK] MainWindow created successfully")
        try:
            window.show()
        except Exception:
            pass
    else:
        print("   [WARN] Failed to create window")
    
    # 2. Verify neon theme stylesheet
    print("\n2. Neon Theme Verification:")
    verification = verify_neon_theme(window)
    
    for key, value in verification.items():
        if key in ["neon_colors", "status_colors"]:
            print(f"\n   {key.upper()}:")
            for color, present in value.items():
                status = "[OK]" if present else "[FAIL]"
                print(f"      {status} {color}: {'Applied' if present else 'Missing'}")
        else:
            status = "[OK]" if value else "[FAIL]"
            print(f"   {status} {key}: {'Present' if value else 'Missing'}")
    
    # 3. Capture screenshots
    print("\n3. Screenshots:")
    
    def safe_capture_screenshot():
        try:
            if window and window.isVisible():
                capture_screenshot(window, "main_window.png")
        except Exception as e:
            print(f"[WARN] Screenshot capture error: {e}")
    
    # Screenshot 1: Main window overview
    QTimer.singleShot(500, safe_capture_screenshot)
    
    # Screenshot 2: Settings tab (if available)
    QTimer.singleShot(1000, safe_capture_screenshot)
    
    # Close after 2 seconds
    QTimer.singleShot(2000, app.quit)
    
    # Run event loop with timeout
    try:
        app.exec()
    except Exception:
        pass
    
    # 4. Summary
    print("\n" + "=" * 70)
    print("SUMMARY:")
    print("=" * 70)
    
    all_checks = [
        verification.get("stylesheet_present", False),
        verification.get("dark_background", False),
        verification.get("electric_blue", False),
        verification.get("glow_effects", False),
        verification.get("gradient_buttons", False),
    ]
    
    # Check all neon colors
    all_colors = all(verification.get("neon_colors", {}).values())
    all_status = all(verification.get("status_colors", {}).values())
    
    if all(all_checks) and all_colors and all_status:
        print("[SUCCESS] NEON THEME VERIFIED SUCCESSFULLY!")
        print("\nAll neon theme components are applied:")
        print("  - Dark background (#0a0a0a)")
        print("  - Electric blue accents (#00d4ff)")
        print("  - Neon glow effects")
        print("  - Gradient buttons")
        print("  - Status color coding")
        print("\nScreenshots saved to: screenshots/")
        return True
    else:
        print("[PARTIAL] NEON THEME PARTIALLY APPLIED")
        print("\nMissing components:")
        if not verification.get("stylesheet_present", False):
            print("  - Main stylesheet")
        if not verification.get("dark_background", False):
            print("  - Dark background")
        if not verification.get("electric_blue", False):
            print("  - Electric blue accent")
        if not verification.get("glow_effects", False):
            print("  - Glow effects")
        if not verification.get("gradient_buttons", False):
            print("  - Gradient buttons")
        if not all_colors:
            print("  - Some neon colors missing")
        if not all_status:
            print("  - Some status colors missing")
        return False


if __name__ == "__main__":
    success = run_theme_tests()
    sys.exit(0 if success else 1)
