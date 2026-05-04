import math
import random
from _runner import EffectRunner, lerp, hex_color

runner = EffectRunner("Hello Kitty")

# Palette
HOT_PINK = (255, 105, 180)
SOFT_PINK = (255, 182, 213)
WHITE = (255, 255, 255)
BOW_RED = (255, 60, 80)

# Twinkling sparkles — larger and brighter
NUM_SPARKLES = 20
sparkles = [
    {
        "x": random.random(),
        "y": random.random(),
        "speed": random.uniform(2.0, 4.0),
        "phase": random.random() * math.tau,
        "radius": random.uniform(0.15, 0.30),
    }
    for _ in range(NUM_SPARKLES)
]

# Bow-red accent points that pulse
NUM_BOWS = 5
bows = [
    {
        "x": random.uniform(0.1, 0.9),
        "y": random.uniform(0.1, 0.9),
        "speed": random.uniform(0.6, 1.2),
        "phase": random.random() * math.tau,
        "radius": random.uniform(0.15, 0.25),
    }
    for _ in range(NUM_BOWS)
]


def render_frame(device, t):
    colors = {}
    for lamp in device.lamps:
        lx, ly = lamp["x"], lamp["y"]

        # Base: bold pink sweep that moves across the keyboard
        wave = math.sin(lx * 4 - t * 1.5) * 0.5 + 0.5
        base = lerp(HOT_PINK, SOFT_PINK, wave)
        r, g, b = base

        # White sparkle twinkles — bold pop-in/pop-out
        for s in sparkles:
            dx = lx - s["x"]
            dy = ly - s["y"]
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < s["radius"]:
                raw = math.sin(t * s["speed"] + s["phase"])
                brightness = max(0, raw) ** 0.5  # sharper on/off
                brightness *= 1.0 - (dist / s["radius"])
                blended = lerp((r, g, b), WHITE, brightness * 0.9)
                r, g, b = blended

        # Bow-red accent pulses
        for bow in bows:
            dx = lx - bow["x"]
            dy = ly - bow["y"]
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < bow["radius"]:
                pulse = max(0, math.sin(t * bow["speed"] + bow["phase"]))
                intensity = pulse * (1.0 - dist / bow["radius"]) * 0.7
                blended = lerp((r, g, b), BOW_RED, intensity)
                r, g, b = blended

        colors[str(lamp["idx"])] = hex_color(int(r), int(g), int(b))
    return colors


runner.run(render_frame, fps=8)
