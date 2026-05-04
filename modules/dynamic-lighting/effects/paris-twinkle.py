import math
import random
from _runner import EffectRunner, lerp, hex_color

runner = EffectRunner("Paris Twinkle")

NAVY = (13, 27, 62)            # #0D1B3E
NAVY_LIGHT = (20, 40, 80)
GOLD = (255, 209, 128)         # #FFD180
WARM_WHITE = (255, 240, 210)

# Generate many star sparkles at different speeds for a rich city-lights feel
NUM_STARS = 20
star_x = [random.random() for _ in range(NUM_STARS)]
star_y = [random.random() for _ in range(NUM_STARS)]
star_speed = [random.uniform(1.5, 6.0) for _ in range(NUM_STARS)]
star_phase = [random.uniform(0, math.tau) for _ in range(NUM_STARS)]
star_color = [random.choice([GOLD, WARM_WHITE]) for _ in range(NUM_STARS)]


def render_frame(device, t):
    colors = {}
    for lamp in device.lamps:
        lx, ly = lamp["x"], lamp["y"]

        # Dark navy base with subtle breathing
        breathe = 0.5 + 0.5 * math.sin(t * 0.6)
        color = lerp(NAVY, NAVY_LIGHT, breathe * 0.3)

        # Golden sparkle stars twinkling at different speeds
        best_star = 0.0
        best_sc = GOLD
        for i in range(NUM_STARS):
            dx = lx - star_x[i]
            dy = ly - star_y[i]
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < 0.25:
                pulse = max(0.0, math.sin(t * star_speed[i] + star_phase[i]))
                intensity = pulse * pulse * (1.0 - dist / 0.25)
                if intensity > best_star:
                    best_star = intensity
                    best_sc = star_color[i]

        if best_star > 0.05:
            color = lerp(color, best_sc, best_star * 0.9)

        colors[str(lamp["idx"])] = hex_color(*color)
    return colors


runner.run(render_frame, fps=8)
