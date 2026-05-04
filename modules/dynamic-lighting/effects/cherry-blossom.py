import math
import random
from _runner import EffectRunner, lerp, hex_color

runner = EffectRunner("Cherry Blossom")

PINK_BASE = (255, 183, 197)    # #FFB7C5
PINK_LIGHT = (255, 221, 225)   # #FFDDE1
SAKURA_DEEP = (232, 144, 156)  # #E8909C
WHITE = (255, 255, 255)        # #FFFFFF

# Pre-generate sparkle phases for petal twinkles
NUM_SPARKLES = 12
sparkle_x = [random.random() for _ in range(NUM_SPARKLES)]
sparkle_y = [random.random() for _ in range(NUM_SPARKLES)]
sparkle_speed = [random.uniform(2.0, 5.0) for _ in range(NUM_SPARKLES)]
sparkle_phase = [random.uniform(0, math.tau) for _ in range(NUM_SPARKLES)]


def render_frame(device, t):
    colors = {}
    for lamp in device.lamps:
        lx, ly = lamp["x"], lamp["y"]

        # Layer 0: Soft pink breathing base
        breathe = 0.5 + 0.5 * math.sin(t * 1.2)
        base = lerp(PINK_BASE, PINK_LIGHT, breathe)

        # Layer 1: Deeper sakura wave sweeping left to right
        wave = 0.5 + 0.5 * math.sin((lx * 4.0) - t * 1.5)
        color = lerp(base, SAKURA_DEEP, wave * 0.5)

        # Layer 2: Sparse white sparkle petals
        best_spark = 0.0
        for i in range(NUM_SPARKLES):
            dx = lx - sparkle_x[i]
            dy = ly - sparkle_y[i]
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < 0.20:
                pulse = max(0.0, math.sin(t * sparkle_speed[i] + sparkle_phase[i]))
                intensity = pulse * (1.0 - dist / 0.20)
                best_spark = max(best_spark, intensity)

        if best_spark > 0.1:
            color = lerp(color, WHITE, best_spark * 0.8)

        colors[str(lamp["idx"])] = hex_color(*color)
    return colors


runner.run(render_frame, fps=8)
