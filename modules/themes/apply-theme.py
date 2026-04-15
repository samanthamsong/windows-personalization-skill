"""
Theme Engine — apply a full desktop + RGB theme from a single JSON spec.

This is the orchestrator CLI. It receives a theme spec from the Copilot agent
and coordinates wallpaper, desktop styling, and DL lighting changes.

Usage:
    python apply-theme.py --spec '{"name":"shrek","wallpaper_url":"...","accent_color":"#4A7C2E",...}'
    python apply-theme.py --check          # check available capabilities
    python apply-theme.py --stop-lighting  # stop running theme lighting

Theme Spec Format:
    {
        "name": "shrek",
        "wallpaper_url": "https://example.com/shrek.jpg",     # direct URL (preferred)
        "wallpaper_search": "shrek ogre swamp wallpaper",     # Unsplash fallback
        "accent_color": "#4A7C2E",
        "mode": "dark",                    # "dark" or "light"
        "taskbar_accent": true,            # show accent on taskbar
        "transparency": true,              # enable transparency
        "dl_palette": ["#4A7C2E","#8B6914","#2D5016"],  # RGB lighting colors
        "dl_style": "wave"                 # wave|breathe|shimmer|static|pulse
    }

All fields are optional — the tool applies what it can and skips the rest.
"""

import argparse
import json
import os
import subprocess
import sys

# Import handlers from same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from desktop_handler import apply_desktop, check_capability as check_desktop
from wallpaper_handler import apply_wallpaper, check_capability as check_wallpaper
from lighting_handler import check_capability as check_lighting, stop_existing as stop_lighting


def _hex_to_color_name(hex_color: str) -> str:
    """Convert a hex color to the closest human-friendly color name."""
    if not hex_color or not hex_color.startswith('#') or len(hex_color) < 7:
        return hex_color
    h = hex_color.lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    # Named color reference table (name, R, G, B)
    named = [
        ("red", 255, 0, 0), ("crimson", 220, 20, 60), ("dark red", 139, 0, 0),
        ("orange", 255, 165, 0), ("burnt orange", 204, 85, 0),
        ("deep orange", 224, 112, 32),
        ("gold", 255, 215, 0), ("yellow", 255, 255, 0), ("amber", 255, 191, 0),
        ("lime green", 50, 205, 50), ("green", 0, 128, 0), ("emerald", 80, 200, 120),
        ("forest green", 34, 139, 34), ("dark green", 0, 100, 0),
        ("olive", 128, 128, 0), ("sage", 188, 184, 138),
        ("mint", 152, 255, 152), ("soft green", 180, 220, 170),
        ("teal", 0, 128, 128), ("cyan", 0, 255, 255), ("aqua", 127, 255, 212),
        ("sky blue", 135, 206, 235), ("light blue", 173, 216, 230),
        ("blue", 0, 0, 255), ("royal blue", 65, 105, 225),
        ("navy", 0, 0, 128), ("steel blue", 70, 130, 180),
        ("purple", 128, 0, 128), ("violet", 238, 130, 238),
        ("lavender", 200, 162, 200), ("indigo", 75, 0, 130),
        ("magenta", 255, 0, 255), ("pink", 255, 182, 193),
        ("hot pink", 255, 105, 180), ("rose", 255, 0, 127),
        ("coral", 255, 127, 80), ("salmon", 250, 128, 114),
        ("peach", 255, 218, 185), ("cream", 255, 253, 208),
        ("ivory", 255, 255, 240), ("beige", 245, 245, 220),
        ("tan", 210, 180, 140), ("brown", 139, 69, 19),
        ("chocolate", 210, 105, 30), ("maroon", 128, 0, 0),
        ("white", 255, 255, 255), ("silver", 192, 192, 192),
        ("gray", 128, 128, 128), ("charcoal", 54, 69, 79),
        ("black", 0, 0, 0),
    ]

    best_name = hex_color
    best_dist = float('inf')
    for name, nr, ng, nb in named:
        dist = (r - nr) ** 2 + (g - ng) ** 2 + (b - nb) ** 2
        if dist < best_dist:
            best_dist = dist
            best_name = name

    return best_name


def check_capabilities() -> dict:
    """Check which theming capabilities are available."""
    caps = {
        "desktop_styling": check_desktop(),
        "wallpaper": check_wallpaper(),
        "dynamic_lighting": check_lighting(),
    }
    return caps


def apply_theme(spec: dict) -> dict:
    """Apply a full theme from a spec dict.

    Returns a summary dict with results for each component.
    """
    name = spec.get("name", "custom theme")
    results = {"name": name, "components": {}}

    print(f"🎨 Applying theme: {name}")
    print(f"{'=' * 40}")

    # Kill any existing lighting effects (shooting-stars, koi-fish, etc.)
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             'Get-Process -Name DynamicLightingDriver -ErrorAction SilentlyContinue | '
             'ForEach-Object { Stop-Process -Id $_.Id -Force }'],
            capture_output=True, text=True, timeout=5
        )
    except Exception:
        pass

    # 1. Wallpaper
    wallpaper_url = spec.get("wallpaper_url")
    wallpaper_search = spec.get("wallpaper_search")
    if wallpaper_url or wallpaper_search:
        print(f"\n🖼️  Wallpaper...")
        result = apply_wallpaper(url=wallpaper_url, search_query=wallpaper_search)
        results["components"]["wallpaper"] = result
        icon = "✅" if result["success"] else "❌"
        print(f"   {icon} {result['message']}")
    else:
        results["components"]["wallpaper"] = {
            "success": None, "message": "No wallpaper specified"
        }
        print(f"\n🖼️  Wallpaper: skipped (not specified)")

    # 2. Desktop styling (accent, mode, taskbar, transparency)
    accent = spec.get("accent_color")
    if accent:
        print(f"\n🎨 Desktop styling...")
        if check_desktop():
            mode = spec.get("mode", "dark")
            taskbar = spec.get("taskbar_accent", True)
            transparency = spec.get("transparency", True)
            result = apply_desktop(accent, mode, taskbar, transparency)
            results["components"]["desktop"] = result
            icon = "✅" if result["success"] else "❌"
            print(f"   {icon} {result['message']}")
        else:
            results["components"]["desktop"] = {
                "success": False, "message": "Registry write not available"
            }
            print(f"   ⚠️  Skipped — registry write not available")
    else:
        results["components"]["desktop"] = {
            "success": None, "message": "No accent color specified"
        }
        print(f"\n🎨 Desktop styling: skipped (no accent color)")

    # 3. Dynamic Lighting
    dl_palette = spec.get("dl_palette")
    if dl_palette and len(dl_palette) > 0:
        print(f"\n🔆 RGB lighting...")
        if check_lighting():
            dl_style = spec.get("dl_style", "wave")
            palette_arg = ",".join(dl_palette)

            # Launch lighting via PowerShell Start-Process so it's fully detached
            lighting_script = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "lighting_handler.py"
            )
            try:
                # Stop any existing lighting first
                stop_lighting()

                # Use Start-Process to launch a fully independent process
                # Python runs hidden; the DL driver creates its own foreground window
                ps_cmd = (
                    f'$env:PYTHONIOENCODING = "utf-8"; '
                    f'Start-Process -FilePath "{sys.executable}" '
                    f'-ArgumentList @("{lighting_script}", "--palette", "{palette_arg}", "--style", "{dl_style}") '
                    f'-WindowStyle Hidden'
                )
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                    capture_output=True, text=True, timeout=10
                )

                # Wait briefly for startup
                import time
                time.sleep(3)

                # Check if the PID file was created (indicates successful start)
                pid_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        '.theme-lighting.pid')
                if os.path.exists(pid_file):
                    with open(pid_file) as f:
                        pid = f.read().strip()
                    colors_str = ', '.join(dl_palette[:3])
                    results["components"]["lighting"] = {
                        "success": True,
                        "message": f"{dl_style.capitalize()} effect running ({colors_str})",
                        "pid": int(pid)
                    }
                    print(f"   ✅ {dl_style.capitalize()} effect started (PID {pid})")
                else:
                    results["components"]["lighting"] = {
                        "success": False,
                        "message": "Lighting process started but no PID file created"
                    }
                    print(f"   ❌ Lighting failed to initialize")
            except Exception as e:
                results["components"]["lighting"] = {
                    "success": False, "message": f"Failed to start lighting: {e}"
                }
                print(f"   ❌ {e}")
            except Exception as e:
                results["components"]["lighting"] = {
                    "success": False, "message": f"Failed to start lighting: {e}"
                }
                print(f"   ❌ {e}")
        else:
            results["components"]["lighting"] = {
                "success": False, "message": "DL driver not found"
            }
            print(f"   ⚠️  Skipped — DL driver not built or not found")
    else:
        results["components"]["lighting"] = {
            "success": None, "message": "No DL palette specified"
        }
        print(f"\n🔆 RGB lighting: skipped (no palette)")

    # Summary
    print(f"\n{'=' * 40}")
    successes = sum(1 for c in results["components"].values()
                    if c.get("success") is True)
    skipped = sum(1 for c in results["components"].values()
                  if c.get("success") is None)
    failed = sum(1 for c in results["components"].values()
                 if c.get("success") is False)
    total = len(results["components"])
    print(f"✨ Theme '{name}': {successes}/{total} applied, "
          f"{skipped} skipped, {failed} failed")

    # Human-readable "what changed" summary for the agent to relay
    print(f"\nWhat changed:")
    wp = results["components"].get("wallpaper", {})
    if wp.get("success"):
        print(f"  🖼️  Wallpaper → themed image ({wp['message']})")
    desk = results["components"].get("desktop", {})
    if desk.get("success"):
        mode_str = spec.get("mode", "dark").capitalize()
        color_name = _hex_to_color_name(spec.get("accent_color", ""))
        print(f"  🎨 Accent color → {color_name}")
        print(f"  {'☀️' if mode_str == 'Light' else '🌙'} Mode → {mode_str}")
        if spec.get("taskbar_accent"):
            print(f"  📌 Taskbar → {color_name}")
        else:
            print(f"  📌 Taskbar → default (no accent)")
        print(f"  ✨ Title bars → {color_name}")
    lt = results["components"].get("lighting", {})
    if lt.get("success"):
        style = spec.get("dl_style", "wave").capitalize()
        palette_names = [_hex_to_color_name(c) for c in spec.get("dl_palette", [])]
        print(f"  🔆 RGB devices → {style} effect ({', '.join(palette_names)})")
    
    # Report what didn't work
    for key, comp in results["components"].items():
        if comp.get("success") is False:
            print(f"  ⚠️  {key} → failed: {comp['message']}")

    results["summary"] = {
        "applied": successes, "skipped": skipped, "failed": failed
    }
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Apply a full desktop + RGB theme from a JSON spec"
    )
    parser.add_argument("--spec", type=str,
                        help="Theme spec as JSON string")
    parser.add_argument("--spec-file", type=str,
                        help="Path to theme spec JSON file")
    parser.add_argument("--check", action="store_true",
                        help="Check available capabilities")
    parser.add_argument("--stop-lighting", action="store_true",
                        help="Stop running theme lighting effect")
    args = parser.parse_args()

    if args.check:
        caps = check_capabilities()
        print("🔍 Capability check:")
        for cap, available in caps.items():
            icon = "✅" if available else "❌"
            print(f"   {icon} {cap}")
        return

    if args.stop_lighting:
        stop_lighting()
        print("✅ Theme lighting stopped")
        return

    if args.spec:
        spec = json.loads(args.spec)
    elif args.spec_file:
        with open(args.spec_file, 'r') as f:
            spec = json.load(f)
    else:
        parser.print_help()
        return

    results = apply_theme(spec)
    # Output results as JSON for agent consumption
    print(f"\n__RESULT_JSON__:{json.dumps(results)}")


if __name__ == "__main__":
    main()
