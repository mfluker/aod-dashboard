#!/usr/bin/env python3
"""
Quick script to check Canvas cookie status
"""
import sys
from pathlib import Path

# Add the updater directory to the path
sys.path.insert(0, str(Path(__file__).parent / "updater"))

from data_fetcher import validate_canvas_cookies

def main():
    print("=" * 60)
    print("CANVAS COOKIE VALIDATOR")
    print("=" * 60)

    cookie_path = Path(__file__).parent / "updater" / "canvas_cookies.json"
    print(f"\nChecking: {cookie_path}")

    if not cookie_path.exists():
        print("\n❌ Cookie file not found!")
        print(f"   Expected location: {cookie_path}")
        print("\n📝 To fix:")
        print("   1. Log into Canvas in Chrome")
        print("   2. Export cookies using Cookie-Editor extension")
        print("   3. Save as canvas_cookies.json")
        print(f"   4. Place at: {cookie_path}")
        return

    is_valid, message = validate_canvas_cookies(str(cookie_path))

    print(f"\n{'✅' if is_valid else '❌'} Status: {message}")

    if is_valid:
        print("\n🎉 You're good to go! Cookies are valid.")
        print("   You can proceed with data fetching.")
    else:
        print("\n⚠️  Action Required:")
        print("   Your Canvas cookies need to be refreshed.")
        print("\n📝 Steps to refresh:")
        print("   1. Open https://canvas.artofdrawers.com in Chrome")
        print("   2. Log in to your account")
        print("   3. Click Cookie-Editor extension")
        print("   4. Keep only PHPSESSID and username cookies")
        print("   5. Click Export")
        print("   6. Save as canvas_cookies.json")
        print(f"   7. Replace file at: {cookie_path}")

    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
