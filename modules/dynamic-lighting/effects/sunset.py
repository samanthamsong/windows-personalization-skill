"""
Sunset Effect
=============
A warm horizon gradient that slowly shifts through golden hour colors.
Bottom rows glow deep orange/red, middle rows are golden amber,
top rows fade into dusky purple — with gentle shimmer throughout.
"""

import os
import subprocess
import json
import time
import threading
import sys
import math
import random

# === MCP SERVER ===
EXE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src', 'DynamicLightingMcp', 'bin', 'Debug', 'net9.0-windows10.0.26100.0', 'DynamicLightingMcp.exe')

proc = subprocess.Popen([EXE], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
threading.Thread(target=lambda: [proc.stderr.readline() for _ in iter(int, 1)], daemon=True).start()

def send(obj):
    proc.stdin.write((json.dumps(obj) + '\n').encode())
    proc.stdin.flush()

def recv():
    return json.loads(proc.stdout.readline())

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

# === EFFECT CONFIG ===
FPS = 8
EFFECT_NAME = "Sunset"

# Sunset palette (bottom to top)
HORIZON = (255, 60, 20)     # deep red-orange at the horizon
GOLDEN = (255, 160, 30)     # golden amber
PEACH = (255, 120, 80)      # warm peach
DUSK = (120, 50, 140)       # dusky purple
NIGHT = (30, 15, 60)        # deep indigo

# Seed per-lamp shimmer offsets
random.seed(42)
shimmer_offsets = [random.uniform(0, math.pi * 2) for _ in lamps]


def lerp(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def sunset_gradient(y, t):
    """Map vertical position to a sunset color, with slow time drift."""
    drift = math.sin(t * 0.15) * 0.08
    y_shifted = max(0.0, min(1.0, y + drift))

    if y_shifted < 0.25:
        return lerp(NIGHT, DUSK, y_shifted / 0.25)
    elif y_shifted < 0.5:
        return lerp(DUSK, PEACH, (y_shifted - 0.25) / 0.25)
    elif y_shifted < 0.75:
        return lerp(PEACH, GOLDEN, (y_shifted - 0.5) / 0.25)
    else:
        return lerp(GOLDEN, HORIZON, (y_shifted - 0.75) / 0.25)


def render_frame(t):
    colors = {}
    for i, lamp in enumerate(lamps):
        base = sunset_gradient(lamp['y'], t)

        # Gentle shimmer: slight brightness fluctuation per lamp
        shimmer = math.sin(t * 1.5 + shimmer_offsets[i]) * 0.08 + 1.0
        r = min(255, int(base[0] * shimmer))
        g = min(255, int(base[1] * shimmer))
        b = min(255, int(base[2] * shimmer))

        colors[str(lamp['idx'])] = '#{:02x}{:02x}{:02x}'.format(r, g, b)
    return colors


# === ANIMATION LOOP ===
print(f"Starting {EFFECT_NAME} (~{FPS}fps). Press Ctrl+C to stop.")
sys.stdout.flush()

frame = 0
start = time.time()
try:
    while True:
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
