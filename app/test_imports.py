#!/usr/bin/env python3
"""
Quick test to verify all imports work correctly
Run this before starting the main app
"""

def test_import(module_name, package=None):
    """Test if a module can be imported"""
    try:
        if package:
            __import__(f"{package}.{module_name}")
            print(f"✓ {package}.{module_name}")
        else:
            __import__(module_name)
            print(f"✓ {module_name}")
        return True
    except ImportError as e:
        print(f"✗ {package + '.' if package else ''}{module_name} - {e}")
        return False

print("=" * 60)
print("PESTO PLAYER - Import Test")
print("=" * 60)
print()

print("Testing core dependencies...")
core_ok = True
core_ok &= test_import("pygame")
test_import("vlc")  # optional: the app falls back to a simulated player

print()
print("Testing optional dependencies...")
test_import("mutagen")
test_import("flask")
test_import("qrcode")

print()
print("Testing project modules...")
modules_ok = True
modules_ok &= test_import("config")
for m in ("audio", "library", "playlist", "prefs"):
    modules_ok &= test_import(m, "player")
for m in ("widgets", "screen_manager", "text_cache", "theme", "keyboard", "now_playing", "queue",
          "mini_player", "volume_hud", "library", "songs", "artists", "albums", "playlists",
          "search", "settings", "add_music"):
    modules_ok &= test_import(m, "ui")
for m in ("battery", "buttons", "system"):
    modules_ok &= test_import(m, "hardware")
modules_ok &= test_import("main")

print()
print("=" * 60)

if core_ok and modules_ok:
    print("✅ All critical imports successful!")
    print("   You can run: python main.py")
elif not core_ok:
    print("❌ Core dependencies missing!")
    print("   Install with: pip install pygame")
elif not modules_ok:
    print("❌ Project module errors!")
    print("   Check for syntax errors in source files")

print("=" * 60)
