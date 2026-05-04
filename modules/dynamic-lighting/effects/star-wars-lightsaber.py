import math
import random
from _runner import EffectRunner, lerp, hex_color

runner = EffectRunner("Star Wars Lightsaber")

SITH_RED = (204, 0, 0)         # #CC0000
SITH_GLOW = (255, 40, 40)
JEDI_BLUE = (0, 68, 255)       # #0044FF
JEDI_GLOW = (60, 120, 255)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

# Spark positions for clash effect
NUM_SPARKS = 8
spark_phase = [random.uniform(0, math.tau) for _ in range(NUM_SPARKS)]
spark_speed = [random.uniform(4.0, 8.0) for _ in range(NUM_SPARKS)]
spark_offset = [random.uniform(-0.15, 0.15) for _ in range(NUM_SPARKS)]


def render_frame(device, t):
    colors = {}
    # Clash point oscillates around the middle
    clash = 0.5 + 0.15 * math.sin(t * 1.2)

    for lamp in device.lamps:
        lx, ly = lamp["x"], lamp["y"]
        dist_to_clash = abs(lx - clash)

        if lx < clash:
            # Red (Sith) side — brighter closer to clash
            intensity = max(0.3, 1.0 - (clash - lx) * 1.5)
            color = lerp(SITH_RED, SITH_GLOW, intensity)
        else:
            # Blue (Jedi) side — brighter closer to clash
            intensity = max(0.3, 1.0 - (lx - clash) * 1.5)
            color = lerp(JEDI_BLUE, JEDI_GLOW, intensity)

        # White sparks/flashes near the clash point
        if dist_to_clash < 0.20:
            best_spark = 0.0
            for i in range(NUM_SPARKS):
                spark_x = clash + spark_offset[i]
                sdist = abs(lx - spark_x)
                if sdist < 0.15:
                    pulse = max(0.0, math.sin(t * spark_speed[i] + spark_phase[i]))
                    flash = 1.0 if pulse > 0.7 else 0.0
                    si = flash * (1.0 - sdist / 0.15)
                    best_spark = max(best_spark, si)

            if best_spark > 0.1:
                color = lerp(color, WHITE, best_spark * 0.9)

        colors[str(lamp["idx"])] = hex_color(*color)
    return colors


runner.run(render_frame, fps=8)
