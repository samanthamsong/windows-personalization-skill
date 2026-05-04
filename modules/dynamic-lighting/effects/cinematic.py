"""
Cinematic Mode — screen-reactive ambient lighting
===================================================
Captures the screen and maps dominant colors from each region to the
corresponding device lamps, creating a bias-light / Ambilight effect.

Works across all connected Dynamic Lighting devices (keyboards, mice,
lamps, mousepads, headsets, light strips).

Usage:
    python cinematic.py
    python cinematic.py --monitor 2     # use second monitor
    python cinematic.py --saturation 1.5 # boost color saturation
"""

import os
import time
import sys
import argparse
import colorsys
import numpy as np
from mss import MSS
from _runner import EffectRunner

# === ARGS ===
parser = argparse.ArgumentParser(description="Cinematic mode — screen-reactive lighting")
parser.add_argument("--monitor", type=int, default=1, help="Monitor number (1 = primary)")
parser.add_argument("--saturation", type=float, default=1.3, help="Color saturation boost (1.0 = no change)")
parser.add_argument("--brightness", type=float, default=1.0, help="Brightness multiplier (1.0 = no change)")
cli_args = parser.parse_args()

# === LIGHTING DRIVER (multi-device) ===
runner = EffectRunner("Cinematic Mode")

# Keep the driver window in foreground so LampArray stays available
runner.send("HOLD_FOREGROUND on")
runner.recv()

# === SCREEN GRID SETTINGS ===
GRID_COLS = 15
GRID_ROWS = 7


def boost_saturation(r, g, b, factor, brightness):
    """Boost color saturation and brightness in HSV space."""
    h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    s = min(1.0, s * factor)
    v = min(1.0, v * brightness)
    r2, g2, b2 = colorsys.hsv_to_rgb(h, s, v)
    return int(r2 * 255), int(g2 * 255), int(b2 * 255)


# === SCREEN CAPTURE ===
sct = None
monitor = None

prev_grid = None
SMOOTHING = 0.4  # 0 = no smoothing, 1 = fully previous frame

MAX_CAPTURE_RETRIES = 3


def _init_mss():
    """Create (or recreate) the MSS capture instance."""
    global sct, monitor
    if sct is not None:
        try:
            sct.close()
        except Exception:
            pass
    sct = MSS()
    monitor = sct.monitors[cli_args.monitor]


_init_mss()


def capture_screen_grid():
    """Capture the screen and downsample to a GRID_ROWS x GRID_COLS color grid."""
    global prev_grid

    for attempt in range(MAX_CAPTURE_RETRIES):
        try:
            frame = sct.grab(monitor)
            break
        except Exception:
            if attempt < MAX_CAPTURE_RETRIES - 1:
                time.sleep(0.5)
                _init_mss()
            else:
                raise
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


def render_device_from_grid(device, grid):
    """Map the screen color grid to a device's lamps."""
    colors = {}
    for lamp in device.lamps:
        gx = min(int(lamp['x'] * GRID_COLS), GRID_COLS - 1)
        gy = min(int(lamp['y'] * GRID_ROWS), GRID_ROWS - 1)

        r, g, b = int(grid[gy, gx, 0]), int(grid[gy, gx, 1]), int(grid[gy, gx, 2])
        r, g, b = boost_saturation(r, g, b, cli_args.saturation, cli_args.brightness)
        colors[str(lamp['idx'])] = f'#{r:02x}{g:02x}{b:02x}'
    return colors


# === ANIMATION LOOP (multi-device) ===
FPS = 10
device_count = len(runner.dm.devices)
lamp_count = sum(len(d.lamps) for d in runner.dm.devices)
print(f"Cinematic mode active on {device_count} device(s), {lamp_count} lamps (~{FPS}fps).")
print(f"Capturing monitor {cli_args.monitor} ({monitor['width']}x{monitor['height']}).")
print("Press Ctrl+C to stop.")
sys.stdout.flush()

PAUSE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'rules', '.pause')

frame_count = 0
start = time.time()
try:
    while True:
        # Alert flash coordination (handled by runner for all devices)
        if os.path.exists(PAUSE_FILE):
            runner._handle_alert_flash(frame_count)
            continue

        grid = capture_screen_grid()
        frames = {}
        for device in runner.dm.devices:
            frames[device.id] = render_device_from_grid(device, grid)
        runner.dm.send_frames(frames)

        frame_count += 1
        elapsed = time.time() - start
        target = frame_count / float(FPS)
        if target > elapsed:
            time.sleep(target - elapsed)
except KeyboardInterrupt:
    print("\nStopped cinematic mode.")
