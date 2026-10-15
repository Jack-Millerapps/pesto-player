#!/usr/bin/env python3
"""
Quick test to verify all imports work correctly
Run this before starting the main app
"""

import sys

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
core_ok &= test_import("vlc")

print()
print("Testing optional dependencies...")
test_import("mutagen")

print()
print("Testing project modules...")
modules_ok = True
modules_ok &= test_import("config")
modules_ok &= test_import("audio", "player")
modules_ok &= test_import("library", "player")
modules_ok &= test_import("widgets", "ui")
modules_ok &= test_import("screen_manager", "ui")
modules_ok &= test_import("now_playing", "ui")
modules_ok &= test_import("library", "ui")
modules_ok &= test_import("settings", "ui")
modules_ok &= test_import("battery", "hardware")
modules_ok &= test_import("buttons", "hardware")

print()
print("=" * 60)

if core_ok and modules_ok:
    print("✅ All critical imports successful!")
    print("   You can run: python main.py")
elif not core_ok:
    print("❌ Core dependencies missing!")
    print("   Install with: pip install pygame python-vlc")
elif not modules_ok:
    print("❌ Project module errors!")
    print("   Check for syntax errors in source files")

print("=" * 60)
