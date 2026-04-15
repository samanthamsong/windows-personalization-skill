"""
Desktop styling handler — applies accent color, dark/light mode, taskbar,
and transparency via Windows registry keys.

Uses PowerShell subprocess to write registry values and broadcast
WM_SETTINGCHANGE so changes take effect immediately.
"""

import subprocess
import sys


def _hex_to_rgb(hex_color: str) -> tuple:
    """Convert '#RRGGBB' to (R, G, B)."""
    h = hex_color.lstrip('#')
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _generate_palette(r: int, g: int, b: int) -> list:
    """Generate 8 AccentPalette shades from a single RGB color.
    Returns a flat list of 32 bytes (8 colors × 4 bytes each, RGBA)."""

    def lighten(c, factor):
        return min(255, int(c + (255 - c) * factor))

    def darken(c, factor):
        return max(0, int(c * (1 - factor)))

    shades = [
        (lighten(r, 0.7), lighten(g, 0.7), lighten(b, 0.7)),  # lightest
        (lighten(r, 0.5), lighten(g, 0.5), lighten(b, 0.5)),
        (lighten(r, 0.3), lighten(g, 0.3), lighten(b, 0.3)),
        (lighten(r, 0.15), lighten(g, 0.15), lighten(b, 0.15)),
        (r, g, b),                                              # main accent
        (darken(r, 0.2), darken(g, 0.2), darken(b, 0.2)),
        (darken(r, 0.4), darken(g, 0.4), darken(b, 0.4)),
        (darken(r, 0.55), darken(g, 0.55), darken(b, 0.55)),   # darkest
    ]

    palette_bytes = []
    for i, (sr, sg, sb) in enumerate(shades):
        alpha = 0x00 if i < 7 else 0x88
        palette_bytes.extend([sr, sg, sb, alpha])
    return palette_bytes


def apply_desktop(accent_hex: str, mode: str = "dark",
                  taskbar_accent: bool = True, transparency: bool = True) -> dict:
    """Apply desktop styling via registry.

    Args:
        accent_hex: Accent color as '#RRGGBB'
        mode: 'dark' or 'light'
        taskbar_accent: Whether to show accent color on taskbar
        transparency: Whether to enable transparency effects

    Returns:
        dict with 'success' bool and 'message' string
    """
    r, g, b = _hex_to_rgb(accent_hex)
    palette = _generate_palette(r, g, b)
    palette_hex = ','.join(f'0x{byte:02X}' for byte in palette)

    is_light = 1 if mode.lower() == "light" else 0
    color_prevalence = 1 if taskbar_accent else 0
    enable_transparency = 1 if transparency else 0

    ps_script = f'''
$ErrorActionPreference = "Stop"

# Accent color (ABGR format as signed int32)
$abgr = [BitConverter]::ToInt32([byte[]]@({r}, {g}, {b}, 0xFF), 0)
Set-ItemProperty -Path "HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Accent" -Name AccentColorMenu -Value $abgr -Type DWord
Set-ItemProperty -Path "HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Accent" -Name StartColorMenu -Value $abgr -Type DWord

# DWM colors (ARGB as ColorizationColor expects BGR with alpha high byte)
$colColor = [BitConverter]::ToInt32([byte[]]@({b}, {g}, {r}, 0xC4), 0)
$dwm = "HKCU:\\SOFTWARE\\Microsoft\\Windows\\DWM"
Set-ItemProperty -Path $dwm -Name ColorizationColor -Value $colColor -Type DWord
Set-ItemProperty -Path $dwm -Name ColorizationAfterglow -Value $colColor -Type DWord
Set-ItemProperty -Path $dwm -Name AccentColor -Value $abgr -Type DWord
Set-ItemProperty -Path $dwm -Name ColorPrevalence -Value 1 -Type DWord
Set-ItemProperty -Path $dwm -Name ColorizationColorBalance -Value 100 -Type DWord

# AccentPalette binary blob
$palette = [byte[]]@({palette_hex})
Set-ItemProperty -Path "HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Accent" -Name AccentPalette -Value $palette -Type Binary

# Light/Dark mode
$personalize = "HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize"
Set-ItemProperty -Path $personalize -Name AppsUseLightTheme -Value {is_light} -Type DWord
Set-ItemProperty -Path $personalize -Name SystemUsesLightTheme -Value {is_light} -Type DWord
Set-ItemProperty -Path $personalize -Name EnableTransparency -Value {enable_transparency} -Type DWord
Set-ItemProperty -Path $personalize -Name ColorPrevalence -Value {color_prevalence} -Type DWord

# Broadcast ImmersiveColorSet for immediate effect
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class ThemeBroadcast {{
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    public static extern IntPtr SendMessageTimeout(IntPtr hWnd, uint Msg, UIntPtr wParam, string lParam, uint fuFlags, uint uTimeout, out UIntPtr lpdwResult);
    public static void Broadcast() {{
        UIntPtr r;
        SendMessageTimeout((IntPtr)0xFFFF, 0x001A, UIntPtr.Zero, "ImmersiveColorSet", 0x0002, 5000, out r);
    }}
}}
"@
[ThemeBroadcast]::Broadcast()

# Restart Explorer to force taskbar to pick up new accent color
$explorerPid = (Get-Process -Name explorer -ErrorAction SilentlyContinue | Select-Object -First 1).Id
if ($explorerPid) {{
    Stop-Process -Id $explorerPid -Force
    Start-Sleep -Seconds 2
    if (-not (Get-Process -Name explorer -ErrorAction SilentlyContinue)) {{
        Start-Process explorer.exe
    }}
}}

Write-Output "OK"
'''

    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            capture_output=True, text=True, timeout=20
        )
        if result.returncode == 0 and "OK" in result.stdout:
            return {
                "success": True,
                "message": f"Desktop styled: accent={accent_hex}, mode={mode}, taskbar_accent={taskbar_accent}"
            }
        else:
            error = result.stderr.strip() or result.stdout.strip()
            return {"success": False, "message": f"Registry write failed: {error}"}
    except subprocess.TimeoutExpired:
        return {"success": False, "message": "Desktop styling timed out"}
    except Exception as e:
        return {"success": False, "message": f"Desktop styling error: {e}"}


def check_capability() -> bool:
    """Test whether we can write to HKCU registry."""
    ps = '''
$ErrorActionPreference = "Stop"
$testPath = "HKCU:\\SOFTWARE\\PersonalizationSkillTest"
try {
    New-Item -Path $testPath -Force | Out-Null
    Remove-Item -Path $testPath -Force | Out-Null
    Write-Output "OK"
} catch {
    Write-Output "FAIL"
}
'''
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True, text=True, timeout=5
        )
        return "OK" in result.stdout
    except Exception:
        return False


if __name__ == "__main__":
    # Quick test
    if check_capability():
        print("✅ Registry write capability: available")
    else:
        print("❌ Registry write capability: not available")
