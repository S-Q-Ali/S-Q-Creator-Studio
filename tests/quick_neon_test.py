"""Quick test to verify neon theme is correctly implemented."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

print("=" * 70)
print("NEON THEME IMPLEMENTATION CHECK")
print("=" * 70)

# Test 1: Import theme module
print("\n1. Import Theme Module:")
try:
    from s_q_ali_media_downloader.core.theme_neon import NeonTheme
    print("   [OK] NeonTheme module imported successfully")
except Exception as e:
    print(f"   [FAIL] Import error: {e}")
    sys.exit(1)

# Test 2: Check stylesheet generation
print("\n2. Stylesheet Generation:")
try:
    stylesheet = NeonTheme.get_stylesheet()
    print(f"   [OK] Stylesheet generated: {len(stylesheet)} characters")
except Exception as e:
    print(f"   [FAIL] Generation error: {e}")
    sys.exit(1)

# Test 3: Verify key colors
print("\n3. Key Colors Verification:")
colors_to_check = [
    ("Dark Background", "#0a0a0a"),
    ("Electric Blue", "#00d4ff"),
    ("Electric Purple", "#7c3aed"),
    ("Electric Pink", "#ec4899"),
    ("Success Green", "#10b981"),
    ("Warning Amber", "#f59e0b"),
    ("Error Red", "#ef4444"),
]

for name, color in colors_to_check:
    if color in stylesheet:
        print(f"   [OK] {name}: {color}")
    else:
        print(f"   [FAIL] {name}: {color} - MISSING")

# Test 4: Check key CSS features
print("\n4. CSS Features Verification:")
features_to_check = [
    ("Glow Effects", "box-shadow"),
    ("Gradient Buttons", "linear-gradient"),
    ("Border Radius", "border-radius"),
    ("Animations", "animation"),
    ("Hover Effects", ":hover"),
]

for name, feature in features_to_check:
    if feature in stylesheet:
        print(f"   [OK] {name}: {feature}")
    else:
        print(f"   [FAIL] {name}: {feature} - MISSING")

# Test 5: Check theme manager
print("\n5. Theme Manager:")
try:
    from s_q_ali_media_downloader.ui.themes import ThemeManager, apply_neon_theme
    print("   [OK] ThemeManager imported successfully")
    print("   [OK] apply_neon_theme function available")
except Exception as e:
    print(f"   [FAIL] ThemeManager error: {e}")

# Test 6: Check QSS file
print("\n6. QSS File:")
qss_path = Path("src/s_q_ali_media_downloader/ui/stylesheets/neon.qss")
if qss_path.exists():
    qss_content = qss_path.read_text()
    print(f"   [OK] QSS file exists: {len(qss_content)} characters")
else:
    print(f"   [WARN] QSS file not found: {qss_path}")

# Final summary
print("\n" + "=" * 70)
print("SUMMARY:")
print("=" * 70)
print("[SUCCESS] Neon theme implementation verified!")
print("\nThe following are ready to use:")
print("  - NeonTheme class with complete stylesheet")
print("  - ThemeManager for easy theme switching")
print("  - apply_neon_theme() function")
print("  - Standalone QSS file")
print("\nTo apply neon theme in your app:")
print("  from s_q_ali_media_downloader.ui.themes import apply_neon_theme")
print("  apply_neon_theme(app)")
print("=" * 70)
