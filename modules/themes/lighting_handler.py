"""
Lighting handler — palette-driven Dynamic Lighting effect for theme engine.

Accepts a color palette (2-6 colors) and a style, then renders a themed
animation across all connected DL peripherals using DeviceManager.

Styles:
    wave    — flowing gradient that moves across the device
    breathe — slow synchronized pulse through palette colors
    shimmer — base gradient with random sparkle overlay
    static  — solid palette gradient mapped to lamp position
    pulse   — rhythmic brightness pulse (like a heartbeat)

Usage:
    python lighting_handler.py --palette "#4A7C2E,#8B6914,#2D5016" --style wave
    python lighting_handler.py --stop
"""

import os
import sys
import subprocess
import json
import time
import math
import threading
import argparse
import signal
import io

# Ensure UTF-8 output
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add parent dirs so we can import device_manager from spotify module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'spotify'))
from device_manager import DeviceManager

EXE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    '..', 'dynamic-lighting', 'src', 'DynamicLightingDriver',
                    'bin', 'Debug', 'net9.0-windows10.0.26100.0',
                    'DynamicLightingDriver.exe')

PID_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.theme-lighting.pid')
PAUSE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          '..', 'dynamic-lighting', 'rules', '.pause')

FPS = 8


def hex_to_rgb(h: str) -> tuple:
    h = h.lstrip('#')
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def rgb_to_hex(r, g, b) -> str:
    return '#{:02x}{:02x}{:02x}'.format(
        max(0, min(255, int(r))),
        max(0, min(255, int(g))),
        max(0, min(255, int(b))))


def lerp_color(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return (c1[0] + (c2[0] - c1[0]) * t,
            c1[1] + (c2[1] - c1[1]) * t,
            c1[2] + (c2[2] - c1[2]) * t)


def palette_sample(palette, t):
    """Sample a color from the palette at position t (0.0–1.0)."""
    if len(palette) == 1:
        return palette[0]
    t = t % 1.0
    n = len(palette)
    idx = t * n
    i = int(idx) % n
    j = (i + 1) % n
    frac = idx - int(idx)
    return lerp_color(palette[i], palette[j], frac)


# --- Effect renderers ---

def render_wave(palette, device, lamp, t):
    """Flowing gradient that moves across the device."""
    pos = (lamp['x'] * 0.7 + lamp['y'] * 0.3)  # diagonal flow
    phase = (pos - t * 0.3) % 1.0
    color = palette_sample(palette, phase)
    return rgb_to_hex(*color)


def render_breathe(palette, device, lamp, t):
    """Slow pulse cycling through palette colors."""
    cycle = t * 0.15  # slow cycle
    color = palette_sample(palette, cycle % 1.0)
    brightness = 0.3 + 0.7 * (math.sin(t * 1.5) * 0.5 + 0.5)
    return rgb_to_hex(color[0] * brightness, color[1] * brightness, color[2] * brightness)


def render_shimmer(palette, device, lamp, t):
    """Base gradient with sparkle overlay."""
    pos = (lamp['x'] + lamp['y'] * 0.5) % 1.0
    color = palette_sample(palette, pos)

    # Pseudo-random sparkle per lamp
    seed = (lamp['idx'] * 73856093) & 0x7FFFFFFF
    sparkle_phase = math.sin(t * (2.0 + (seed % 100) / 50.0) + seed) * 0.5 + 0.5
    if sparkle_phase > 0.92:
        boost = (sparkle_phase - 0.92) / 0.08
        color = lerp_color(color, (255, 255, 255), boost * 0.6)

    return rgb_to_hex(*color)


def render_static(palette, device, lamp, t):
    """Solid palette gradient mapped to position."""
    pos = (lamp['x'] * 0.8 + lamp['y'] * 0.2) % 1.0
    color = palette_sample(palette, pos)
    return rgb_to_hex(*color)


def render_pulse(palette, device, lamp, t):
    """Rhythmic brightness pulse radiating from center."""
    cx, cy = 0.5, 0.5
    dist = math.sqrt((lamp['x'] - cx) ** 2 + (lamp['y'] - cy) ** 2)
    wave = math.sin(t * 3.0 - dist * 8.0) * 0.5 + 0.5
    color = palette_sample(palette, (lamp['x'] + lamp['y']) * 0.5)
    brightness = 0.15 + wave * 0.85
    return rgb_to_hex(color[0] * brightness, color[1] * brightness, color[2] * brightness)


RENDERERS = {
    'wave': render_wave,
    'breathe': render_breathe,
    'shimmer': render_shimmer,
    'static': render_static,
    'pulse': render_pulse,
}


def stop_existing():
    """Stop any running theme lighting process and orphaned DL drivers."""
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, 'r') as f:
                pid = int(f.read().strip())
            os.kill(pid, signal.SIGTERM)
            print(f"  Stopped previous theme lighting (PID {pid})")
        except (ProcessLookupError, ValueError, OSError):
            pass
        try:
            os.remove(PID_FILE)
        except OSError:
            pass

    # Kill any DynamicLightingDriver processes so we can take over the lamps
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             'Get-Process -Name DynamicLightingDriver -ErrorAction SilentlyContinue | '
             'ForEach-Object { Stop-Process -Id $_.Id -Force; Write-Host "Killed driver PID $($_.Id)" }'],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        if result.stdout.strip():
            print(f"  {result.stdout.strip()}")
    except Exception:
        pass


def run_effect(palette_hex: list, style: str = "wave"):
    """Run the themed lighting effect.

    Args:
        palette_hex: List of hex color strings, e.g. ['#4A7C2E', '#8B6914']
        style: One of 'wave', 'breathe', 'shimmer', 'static', 'pulse'
    """
    stop_existing()

    palette = [hex_to_rgb(c) for c in palette_hex]
    renderer = RENDERERS.get(style, render_wave)

    # Save PID for stop functionality
    with open(PID_FILE, 'w') as f:
        f.write(str(os.getpid()))

    # Start DL driver
    if not os.path.exists(EXE):
        print(f"  ❌ Driver not found: {EXE}")
        return {"success": False, "message": "DL driver not built"}

    proc = subprocess.Popen(
        [EXE], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, bufsize=0
    )
    threading.Thread(target=lambda: [proc.stderr.readline() for _ in iter(int, 1)],
                     daemon=True).start()

    def send(cmd):
        proc.stdin.write((cmd + '\n').encode())
        proc.stdin.flush()

    def recv():
        return proc.stdout.readline().decode().strip()

    ready = recv()
    if ready != 'READY':
        print(f"  ❌ Driver not ready: {ready}")
        return {"success": False, "message": f"Driver error: {ready}"}

    # Discover devices
    dm = DeviceManager(send, recv)
    dm.discover()

    if not dm.devices:
        proc.terminate()
        return {"success": False, "message": "No DL devices found"}

    style_name = style.capitalize()
    colors_str = ', '.join(palette_hex[:3])
    if len(palette_hex) > 3:
        colors_str += f" +{len(palette_hex) - 3} more"
    print(f"  🎨 Theme lighting: {style_name} ({colors_str})")
    print(f"  Running on {len(dm.devices)} device(s) at ~{FPS}fps. Ctrl+C to stop.")
    sys.stdout.flush()

    frame = 0
    start = time.time()
    try:
        while True:
            # Alert flash coordination
            if os.path.exists(PAUSE_FILE):
                try:
                    with open(PAUSE_FILE, 'r') as f:
                        alert_data = f.read().strip()
                    parts = alert_data.split('|')
                    flash_color = parts[0] if parts[0].startswith('#') else '#FF69B4'
                    flash_duration = float(parts[1]) if len(parts) > 1 else 3.0
                    flash_start = time.time()
                    while time.time() - flash_start < flash_duration:
                        dm.send_frame_all(lambda dev, lamp: flash_color)
                        frame += 1
                        time.sleep(0.125)
                except Exception as e:
                    print(f"  Alert flash error: {e}")
                finally:
                    try:
                        os.remove(PAUSE_FILE)
                    except Exception:
                        pass
                continue

            t = time.time() - start
            dm.send_frame_all(lambda dev, lamp, _t=t: renderer(palette, dev, lamp, _t))
            frame += 1
            target = frame / float(FPS)
            elapsed = time.time() - start
            if target > elapsed:
                time.sleep(target - elapsed)

    except KeyboardInterrupt:
        print("\n  Stopped.")
    finally:
        try:
            os.remove(PID_FILE)
        except OSError:
            pass
        proc.terminate()


def check_capability() -> bool:
    """Check if the DL driver executable exists."""
    return os.path.exists(EXE)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Theme lighting effect")
    parser.add_argument("--palette", type=str, help="Comma-separated hex colors")
    parser.add_argument("--style", type=str, default="wave",
                        choices=list(RENDERERS.keys()),
                        help="Effect style (default: wave)")
    parser.add_argument("--stop", action="store_true", help="Stop running theme lighting")
    args = parser.parse_args()

    if args.stop:
        stop_existing()
        print("✅ Theme lighting stopped")
    elif args.palette:
        colors = [c.strip() for c in args.palette.split(',')]
        run_effect(colors, args.style)
    else:
        parser.print_help()
