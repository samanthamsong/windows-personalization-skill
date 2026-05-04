import math
import random
from _runner import EffectRunner, lerp, hex_color

runner = EffectRunner("Monet Water Lilies")

TEAL_DEEP = (46, 91, 82)       # #2E5B52
SAGE = (123, 168, 153)          # #7BA899
LAVENDER = (201, 160, 196)      # #C9A0C4
GOLDEN = (245, 222, 179)        # #F5DEB3

# Sun-dapple twinkle positions
NUM_DAPPLES = 8
dap_x = [random.random() for _ in range(NUM_DAPPLES)]
dap_y = [random.random() for _ in range(NUM_DAPPLES)]
dap_speed = [random.uniform(1.5, 4.0) for _ in range(NUM_DAPPLES)]
dap_phase = [random.uniform(0, math.tau) for _ in range(NUM_DAPPLES)]


def render_frame(device, t):
    colors = {}
    for lamp in device.lamps:
        lx, ly = lamp["x"], lamp["y"]

        # Layer 0: Slow teal-green pond wave
        wave = 0.5 + 0.5 * math.sin((lx * 3.5) - t * 1.0)
        color = lerp(TEAL_DEEP, SAGE, wave)

        # Layer 1: Lavender-pink breathing overlay
        breathe = 0.5 + 0.5 * math.sin(t * 0.8)
        color = lerp(color, LAVENDER, breathe * 0.3)

        # Layer 2: Sparse warm golden sun-dapple twinkles
        best_dap = 0.0
        for i in range(NUM_DAPPLES):
            dx = lx - dap_x[i]
            dy = ly - dap_y[i]
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < 0.20:
                pulse = max(0.0, math.sin(t * dap_speed[i] + dap_phase[i]))
                intensity = pulse * (1.0 - dist / 0.20)
                best_dap = max(best_dap, intensity)

        if best_dap > 0.1:
            color = lerp(color, GOLDEN, best_dap * 0.7)

        colors[str(lamp["idx"])] = hex_color(*color)
    return colors


runner.run(render_frame, fps=8)
