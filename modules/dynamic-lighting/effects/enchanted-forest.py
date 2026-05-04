import math
import random
from _runner import EffectRunner, lerp, hex_color

runner = EffectRunner("Enchanted Forest")

DARK_GREEN = (10, 46, 10)     # #0A2E0A
BRIGHT_GREEN = (27, 94, 32)   # #1B5E20
BLUE_MIST = (0, 77, 102)      # #004D66
GOLD = (255, 224, 130)         # #FFE082

# Firefly sparkle positions
NUM_FIREFLIES = 10
fly_x = [random.random() for _ in range(NUM_FIREFLIES)]
fly_y = [random.random() for _ in range(NUM_FIREFLIES)]
fly_speed = [random.uniform(2.5, 5.0) for _ in range(NUM_FIREFLIES)]
fly_phase = [random.uniform(0, math.tau) for _ in range(NUM_FIREFLIES)]


def render_frame(device, t):
    colors = {}
    for lamp in device.lamps:
        lx, ly = lamp["x"], lamp["y"]

        # Layer 0: Deep green breathing base
        breathe = 0.5 + 0.5 * math.sin(t * 1.0)
        color = lerp(DARK_GREEN, BRIGHT_GREEN, breathe)

        # Layer 1: Slow blue mist wave
        wave = 0.5 + 0.5 * math.sin((lx * 3.0) - t * 1.2)
        color = lerp(color, BLUE_MIST, wave * 0.35)

        # Layer 2: Golden firefly sparkles
        best_glow = 0.0
        for i in range(NUM_FIREFLIES):
            dx = lx - fly_x[i]
            dy = ly - fly_y[i]
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < 0.25:
                pulse = max(0.0, math.sin(t * fly_speed[i] + fly_phase[i]))
                # Sharp on/off blink
                blink = 1.0 if pulse > 0.6 else 0.0
                intensity = blink * (1.0 - dist / 0.25)
                best_glow = max(best_glow, intensity)

        if best_glow > 0.1:
            color = lerp(color, GOLD, best_glow * 0.9)

        colors[str(lamp["idx"])] = hex_color(*color)
    return colors


runner.run(render_frame, fps=8)
