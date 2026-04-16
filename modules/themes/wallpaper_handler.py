"""
Wallpaper handler — downloads a themed image and sets it as the desktop wallpaper.

Uses ctypes to call SystemParametersInfoW for immediate wallpaper change.
Image sources (in priority order):
  1. Direct URL (provided by agent)
  2. Art museum search (Art Institute of Chicago IIIF API) — for paintings/art themes
  3. Unsplash photo search — for nature/landscape/photo themes
"""

import ctypes
import os
import re
import sys

PICTURES_DIR = os.path.join(os.path.expanduser("~"), "Pictures")
THEMES_DIR = os.path.join(PICTURES_DIR, "themes")
WALLPAPER_PATH = os.path.join(PICTURES_DIR, "theme-wallpaper.jpg")


def _theme_cache_path(theme_name: str) -> str:
    """Get a cache path for a named theme's wallpaper."""
    safe = re.sub(r'[^\w\s-]', '', theme_name).strip().lower().replace(' ', '-')
    os.makedirs(THEMES_DIR, exist_ok=True)
    return os.path.join(THEMES_DIR, f"{safe}.jpg")


def _download(url: str, dest: str) -> bool:
    """Download a file from URL to dest path."""
    try:
        import requests
        resp = requests.get(url, timeout=15, headers={
            "User-Agent": "WindowsPersonalizationSkill/1.0"
        }, allow_redirects=True)
        if resp.status_code != 200 or len(resp.content) < 5000:
            return False
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(resp.content)
        return True
    except Exception as e:
        print(f"  Download failed: {e}", file=sys.stderr)
        return False


def _search_unsplash(query: str, dest: str) -> bool:
    """Search Unsplash for a wallpaper matching the query."""
    try:
        import requests
        import urllib.parse
        encoded = urllib.parse.quote(query)
        # Use Unsplash random photo endpoint (no API key needed for this)
        url = f"https://source.unsplash.com/random/2560x1440/?{encoded}"
        resp = requests.get(url, timeout=15, headers={
            "User-Agent": "WindowsPersonalizationSkill/1.0"
        }, allow_redirects=True)
        if resp.status_code == 200 and len(resp.content) > 5000:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as f:
                f.write(resp.content)
            return True
        return False
    except Exception as e:
        print(f"  Unsplash search failed: {e}", file=sys.stderr)
        return False


def _search_art_museum(query: str, dest: str) -> bool:
    """Search Art Institute of Chicago for artwork matching the query.

    Uses their public API + IIIF image service. Great for finding actual
    paintings, sculptures, and other fine art as wallpapers.
    """
    try:
        import requests
        import urllib.parse

        encoded = urllib.parse.quote(query)
        api_url = (
            f"https://api.artic.edu/api/v1/artworks/search"
            f"?q={encoded}&fields=id,title,image_id,artist_title"
            f"&limit=5"
        )
        resp = requests.get(api_url, timeout=10, headers={
            "User-Agent": "WindowsPersonalizationSkill/1.0"
        })
        if resp.status_code != 200:
            return False

        data = resp.json().get("data", [])
        iiif_base = resp.json().get("config", {}).get("iiif_url", "https://www.artic.edu/iiif/2")

        # Try each result until we get a good image
        for artwork in data:
            image_id = artwork.get("image_id")
            if not image_id:
                continue
            title = artwork.get("title", "unknown")
            artist = artwork.get("artist_title", "unknown")
            # Request max resolution via IIIF
            img_url = f"{iiif_base}/{image_id}/full/max/0/default.jpg"
            print(f"  🎨 Found: \"{title}\" by {artist}")
            if _download(img_url, dest):
                return True

        return False
    except Exception as e:
        print(f"  Museum search failed: {e}", file=sys.stderr)
        return False


def _set_wallpaper_win32(path: str) -> bool:
    """Set wallpaper using PowerShell + SystemParametersInfo (more reliable than ctypes)."""
    # Validate path to prevent injection — must be an existing file with image extension
    import os.path as osp
    if not osp.isabs(path) or not osp.exists(path):
        return False
    allowed_ext = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tif', '.tiff'}
    if osp.splitext(path)[1].lower() not in allowed_ext:
        return False
    # Escape single quotes for PowerShell string literal
    safe_path = path.replace("'", "''")
    ps_script = f"""
Set-ItemProperty -Path 'HKCU:\\Control Panel\\Desktop' -Name WallpaperStyle -Value '10'
Set-ItemProperty -Path 'HKCU:\\Control Panel\\Desktop' -Name TileWallpaper -Value '0'
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public class WpApply {{
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    public static extern int SystemParametersInfo(int uAction, int uParam, string lpvParam, int fuWinIni);
}}
'@
$r = [WpApply]::SystemParametersInfo(0x0014, 0, '{safe_path}', 3)
if ($r -eq 1) {{ Write-Output 'OK' }} else {{ Write-Output 'FAIL' }}
"""
    try:
        import subprocess
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        return "OK" in result.stdout
    except Exception:
        return False


def apply_wallpaper(url: str = None, search_query: str = None,
                    art_search: str = None,
                    dest: str = WALLPAPER_PATH,
                    theme_name: str = None) -> dict:
    """Download and set a themed wallpaper.

    Args:
        url: Direct URL to wallpaper image (preferred)
        search_query: Unsplash search query (fallback for photos)
        art_search: Art museum search query (fallback for paintings/fine art)
        dest: Local path to save the image
        theme_name: If provided, caches wallpaper per theme for reuse

    Returns:
        dict with 'success' bool and 'message' string
    """
    # Check cache first — reuse wallpaper if this theme was applied before
    cache_path = _theme_cache_path(theme_name) if theme_name else None
    if cache_path and os.path.exists(cache_path) and os.path.getsize(cache_path) > 5000:
        print(f"  ♻ Using cached wallpaper for '{theme_name}'")
        import shutil
        shutil.copy2(cache_path, dest)
        if _set_wallpaper_win32(dest):
            size_kb = os.path.getsize(dest) // 1024
            return {
                "success": True,
                "message": f"Wallpaper set from cache ({size_kb}KB, Fill mode)"
            }

    downloaded = False

    # Try direct URL first
    if url:
        downloaded = _download(url, dest)
        if not downloaded:
            print(f"  ⚠ Direct URL failed, trying fallback search...")

    # Fallback: art museum search (for paintings, fine art)
    if not downloaded and art_search:
        print(f"  🖼️ Searching museum collections...")
        downloaded = _search_art_museum(art_search, dest)

    # Fallback: Unsplash search (for photos, landscapes, nature)
    if not downloaded and search_query:
        print(f"  📷 Searching Unsplash photos...")
        downloaded = _search_unsplash(search_query, dest)

    if not downloaded:
        return {
            "success": False,
            "message": "Wallpaper download failed — no valid URL or search query"
        }

    # Verify file exists and has reasonable size
    if not os.path.exists(dest) or os.path.getsize(dest) < 5000:
        return {
            "success": False,
            "message": "Downloaded file too small or missing — likely an error page"
        }

    # Cache the wallpaper for this theme so it can be reused
    if cache_path:
        import shutil
        shutil.copy2(dest, cache_path)
        print(f"  💾 Cached wallpaper as '{os.path.basename(cache_path)}'")

    # Apply wallpaper
    if _set_wallpaper_win32(dest):
        size_kb = os.path.getsize(dest) // 1024
        return {
            "success": True,
            "message": f"Wallpaper set ({size_kb}KB, Fill mode)"
        }
    else:
        return {
            "success": False,
            "message": "SystemParametersInfo call failed"
        }


def check_capability() -> bool:
    """Wallpaper setting should work for all Windows users."""
    try:
        # Just verify we can call the API (get current wallpaper)
        buf = ctypes.create_unicode_buffer(512)
        ctypes.windll.user32.SystemParametersInfoW(0x0073, 512, buf, 0)
        return True
    except Exception:
        return False


if __name__ == "__main__":
    if check_capability():
        print("✅ Wallpaper capability: available")
        print(f"   Current: {ctypes.create_unicode_buffer(512)}")
    else:
        print("❌ Wallpaper capability: not available")
