"""
Dynamic Lighting Effect Template
=================================
Copy this file to create a new per-lamp lighting effect.

How it works:
1. Launches the Dynamic Lighting MCP server via JSON-RPC over stdio
2. Calls `set_per_lamp_colors` each frame with a dict of {lamp_index: "#rrggbb"}
3. Your job: implement `render_frame(t)` to return colors for each lamp

Alert flash coordination:
    Effects support pause-file alert overrides. When ../rules/.pause exists,
    the animation loop reads the file (format: #RRGGBB|seconds), flashes all
    lamps that color for the specified duration, deletes the file, and resumes.
    The PAUSE_FILE constant and check block at the top of the while-loop handle
    this automatically — keep them in your effect.

Quick start:
    1. Copy this file: cp _template.py my-effect.py
    2. Edit the EFFECT CONFIG section and render_frame()
    3. Build the MCP server: dotnet build (from modules/dynamic-lighting/)
    4. Run: python my-effect.py

Keyboard layout:
    87-key TKL with 7 rows. Each lamp has an (x, y) position normalized to [0, 1].
    Use lamp['x'] and lamp['y'] to create spatial effects.
"""

import os
import subprocess
import json
import time
import threading
import sys
import math

# === MCP SERVER ===
EXE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src', 'DynamicLightingMcp', 'bin', 'Debug', 'net9.0-windows10.0.26100.0', 'DynamicLightingMcp.exe')

proc = subprocess.Popen([EXE], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
threading.Thread(target=lambda: [proc.stderr.readline() for _ in iter(int, 1)], daemon=True).start()

def send(obj):
    proc.stdin.write((json.dumps(obj) + '\n').encode())
    proc.stdin.flush()

def recv():
    return json.loads(proc.stdout.readline())

# Initialize MCP handshake
send({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {
    'protocolVersion': '2024-11-05', 'capabilities': {},
    'clientInfo': {'name': 'effect-script', 'version': '1.0'}
}})
recv()
send({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
time.sleep(3)

# === KEYBOARD LAYOUT (87-key TKL) ===
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


# =============================================
# === EFFECT CONFIG — edit these values! ===
# =============================================
FPS = 8
EFFECT_NAME = "My Effect"

# Your color palette
COLOR_A = (0, 120, 255)   # primary color
COLOR_B = (255, 255, 255) # accent color


def lerp(c1, c2, t):
    """Linearly interpolate between two RGB colors."""
    t = max(0.0, min(1.0, t))
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def render_frame(t):
    """
    Return a dict of {lamp_index_str: "#rrggbb"} for the current time t (seconds).

    This is where your effect logic goes! Use lamp['x'] and lamp['y']
    for spatial effects, and `t` for animation over time.
    """
    colors = {}
    for lamp in lamps:
        # Example: a simple wave that moves left to right
        wave = math.sin(lamp['x'] * math.pi * 2 - t * 2.0) * 0.5 + 0.5
        color = lerp(COLOR_A, COLOR_B, wave)
        colors[str(lamp['idx'])] = '#{:02x}{:02x}{:02x}'.format(*color)
    return colors


# === ANIMATION LOOP ===
print(f"Starting {EFFECT_NAME} (~{FPS}fps). Press Ctrl+C to stop.")
sys.stdout.flush()

PAUSE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'rules', '.pause')

frame = 0
start = time.time()
try:
    while True:
        # Alert flash coordination — check for notification override
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
                    send({'jsonrpc':'2.0','id':100+frame,'method':'tools/call','params':{
                        'name':'set_per_lamp_colors',
                        'arguments':{'lamp_colors': json.dumps(all_flash)}
                    }})
                    recv()
                    frame += 1
                    time.sleep(0.125)
            except Exception as e:
                print(f"Alert flash error: {e}")
            finally:
                try:
                    os.remove(PAUSE_FILE)
                except Exception:
                    pass
            continue
        t = time.time() - start
        colors = render_frame(t)
        send({'jsonrpc': '2.0', 'id': 100 + frame, 'method': 'tools/call', 'params': {
            'name': 'set_per_lamp_colors',
            'arguments': {'lamp_colors': json.dumps(colors)}
        }})
        recv()
        frame += 1
        elapsed = time.time() - start
        target = frame / float(FPS)
        if target > elapsed:
            time.sleep(target - elapsed)
except KeyboardInterrupt:
    print("\nStopped.")
    proc.terminate()
