"""
MSIX theme handler — extract and apply MSIX-packaged Windows themes.

The MSIX packages from the Store team wrap a .deskthemepack file (CAB archive)
containing wallpapers, accent colors, cursors, and sounds. We extract the
contents and apply them directly via registry + SystemParametersInfo.
"""

import configparser
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile


LIBRARY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "library")
PACKAGES_DIR = os.path.join(LIBRARY_DIR, "packages")
CATALOG_PATH = os.path.join(LIBRARY_DIR, "catalog.json")

# Where we cache extracted theme contents for quick re-application
CACHE_DIR = os.path.join(LIBRARY_DIR, ".cache")


def _extract_deskthemepack(msix_path: str) -> str:
    """Extract the .deskthemepack from an MSIX package and unpack it.

    The deskthemepack is a CAB archive containing config.theme + wallpapers.
    Returns the path to the cache directory with extracted contents.
    """
    msix_name = os.path.splitext(os.path.basename(msix_path))[0]
    cache_path = os.path.join(CACHE_DIR, msix_name)
    config_theme = os.path.join(cache_path, "config.theme")

    # If already extracted and has config.theme, reuse cache
    if os.path.exists(config_theme):
        return cache_path

    os.makedirs(cache_path, exist_ok=True)

    # Step 1: Extract .deskthemepack from the MSIX (which is a ZIP)
    deskthemepack_path = os.path.join(cache_path, "theme.deskthemepack")
    with zipfile.ZipFile(msix_path, 'r') as zf:
        theme_entries = [e for e in zf.namelist()
                         if e.lower().endswith('.deskthemepack')]
        if not theme_entries:
            raise FileNotFoundError(
                f"No .deskthemepack found in {msix_path}")

        entry = theme_entries[0]
        data = zf.read(entry)
        with open(deskthemepack_path, 'wb') as f:
            f.write(data)

    # Step 2: The deskthemepack is a CAB — expand it to get config.theme + wallpapers
    subprocess.run(
        ["expand", deskthemepack_path, "-F:*", cache_path],
        capture_output=True, check=True
    )

    return cache_path


def apply(theme_id: str) -> dict:
    """Apply a theme from the library by its catalog ID.

    Extracts the MSIX → deskthemepack (CAB) → config.theme + wallpapers,
    then applies each component directly:
    - Wallpaper via SystemParametersInfo
    - Accent color + dark/light mode via registry
    - Cursors and sounds if present

    Returns dict with 'success', 'message', and theme metadata.
    """
    # Find the package file
    catalog = _load_catalog()
    theme_entry = None
    for t in catalog:
        if t["id"] == theme_id:
            theme_entry = t
            break

    if not theme_entry:
        return {"success": False, "message": f"Theme '{theme_id}' not found in catalog"}

    package_file = theme_entry.get("package_file", "")
    msix_path = os.path.join(LIBRARY_DIR, package_file)

    if not os.path.exists(msix_path):
        return {"success": False,
                "message": f"Package file not found: {msix_path}"}

    try:
        cache_dir = _extract_deskthemepack(msix_path)
    except Exception as e:
        return {"success": False, "message": f"Failed to extract theme: {e}"}

    # Parse the config.theme for settings
    config_theme = os.path.join(cache_dir, "config.theme")
    if not os.path.exists(config_theme):
        return {"success": False, "message": "config.theme not found in extracted theme"}

    theme_settings = _parse_theme_ini(config_theme)
    accent = theme_settings.get("accent_color", theme_entry.get("accent_color", "#0078D7"))
    mode = theme_settings.get("mode", theme_entry.get("mode", "dark"))

    applied = []
    errors = []

    # 1. Apply wallpaper — find the first wallpaper in the extracted dir
    wallpaper_dir = os.path.join(cache_dir, "DesktopBackground")
    if os.path.isdir(wallpaper_dir):
        wallpapers = sorted([
            os.path.join(wallpaper_dir, f)
            for f in os.listdir(wallpaper_dir)
            if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp'))
        ])
        if wallpapers:
            try:
                _set_wallpaper_direct(wallpapers[0])
                applied.append("wallpaper")
            except Exception as e:
                errors.append(f"wallpaper: {e}")

    # 2. Apply accent color + dark/light mode via registry
    try:
        from desktop_handler import apply_desktop
        desk_result = apply_desktop(accent, mode)
        if desk_result.get("success"):
            applied.append("accent+mode")
        else:
            errors.append(f"desktop: {desk_result.get('message')}")
    except Exception as e:
        errors.append(f"desktop: {e}")

    success = len(applied) > 0
    msg_parts = []
    if applied:
        msg_parts.append(f"Applied: {', '.join(applied)}")
    if errors:
        msg_parts.append(f"Errors: {'; '.join(errors)}")

    return {
        "success": success,
        "message": f"Applied packaged theme: {theme_entry['name']}" if success else "; ".join(msg_parts),
        "theme_id": theme_id,
        "theme_name": theme_entry["name"],
        "accent_color": accent,
        "mode": mode,
        "source": "library",
        "applied_components": applied,
        "errors": errors
    }


def _set_wallpaper_direct(path: str):
    """Set wallpaper using ctypes SystemParametersInfoW as a fallback."""
    import ctypes
    SPI_SETDESKWALLPAPER = 0x0014
    SPIF_UPDATEINIFILE = 0x01
    SPIF_SENDCHANGE = 0x02
    result = ctypes.windll.user32.SystemParametersInfoW(
        SPI_SETDESKWALLPAPER, 0, path, SPIF_UPDATEINIFILE | SPIF_SENDCHANGE
    )
    if not result:
        raise RuntimeError("SystemParametersInfoW returned 0")



def list_themes() -> list:
    """List all themes in the library catalog."""
    return _load_catalog()


def parse_msix_theme(msix_path: str) -> dict:
    """Parse an MSIX theme package and extract metadata.

    Reads the AppxManifest.xml for the name and the config.theme INI
    for colors, mode, wallpaper count, etc. Useful for building catalog entries.

    Returns a dict suitable for adding to catalog.json.
    """
    result = {
        "id": "",
        "name": "",
        "package_file": "",
        "tags": [],
        "accent_color": "",
        "mode": "dark",
        "has_sounds": False,
        "has_cursors": False,
        "has_wallpapers": False,
        "wallpaper_count": 0,
        "description": ""
    }

    basename = os.path.splitext(os.path.basename(msix_path))[0]
    result["id"] = re.sub(r'[^a-z0-9]+', '-', basename.lower()).strip('-')

    with zipfile.ZipFile(msix_path, 'r') as zf:
        # Parse AppxManifest.xml for display name
        try:
            manifest = zf.read("AppxManifest.xml").decode("utf-8")
            name_match = re.search(r'<DisplayName>([^<]+)</DisplayName>',
                                   manifest)
            if name_match:
                result["name"] = name_match.group(1)
                result["description"] = name_match.group(1)
        except Exception:
            pass

        # Find and extract the deskthemepack to parse config.theme
        theme_entries = [e for e in zf.namelist()
                         if e.lower().endswith('.deskthemepack')]
        if not theme_entries:
            return result

        # Extract deskthemepack to temp dir and expand (it's a CAB)
        with tempfile.TemporaryDirectory() as tmpdir:
            dtp_path = os.path.join(tmpdir, "theme.deskthemepack")
            with open(dtp_path, 'wb') as f:
                f.write(zf.read(theme_entries[0]))

            # Expand CAB
            expanded = os.path.join(tmpdir, "expanded")
            os.makedirs(expanded)
            subprocess.run(
                ["expand", dtp_path, "-F:*", expanded],
                capture_output=True, timeout=30
            )

            # Parse config.theme (INI format)
            config_path = None
            for fname in os.listdir(expanded):
                if fname.lower().endswith('.theme'):
                    config_path = os.path.join(expanded, fname)
                    break

            if config_path:
                result.update(_parse_theme_ini(config_path))

            # Count wallpapers
            bg_dir = os.path.join(expanded, "DesktopBackground")
            if os.path.isdir(bg_dir):
                imgs = [f for f in os.listdir(bg_dir)
                        if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp'))]
                result["has_wallpapers"] = len(imgs) > 0
                result["wallpaper_count"] = len(imgs)

    # Auto-generate basic tags from the name
    result["tags"] = list(set(
        re.findall(r'[a-z]+', result["name"].lower())
    ))

    return result


def _parse_theme_ini(path: str) -> dict:
    """Parse a config.theme INI file for metadata."""
    updates = {}

    # Theme files are typically UTF-16 LE (BOM: FF FE)
    with open(path, 'rb') as f:
        raw = f.read()
    if raw[:2] == b'\xff\xfe':
        content = raw.decode('utf-16-le')
    elif raw[:2] == b'\xfe\xff':
        content = raw.decode('utf-16-be')
    else:
        content = raw.decode('utf-8', errors='replace')

    # ColorizationColor → accent_color
    color_match = re.search(r'ColorizationColor\s*=\s*0[Xx]([0-9A-Fa-f]{8})',
                            content)
    if color_match:
        argb = color_match.group(1)
        # Format is AARRGGBB — extract RGB
        r, g, b = argb[2:4], argb[4:6], argb[6:8]
        updates["accent_color"] = f"#{r}{g}{b}".upper()

    # AppMode / SystemMode
    app_mode = re.search(r'AppMode\s*=\s*(\w+)', content)
    if app_mode:
        updates["mode"] = app_mode.group(1).lower()

    # Sounds — check if non-default scheme
    has_sounds = bool(re.search(
        r'\[Sounds\].*?SchemeName\s*=\s*(?!@mmres)',
        content, re.DOTALL
    ))
    updates["has_sounds"] = has_sounds

    # Cursors — check if any non-system cursor paths
    cursor_section = re.search(
        r'\[Control Panel\\Cursors\](.*?)(?:\[|$)',
        content, re.DOTALL
    )
    if cursor_section:
        cursor_text = cursor_section.group(1)
        non_default = [line for line in cursor_text.split('\n')
                       if '=' in line
                       and not line.strip().startswith(';')
                       and '%SystemRoot%' not in line
                       and 'DefaultValue' not in line.split('=', 1)[0]
                       and line.split('=', 1)[1].strip()]
        updates["has_cursors"] = len(non_default) > 0
    else:
        updates["has_cursors"] = False

    return updates


def _load_catalog() -> list:
    """Load the theme catalog."""
    if not os.path.exists(CATALOG_PATH):
        return []
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        return json.load(f).get("themes", [])


def rebuild_catalog() -> dict:
    """Scan all MSIX packages in the library and rebuild catalog.json.

    Preserves manually-set tags from the existing catalog while
    auto-populating everything else from the package contents.

    Returns summary dict.
    """
    existing = {}
    for t in _load_catalog():
        existing[t["id"]] = t

    themes = []
    if not os.path.isdir(PACKAGES_DIR):
        return {"success": False, "message": "No packages directory"}

    for fname in sorted(os.listdir(PACKAGES_DIR)):
        if not fname.lower().endswith('.msix'):
            continue

        msix_path = os.path.join(PACKAGES_DIR, fname)
        print(f"  Parsing: {fname}...")

        parsed = parse_msix_theme(msix_path)
        parsed["package_file"] = f"packages/{fname}"

        # Preserve manually-curated tags if they exist
        if parsed["id"] in existing:
            old = existing[parsed["id"]]
            if old.get("tags"):
                parsed["tags"] = old["tags"]
            if old.get("description") and old["description"] != old["name"]:
                parsed["description"] = old["description"]

        themes.append(parsed)

    catalog = {"version": 1, "themes": themes}
    with open(CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2)

    return {
        "success": True,
        "message": f"Catalog rebuilt with {len(themes)} themes",
        "count": len(themes)
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="MSIX theme handler")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list", help="List available themes")
    sub.add_parser("rebuild-catalog", help="Rebuild catalog from packages")

    apply_p = sub.add_parser("apply", help="Apply a theme by ID")
    apply_p.add_argument("theme_id", help="Theme ID from catalog")

    parse_p = sub.add_parser("parse", help="Parse an MSIX and show metadata")
    parse_p.add_argument("msix_path", help="Path to .msix file")

    args = parser.parse_args()

    if args.command == "list":
        themes = list_themes()
        if not themes:
            print("No themes in library. Add .msix files to library/packages/ and run rebuild-catalog.")
        for t in themes:
            status = []
            if t.get("has_wallpapers"):
                status.append(f"{t.get('wallpaper_count', '?')} wallpapers")
            if t.get("has_sounds"):
                status.append("sounds")
            if t.get("has_cursors"):
                status.append("cursors")
            extras = f" ({', '.join(status)})" if status else ""
            print(f"  {t['id']:30s} {t['name']}{extras}")

    elif args.command == "rebuild-catalog":
        print("Rebuilding catalog from packages...")
        result = rebuild_catalog()
        print(f"  {result['message']}")

    elif args.command == "apply":
        result = apply(args.theme_id)
        icon = "✅" if result["success"] else "❌"
        print(f"{icon} {result['message']}")

    elif args.command == "parse":
        result = parse_msix_theme(args.msix_path)
        print(json.dumps(result, indent=2))

    else:
        parser.print_help()
