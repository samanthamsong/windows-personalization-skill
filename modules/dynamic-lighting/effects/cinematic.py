"""
Cinematic Mode — screen-reactive ambient lighting
===================================================
Captures the screen and maps dominant colors from each region to the
corresponding keyboard zone, creating a bias-light / Ambilight effect.

Usage:
    python cinematic.py
    python cinematic.py --monitor 2     # use second monitor
    python cinematic.py --saturation 1.5 # boost color saturation
"""

import os
import subprocess
import json
import time
import threading
import sys
import math
import argparse
import colorsys
import numpy as np
from mss import MSS

# === ARGS ===
parser = argparse.ArgumentParser(description="Cinematic mode — screen-reactive lighting")
parser.add_argument("--monitor", type=int, default=1, help="Monitor number (1 = primary)")
parser.add_argument("--saturation", type=float, default=1.3, help="Color saturation boost (1.0 = no change)")
parser.add_argument("--brightness", type=float, default=1.0, help="Brightness multiplier (1.0 = no change)")
cli_args = parser.parse_args()

# === LIGHTING DRIVER ===
# Search for driver in known locations
_candidates = [
    os.path.join(os.environ.get('LOCALAPPDATA', ''), 'DynamicLightingDriver', 'DynamicLightingDriver.exe'),
    os.path.join(os.path.expanduser('~'), 'DLDriverBin', 'DynamicLightingDriver.exe'),
]
EXE = next((p for p in _candidates if os.path.isfile(p)), _candidates[0])
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

proc = subprocess.Popen([EXE], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
threading.Thread(target=lambda: [proc.stderr.readline() for _ in iter(int, 1)], daemon=True).start()

def send(cmd):
    proc.stdin.write((cmd + '\n').encode())
    proc.stdin.flush()

def recv():
    return proc.stdout.readline().decode().strip()

ready = recv()
assert ready == 'READY', f'Driver not ready: {ready}'

send("SET_EFFECT_NAME Cinematic Mode")
recv()

# Keep the driver window in foreground so LampArray stays available
send("HOLD_FOREGROUND on")
recv()

# === KEYBOARD LAYOUT (87-key TKL) ===
GRID_COLS = 15
GRID_ROWS = 7

rows = [15, 15, 15, 14, 13, 8, 7]
row_offsets = [0, 0, 0.075, 0.12, 0.15, 0, 0.85]
row_kw = [1, 1, 1, 1, 1, 1.5, 1]

lamps = []
idx = 0
for ri, count in enumerate(rows):
    for ci in range(count):
        x = (row_offsets[ri] + ci * row_kw[ri]) / 15.0
        y = ri / 6.0
        lamps.append({"idx": idx, "x": x, "y": y, "row": ri, "col": ci})
        idx += 1


def boost_saturation(r, g, b, factor, brightness):
    """Boost color saturation and brightness in HSV space."""
    h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    s = min(1.0, s * factor)
    v = min(1.0, v * brightness)
    r2, g2, b2 = colorsys.hsv_to_rgb(h, s, v)
    return int(r2 * 255), int(g2 * 255), int(b2 * 255)


def lerp_color(c1, c2, t):
    """Linearly interpolate between two RGB tuples."""
    t = max(0.0, min(1.0, t))
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


# === SCREEN CAPTURE ===
sct = MSS()
monitor = sct.monitors[cli_args.monitor]

# Previous frame's grid for temporal smoothing
prev_grid = None
SMOOTHING = 0.4  # 0 = no smoothing, 1 = fully previous frame


def capture_screen_grid():
    """Capture the screen and downsample to a GRID_ROWS x GRID_COLS color grid."""
    global prev_grid

    frame = sct.grab(monitor)
    # Convert BGRA to RGB numpy array, then resize to grid dimensions
    img = np.frombuffer(frame.raw, dtype=np.uint8).reshape(frame.height, frame.width, 4)
    # Drop alpha, convert BGR -> RGB
    img = img[:, :, :3][:, :, ::-1]

    # Downsample by splitting into grid cells and averaging each
    h, w = img.shape[:2]
    cell_h = h // GRID_ROWS
    cell_w = w // GRID_COLS

    grid = np.zeros((GRID_ROWS, GRID_COLS, 3), dtype=np.float32)
    for gy in range(GRID_ROWS):
        for gx in range(GRID_COLS):
            y0 = gy * cell_h
            y1 = y0 + cell_h
            x0 = gx * cell_w
            x1 = x0 + cell_w
            cell = img[y0:y1, x0:x1]
            grid[gy, gx] = cell.mean(axis=(0, 1))

    # Temporal smoothing to reduce flicker
    if prev_grid is not None:
        grid = prev_grid * SMOOTHING + grid * (1 - SMOOTHING)
    prev_grid = grid.copy()

    return grid


def render_frame_from_grid(grid):
    """Map the screen color grid to keyboard lamps."""
    colors = {}
    for lamp in lamps:
        # Map lamp (x, y) position to grid cell
        gx = min(int(lamp['x'] * GRID_COLS), GRID_COLS - 1)
        gy = min(int(lamp['y'] * GRID_ROWS), GRID_ROWS - 1)

        r, g, b = int(grid[gy, gx, 0]), int(grid[gy, gx, 1]), int(grid[gy, gx, 2])
        r, g, b = boost_saturation(r, g, b, cli_args.saturation, cli_args.brightness)
        colors[str(lamp['idx'])] = f'#{r:02x}{g:02x}{b:02x}'
    return colors


# === ANIMATION LOOP ===
FPS = 10
print(f"Cinematic mode active (~{FPS}fps). Capturing monitor {cli_args.monitor} ({monitor['width']}x{monitor['height']}).")
print("Press Ctrl+C to stop.")
sys.stdout.flush()

PAUSE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'rules', '.pause')

frame_count = 0
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
                all_flash = {str(lamp['idx']): flash_color for lamp in lamps}
                flash_start = time.time()
                while time.time() - flash_start < flash_duration:
                    send(f"SET_LAMPS {json.dumps(all_flash)}")
                    recv()
                    frame_count += 1
                    time.sleep(0.125)
            except Exception as e:
                print(f"Alert flash error: {e}")
            finally:
                try:
                    os.remove(PAUSE_FILE)
                except Exception:
                    pass
            continue

        grid = capture_screen_grid()
        colors = render_frame_from_grid(grid)
        send(f"SET_LAMPS {json.dumps(colors)}")
        recv()

        frame_count += 1
        elapsed = time.time() - start
        target = frame_count / float(FPS)
        if target > elapsed:
            time.sleep(target - elapsed)
except KeyboardInterrupt:
    print("\nStopped cinematic mode.")
    proc.terminate()
